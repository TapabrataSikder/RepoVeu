from pathlib import Path
import json


# ==================================================
# FILE EXTENSION CLASSIFICATION
# ==================================================

CODE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".kt": "kotlin",
}

DOCUMENTATION_EXTENSIONS = {
    ".md",
    ".markdown",
    ".rst",
    ".txt",
}

CONFIGURATION_FILES = {
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "pom.xml",
    "build.gradle",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".gitignore",
}

IGNORED_DIRECTORIES = {
    ".git",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    ".idea",
    ".vscode",
}


# ==================================================
# CLASSIFY FILE
# ==================================================

def classify_file(file_path: Path):
    extension = file_path.suffix.lower()
    file_name = file_path.name.lower()

    if extension in CODE_EXTENSIONS:
        return {
            "type": "code",
            "language": CODE_EXTENSIONS[extension]
        }

    if extension in DOCUMENTATION_EXTENSIONS:
        return {
            "type": "documentation",
            "language": "markdown"
        }

    if file_name in CONFIGURATION_FILES:
        return {
            "type": "configuration",
            "language": None
        }

    if file_name == ".env":
        return {
            "type": "environment",
            "language": None
        }

    return {
        "type": "other",
        "language": None
    }


# ==================================================
# CREATE REPOSITORY MANIFEST
# ==================================================

def create_repository_manifest(
    repository_path,
    repository_id,
    owner,
    repository_name
):
    repository_path = Path(repository_path)

    files = []
    directories = set()
    language_counts = {}

    # Scan repository
    for path in repository_path.rglob("*"):

        # Skip directories
        if path.is_dir():
            relative_path = path.relative_to(repository_path)
            parts = relative_path.parts

            if any(part in IGNORED_DIRECTORIES for part in parts):
                continue

            directories.add(relative_path.as_posix())
            continue

        # Skip files inside ignored directories
        relative_path = path.relative_to(repository_path)
        parts = relative_path.parts

        if any(part in IGNORED_DIRECTORIES for part in parts):
            continue

        # Classify file
        classification = classify_file(path)

        file_info = {
            "path": relative_path.as_posix(),
            "name": path.name,
            "type": classification["type"],
            "language": classification["language"]
        }

        files.append(file_info)

        # Language statistics
        language = classification["language"]

        if language:
            language_counts[language] = (
                language_counts.get(language, 0) + 1
            )

    # Create manifest
    manifest = {
        "repository_id": repository_id,
        "owner": owner,
        "repository": repository_name,
        "total_files": len(files),
        "total_directories": len(directories),
        "directories": sorted(directories),
        "files": files,
        "languages": language_counts
    }

    return manifest


# ==================================================
# SAVE REPOSITORY MANIFEST
# ==================================================

def save_repository_manifest(
    manifest,
    output_directory
):
    output_directory = Path(output_directory)
    output_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    repository_id = manifest["repository_id"]

    output_file = (
        output_directory /
        f"{repository_id}.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            manifest,
            file,
            indent=4,
            ensure_ascii=False
        )

    return output_file


