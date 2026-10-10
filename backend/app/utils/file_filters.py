from pathlib import Path
import re

IGNORED_DIRECTORIES = {
    ".git", ".svn", ".hg",
    "node_modules", "venv", ".venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    ".next", ".nuxt", "dist", "build", "out", "target", "bin", "obj",
    ".idea", ".vscode", ".tox", "coverage", ".bundle", "vendor"
}

IGNORED_FILES = {
    ".ds_store", "thumbs.db", "desktop.ini",
    "id_rsa", "id_rsa.pub", "id_ed25519", "id_ecdsa",
    "npm-debug.log", "yarn-error.log", "pnpm-debug.log"
}

IGNORED_EXTENSIONS = {
    # Binaries and compiled
    ".exe", ".dll", ".so", ".dylib", ".bin", ".iso", ".class", ".pyc", ".pyo", ".o", ".a", ".obj",
    # Archives
    ".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz",
    # Images and Media
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff", ".pdf",
    ".mp4", ".mp3", ".wav", ".avi", ".mov", ".flv", ".webm",
    # Fonts
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Source maps and minified
    ".map",
    # Secrets & Certificates
    ".pem", ".key", ".pfx", ".p12", ".keystore", ".jks"
}

SECRET_NAME_PATTERNS = [
    re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
    re.compile(r".*credential.*", re.IGNORECASE),
    re.compile(r".*secret.*", re.IGNORECASE),
    re.compile(r".*password.*", re.IGNORECASE),
    re.compile(r"^id_[a-z0-9_]+$", re.IGNORECASE),
]

EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "scss",
    ".less": "less",
    ".json": "json",
    ".ipynb": "notebook",
    ".csv": "csv",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sql": "sql",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".sh": "shell",
    ".bash": "shell",
    ".ps1": "powershell",
    ".xml": "xml",
    ".toml": "toml",
    ".dockerfile": "dockerfile"
}

def is_ignored_path(relative_path_str: str) -> bool:
    """
    Check if a relative file path matches any exclusion rule (secrets, dependencies, build, binary).
    """
    clean_path = relative_path_str.replace("\\", "/").strip("/")
    parts = clean_path.split("/")
    filename = parts[-1].lower() if parts else ""
    ext = Path(filename).suffix.lower()

    # Check directory components
    for dir_part in parts[:-1]:
        if dir_part.lower() in IGNORED_DIRECTORIES:
            return True

    # Check file names and extensions
    if filename in IGNORED_FILES or ext in IGNORED_EXTENSIONS:
        return True

    # Check for secret patterns (.env, secrets, credentials)
    for pattern in SECRET_NAME_PATTERNS:
        if pattern.match(filename):
            return True

    return False

def is_binary_file(file_path: Path) -> bool:
    """
    Check if a file appears to be binary by scanning the first 8192 bytes for null bytes.
    """
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
            if b"\x00" in chunk:
                return True
        return False
    except Exception:
        return True

def detect_language(file_path_str: str) -> str:
    """
    Detect programming language from file extension. Defaults to 'plaintext'.
    """
    name = Path(file_path_str).name.lower()
    if name == "dockerfile":
        return "dockerfile"
    if name in ("makefile", "gnumakefile"):
        return "makefile"

    ext = Path(file_path_str).suffix.lower()
    return EXTENSION_LANGUAGE_MAP.get(ext, "plaintext")
