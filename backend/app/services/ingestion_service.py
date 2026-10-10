import hashlib
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

from app.models.base import db
from app.models.project import Project
from app.models.file_metadata import ProjectFile
from app.utils.file_filters import is_ignored_path, is_binary_file, detect_language
from app.utils.security import sanitize_relative_path, is_safe_path
from app.utils.logger import logger

# ─── Upload safety limits (override via config if needed) ────────────────────
MAX_ARCHIVE_ENTRIES = 10_000          # max number of entries in a ZIP
MAX_UNCOMPRESSED_BYTES = 500_000_000  # 500 MB uncompressed total
MAX_SINGLE_FILE_BYTES = 10_000_000    # 10 MB per source file


class IngestionError(ValueError):
    """Raised for user-visible ingestion validation failures."""


class IngestionService:

    # ──────────────────────────────────────────────────────────────────────────
    # ZIP validation
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def validate_zip(zip_file_path: Path) -> None:
        """
        Pre-validates a ZIP archive for safety before extraction.

        Raises IngestionError if:
        - The file is not a valid ZIP
        - Entry count exceeds MAX_ARCHIVE_ENTRIES (zip bomb guard)
        - Total uncompressed size exceeds MAX_UNCOMPRESSED_BYTES (zip bomb guard)
        - Any entry is an absolute path or contains traversal sequences
        - Any entry is a symlink
        """
        if not zipfile.is_zipfile(zip_file_path):
            raise IngestionError("Uploaded file is not a valid ZIP archive.")

        with zipfile.ZipFile(zip_file_path, "r") as archive:
            members = archive.infolist()

            if len(members) > MAX_ARCHIVE_ENTRIES:
                raise IngestionError(
                    f"Archive has too many entries ({len(members)} > {MAX_ARCHIVE_ENTRIES}). "
                    "Please reduce the archive size."
                )

            total_uncompressed = sum(m.file_size for m in members)
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise IngestionError(
                    f"Archive uncompressed content exceeds the limit of "
                    f"{MAX_UNCOMPRESSED_BYTES // 1_000_000} MB."
                )

            for member in members:
                name = member.filename

                # Reject absolute paths
                if name.startswith("/") or name.startswith("\\"):
                    raise IngestionError(
                        f"Archive contains an absolute path entry: {name!r}"
                    )

                # Reject traversal sequences
                parts = name.replace("\\", "/").split("/")
                if ".." in parts:
                    raise IngestionError(
                        f"Archive contains a path traversal entry: {name!r}"
                    )

                # Reject symlinks (external_attr encodes Unix file mode in high 16 bits)
                if (member.external_attr >> 16) & 0xA000 == 0xA000:
                    raise IngestionError(
                        f"Archive contains a symlink entry which is not permitted: {name!r}"
                    )

    # ──────────────────────────────────────────────────────────────────────────
    # Extraction
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def extract_zip(zip_file_path: Path, target_dir: Path) -> List[Path]:
        """
        Safely extracts a validated ZIP archive into target_dir.

        - Skips directory-only entries
        - Sanitises all member paths (no traversal, no absolute paths)
        - Skips ignored paths (node_modules, .git, secrets, binaries, etc.)
        - Enforces per-file size limit
        - Verifies every destination path stays within target_dir
        - Removes extracted binary files (keeps storage clean)

        Returns a list of successfully extracted text-file Paths.
        """
        extracted_files: List[Path] = []
        target_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_file_path, "r") as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue

                # Per-file decompressed size guard
                if member.file_size > MAX_SINGLE_FILE_BYTES:
                    logger.info(
                        f"Skipping oversized entry {member.filename!r} "
                        f"({member.file_size} bytes)"
                    )
                    continue

                clean_name = sanitize_relative_path(member.filename)
                if not clean_name:
                    continue

                if is_ignored_path(clean_name):
                    logger.debug(f"Skipping ignored path in zip: {clean_name}")
                    continue

                dest_path = target_dir / clean_name

                # Final traversal guard
                if not is_safe_path(target_dir, dest_path):
                    logger.warning(
                        f"Blocked path-traversal attempt in ZIP: {member.filename!r}"
                    )
                    continue

                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())

                if not is_binary_file(dest_path):
                    extracted_files.append(dest_path)
                else:
                    dest_path.unlink(missing_ok=True)

        return extracted_files

    # ──────────────────────────────────────────────────────────────────────────
    # DB sync
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def sync_project_files_to_db(project: Project) -> Tuple[int, List[ProjectFile]]:
        """
        Scans the project's source directory and upserts file metadata into
        the project_files table.

        Uses content hashes to skip re-processing identical files (duplicate upload).
        Returns (file_count, list_of_ProjectFile).
        """
        source_dir = Path(project.storage_path) / "source"
        if not source_dir.exists():
            return 0, []

        # Build a lookup of existing records keyed by rel_path
        existing: Dict[str, ProjectFile] = {
            pf.file_path: pf
            for pf in ProjectFile.query.filter_by(project_id=project.id).all()
        }

        seen_paths = set()
        db_files: List[ProjectFile] = []

        for file_path in sorted(source_dir.rglob("*")):
            if not file_path.is_file():
                continue

            rel_path = file_path.relative_to(source_dir).as_posix()

            if is_ignored_path(rel_path) or is_binary_file(file_path):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                content_bytes = content.encode("utf-8")
                content_hash = hashlib.sha256(content_bytes).hexdigest()
                line_count = len(content.splitlines())
                file_size = file_path.stat().st_size
                language = detect_language(rel_path)

                if rel_path in existing:
                    pf = existing[rel_path]
                    if pf.content_hash == content_hash:
                        # File unchanged – keep existing record as-is
                        db_files.append(pf)
                        seen_paths.add(rel_path)
                        continue
                    # File changed – update record
                    pf.file_type = language
                    pf.content_hash = content_hash
                    pf.file_size = file_size
                    pf.line_count = line_count
                else:
                    pf = ProjectFile(
                        project_id=project.id,
                        file_path=rel_path,
                        file_type=language,
                        content_hash=content_hash,
                        file_size=file_size,
                        line_count=line_count,
                    )
                    db.session.add(pf)

                db_files.append(pf)
                seen_paths.add(rel_path)

            except Exception as exc:
                logger.warning(f"Could not process file {rel_path}: {exc}")

        # Remove records for files that no longer exist on disk
        for rel_path, pf in existing.items():
            if rel_path not in seen_paths:
                db.session.delete(pf)

        project.file_count = len(db_files)
        db.session.commit()
        logger.info(f"Synced {len(db_files)} files for project ID {project.id}")
        return len(db_files), db_files

    # ──────────────────────────────────────────────────────────────────────────
    # File tree builder
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def build_file_tree(source_dir: Path) -> List[Dict]:
        """
        Builds a nested directory-tree for frontend navigation.
        Never includes server absolute paths — only relative paths within source_dir.
        """
        if not source_dir.exists():
            return []

        def build_node(current_path: Path) -> Dict:
            rel = (
                current_path.relative_to(source_dir).as_posix()
                if current_path != source_dir
                else ""
            )
            if current_path.is_file():
                return {
                    "name": current_path.name,
                    "path": rel,
                    "type": "file",
                    "language": detect_language(rel),
                    "size": current_path.stat().st_size,
                }

            children = []
            for child in sorted(
                current_path.iterdir(),
                key=lambda c: (not c.is_dir(), c.name.lower()),
            ):
                child_rel = child.relative_to(source_dir).as_posix()
                if is_ignored_path(child_rel):
                    continue
                if child.is_file() and is_binary_file(child):
                    continue
                children.append(build_node(child))

            return {
                "name": current_path.name if current_path != source_dir else "root",
                "path": rel,
                "type": "directory",
                "children": children,
            }

        root_node = build_node(source_dir)
        return root_node.get("children", [])
