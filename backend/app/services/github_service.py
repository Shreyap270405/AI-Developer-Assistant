import io
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from urllib.parse import urlparse
import requests
from app.config import Config
from app.utils.file_filters import is_ignored_path, is_binary_file
from app.utils.security import sanitize_relative_path, is_safe_path
from app.utils.logger import logger

# Safety and limits
MAX_GITHUB_ARCHIVE_BYTES = 52_428_800    # 50 MB zip limit
MAX_UNCOMPRESSED_BYTES = 200_000_000     # 200 MB uncompressed limit
MAX_ARCHIVE_ENTRIES = 10_000             # 10,000 files max
MAX_SINGLE_FILE_BYTES = 10_000_000       # 10 MB per file
REQUEST_TIMEOUT_SECONDS = 45


class GitHubImportError(ValueError):
    """Raised for validation or upstream GitHub errors during repository import."""
    def __init__(self, message: str, status_code: int = 400, error_code: str = "github_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class GitHubService:
    """
    Dedicated service for safe GitHub repository validation, metadata retrieval,
    archive downloading, sanitization, and extraction into local project storage.
    """

    @staticmethod
    def parse_repo_url(url: str) -> Tuple[str, str, Optional[str]]:
        """
        Extracts owner, repository name, and optional ref (branch/commit) from a GitHub URL.
        Prevents SSRF by validating the domain and structure strictly.

        Accepts:
        - https://github.com/owner/repo
        - https://github.com/owner/repo/tree/branch-name
        - https://github.com/owner/repo.git
        - github.com/owner/repo
        - owner/repo
        """
        if not url or not isinstance(url, str):
            raise GitHubImportError("Repository URL is required and must be a string.", 400, "invalid_url")

        clean_url = url.strip()
        if not clean_url:
            raise GitHubImportError("Repository URL cannot be empty.", 400, "invalid_url")

        # Normalize URL with scheme if missing
        if clean_url.startswith("github.com/"):
            clean_url = "https://" + clean_url
        elif not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            # Check for simple owner/repo pattern
            simple_match = re.match(r"^([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)$", clean_url)
            if simple_match:
                owner, repo = simple_match.group(1), simple_match.group(2)
                if repo.endswith(".git"):
                    repo = repo[:-4]
                return owner, repo, None
            else:
                clean_url = "https://" + clean_url

        try:
            parsed = urlparse(clean_url)
        except Exception:
            raise GitHubImportError(f"Malformed URL provided: {url}", 400, "invalid_url")

        # SSRF Defense: Enforce GitHub hostname only
        hostname = (parsed.hostname or "").lower()
        if hostname not in ("github.com", "www.github.com"):
            raise GitHubImportError(
                f"Unsupported host '{hostname}'. Only official GitHub repositories ('github.com') are supported.",
                400,
                "unsupported_host"
            )

        # Path parsing: /owner/repo[/tree/ref]
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(path_parts) < 2:
            raise GitHubImportError(
                "Invalid GitHub URL structure. Expected 'https://github.com/<owner>/<repo>'.",
                400,
                "invalid_url_structure"
            )

        owner = path_parts[0]
        repo = path_parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]

        # Validate owner and repo format against standard GitHub naming patterns
        name_pattern = r"^[a-zA-Z0-9_.-]+$"
        if not re.match(name_pattern, owner) or not re.match(name_pattern, repo):
            raise GitHubImportError("Invalid characters detected in repository owner or name.", 400, "invalid_repo_name")

        if owner in (".", "..") or repo in (".", ".."):
            raise GitHubImportError("Invalid path traversal sequence in repository identifier.", 400, "invalid_repo_name")

        ref = None
        if len(path_parts) >= 4 and path_parts[2] in ("tree", "commits", "releases"):
            ref = "/".join(path_parts[3:])

        return owner, repo, ref

    @classmethod
    def _get_headers(cls, user_token: Optional[str] = None) -> Dict[str, str]:
        """Builds standard GitHub API request headers."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-Developer-Assistant/1.0"
        }
        # Priority: explicit user token (if supplied) -> server configured token
        token = user_token or Config.GITHUB_API_TOKEN
        if token and token.strip():
            headers["Authorization"] = f"Bearer {token.strip()}"
        return headers

    @classmethod
    def validate_repository(
        cls,
        repo_url: str,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validates that a GitHub repository exists, is accessible, and retrieves repository metadata
        without downloading source archives.
        """
        owner, repo, ref = cls.parse_repo_url(repo_url)
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = cls._get_headers(token)

        logger.info(f"Validating GitHub repository '{owner}/{repo}' via {api_url}...")

        try:
            resp = requests.get(api_url, headers=headers, timeout=15)
        except requests.exceptions.Timeout:
            raise GitHubImportError("Connection to GitHub API timed out during validation.", 504, "timeout")
        except requests.exceptions.RequestException as e:
            raise GitHubImportError(f"Network error connecting to GitHub: {str(e)}", 502, "network_error")

        if resp.status_code == 404:
            raise GitHubImportError(
                f"GitHub repository '{owner}/{repo}' not found or is private.",
                404,
                "not_found"
            )
        if resp.status_code == 401:
            raise GitHubImportError("GitHub authentication failed. Please verify your token.", 401, "unauthorized")
        if resp.status_code == 403:
            reset_time = resp.headers.get("X-RateLimit-Reset")
            reset_msg = ""
            if reset_time:
                try:
                    reset_dt = datetime.fromtimestamp(int(reset_time), tz=timezone.utc)
                    reset_msg = f" Rate limit resets at {reset_dt.strftime('%H:%M:%S UTC')}."
                except Exception:
                    pass
            raise GitHubImportError(
                f"GitHub API rate limit exceeded.{reset_msg} Set GITHUB_API_TOKEN in backend environment to increase quota.",
                429,
                "rate_limit_exceeded"
            )
        if resp.status_code != 200:
            raise GitHubImportError(
                f"GitHub API returned error code {resp.status_code}.",
                resp.status_code,
                "provider_error"
            )

        data = resp.json()
        default_branch = ref or data.get("default_branch", "main")
        size_kb = data.get("size", 0)

        # Get latest commit SHA on default branch
        commit_sha = ""
        try:
            commit_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{default_branch}"
            commit_resp = requests.get(commit_url, headers=headers, timeout=10)
            if commit_resp.status_code == 200:
                commit_data = commit_resp.json()
                commit_sha = commit_data.get("sha", "")[:8]
        except Exception as e:
            logger.warning(f"Could not fetch commit SHA for {owner}/{repo}: {e}")

        return {
            "valid": True,
            "owner": data.get("owner", {}).get("login", owner),
            "repo": data.get("name", repo),
            "full_name": data.get("full_name", f"{owner}/{repo}"),
            "description": data.get("description") or "",
            "default_branch": default_branch,
            "commit_sha": commit_sha,
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "language": data.get("language") or "plaintext",
            "size_kb": size_kb,
            "is_private": data.get("private", False),
            "html_url": data.get("html_url", f"https://github.com/{owner}/{repo}")
        }

    @classmethod
    def import_repository(
        cls,
        repo_url: str,
        target_dir: Path,
        token: Optional[str] = None,
        ref: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Downloads and safely unpacks repository source code using GitHub REST API zipball endpoint.
        Cleans existing files in target_dir to guarantee no stale files remain.
        """
        # 1. Validate & get metadata
        meta = cls.validate_repository(repo_url, token=token)
        owner = meta["owner"]
        repo = meta["repo"]
        target_branch = ref or meta["default_branch"]

        zip_api_url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{target_branch}"
        headers = cls._get_headers(token)

        logger.info(f"Streaming GitHub repository zipball for '{owner}/{repo}' ({target_branch})...")

        try:
            resp = requests.get(
                zip_api_url,
                headers=headers,
                stream=True,
                timeout=REQUEST_TIMEOUT_SECONDS
            )
        except requests.exceptions.Timeout:
            raise GitHubImportError("GitHub repository archive download timed out.", 504, "timeout")
        except requests.exceptions.RequestException as e:
            raise GitHubImportError(f"Network failure downloading repository archive: {str(e)}", 502, "network_error")

        if resp.status_code == 404:
            raise GitHubImportError(f"GitHub repository archive '{owner}/{repo}' not found.", 404, "not_found")
        if resp.status_code == 403:
            raise GitHubImportError("GitHub API rate limit exceeded while downloading repository archive.", 429, "rate_limit_exceeded")
        if resp.status_code != 200:
            raise GitHubImportError(f"GitHub API returned error code {resp.status_code} during archive download.", resp.status_code, "provider_error")

        # Stream download with byte limit check to guard against huge downloads
        archive_bytes = bytearray()
        downloaded = 0
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                downloaded += len(chunk)
                if downloaded > MAX_GITHUB_ARCHIVE_BYTES:
                    raise GitHubImportError(
                        f"Repository archive exceeds maximum allowed download size of {MAX_GITHUB_ARCHIVE_BYTES // 1_000_000} MB.",
                        413,
                        "archive_too_large"
                    )
                archive_bytes.extend(chunk)

        if not archive_bytes:
            raise GitHubImportError("Downloaded GitHub repository archive is empty.", 400, "empty_archive")

        # 2. Extract and sanitize contents
        try:
            archive = zipfile.ZipFile(io.BytesIO(archive_bytes), "r")
        except zipfile.BadZipFile:
            raise GitHubImportError("Received invalid ZIP archive from GitHub API.", 502, "corrupt_archive")

        with archive:
            members = archive.infolist()
            if not members:
                raise GitHubImportError("GitHub archive contains no files.", 400, "empty_archive")

            if len(members) > MAX_ARCHIVE_ENTRIES:
                raise GitHubImportError(
                    f"Repository exceeds maximum allowed entry count ({len(members)} > {MAX_ARCHIVE_ENTRIES}).",
                    400,
                    "too_many_files"
                )

            total_uncompressed = sum(m.file_size for m in members)
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise GitHubImportError(
                    f"Repository uncompressed size exceeds limit of {MAX_UNCOMPRESSED_BYTES // 1_000_000} MB.",
                    400,
                    "uncompressed_size_exceeded"
                )

            # Ensure clean directory state (wipe previous files to eliminate stale leftovers on re-import)
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            target_dir.mkdir(parents=True, exist_ok=True)

            # GitHub archives wrap all files in a root directory (e.g. `owner-repo-sha/`)
            root_prefix = members[0].filename.split("/")[0] + "/"

            extracted_count = 0
            for member in members:
                if member.is_dir():
                    continue

                rel_name = member.filename
                if rel_name.startswith(root_prefix):
                    rel_name = rel_name[len(root_prefix):]

                clean_name = sanitize_relative_path(rel_name)
                if not clean_name or is_ignored_path(clean_name):
                    continue

                if member.file_size > MAX_SINGLE_FILE_BYTES:
                    logger.warning(f"Skipping oversized file {clean_name} ({member.file_size} bytes)")
                    continue

                dest_path = target_dir / clean_name
                if not is_safe_path(target_dir, dest_path):
                    continue

                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())

                if is_binary_file(dest_path):
                    dest_path.unlink(missing_ok=True)
                else:
                    extracted_count += 1

        logger.info(f"Extracted {extracted_count} clean source files from GitHub repository {owner}/{repo}")

        return {
            "owner": owner,
            "repo": repo,
            "branch": target_branch,
            "commit_sha": meta["commit_sha"],
            "extracted_count": extracted_count,
            "description": meta["description"],
            "html_url": meta["html_url"],
            "stars": meta["stars"]
        }
