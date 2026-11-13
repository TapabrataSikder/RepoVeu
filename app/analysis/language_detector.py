from pathlib import Path


EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".java": "java",
}


def detect_language(file_path):
    """
    Detect programming language from file extension.

    Args:
        file_path: Path to the source file.

    Returns:
        str | None: Detected language.
    """

    file_path = Path(file_path)

    extension = file_path.suffix.lower()

    return EXTENSION_TO_LANGUAGE.get(extension)