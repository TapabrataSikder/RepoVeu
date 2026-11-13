from pathlib import Path


# --------------------------------------------------
# Supported Languages
# --------------------------------------------------

LANGUAGE_MAP = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
    ".cpp": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
}


# --------------------------------------------------
# Directories to Ignore
# --------------------------------------------------

IGNORED_DIRECTORIES = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "venv",
    ".venv",
    "node_modules",
    "target",
    "build",
    "dist",
}


# --------------------------------------------------
# Discover Repository Files
# --------------------------------------------------

def discover_files(repository_path):

    repository_path = Path(repository_path)

    files = []

    for path in repository_path.rglob("*"):

        if not path.is_file():
            continue

        if any(
            ignored in path.parts
            for ignored in IGNORED_DIRECTORIES
        ):
            continue

        files.append(path)

    return files


# --------------------------------------------------
# Detect Language
# --------------------------------------------------

def detect_language(file_path):

    suffix = Path(file_path).suffix.lower()

    return LANGUAGE_MAP.get(suffix)


# --------------------------------------------------
# Generate Repository Metadata
# --------------------------------------------------

def get_repository_metadata(repository_path):

    files = discover_files(repository_path)

    supported_files = []
    unsupported_files = []

    languages = {}

    for file_path in files:

        language = detect_language(file_path)

        if language is None:

            unsupported_files.append(file_path)

        else:

            supported_files.append(file_path)

            languages[language] = (
                languages.get(language, 0) + 1
            )

    metadata = {
        "repository_path": str(repository_path),
        "total_files": len(files),
        "supported_files": len(supported_files),
        "unsupported_files": len(unsupported_files),
        "languages": languages,
    }

    return metadata


# --------------------------------------------------
# Test
# --------------------------------------------------

if __name__ == "__main__":

    repository_path = (
        "data/repositories/"
        "TapabrataSikder_Spring-Boot"
    )

    metadata = get_repository_metadata(
        repository_path
    )

    print("=" * 50)
    print("REPOSITORY METADATA")
    print("=" * 50)

    print(
        f"Repository       : "
        f"{metadata['repository_path']}"
    )

    print(
        f"Total files      : "
        f"{metadata['total_files']}"
    )

    print(
        f"Supported files  : "
        f"{metadata['supported_files']}"
    )

    print(
        f"Unsupported files: "
        f"{metadata['unsupported_files']}"
    )

    print(
        f"Languages        : "
        f"{metadata['languages']}"
    )