from pathlib import Path


# Files not to consider for scanning
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


IGNORED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".exe",
    ".dll",
    ".so",
    ".class",
    ".o",
    ".obj",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".zip",
    ".tar",
    ".gz",
}


def discover_files(repository_path):
    """
    Discover relevant files inside a local repository.

    Args:
        repository_path (str): Path to the downloaded repository.

    Returns:
        list: List of discovered file paths.
    """

    repository_path = Path(repository_path)

    if not repository_path.exists():
        return []

    if not repository_path.is_dir():
        return []

    available_files = []

    for path in repository_path.rglob("*"):

        # Ignore directories
        if path.is_dir():
            continue

        # Ignore files inside unwanted directories
        if any(
            directory in IGNORED_DIRECTORIES
            for directory in path.parts
        ):
            continue

        # Ignore unwanted file extensions
        if path.suffix.lower() in IGNORED_EXTENSIONS:
            continue

        available_files.append(path)

    return available_files


if __name__ == "__main__":

    repository_path = "data/repositories/CogWorksBWSI_GitPracticeRepo"

    files = discover_files(repository_path)

    print(f"Found {len(files)} files\n")

    for file in files:
        print(file)