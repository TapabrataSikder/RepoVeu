from pathlib import Path


EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".sh": "shell",
    ".bash": "shell",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xml": "xml",
    ".toml": "toml",
    ".ini": "ini",
    ".md": "markdown",
    ".txt": "text",
}

def detect_language(file_path):
    """
    Detect the programming or markup language of a file.
    Args:
        file_path (str | Path): Path to the file.
    Returns:
        str: Detected language, or 'unknown'.
    """

    file_path = Path(file_path)

    extension = file_path.suffix.lower()

    return EXTENSION_TO_LANGUAGE.get(extension, "unknown")

if __name__ == "__main__":

    test_files = [
        "main.py",
        "script.js",
        "app.ts",
        "App.java",
        "index.html",
        "style.css",
        "config.json",
        "README.md",
        "unknown.xyz",
    ]

    for file in test_files:

        language = detect_language(file)

        print(f"{file:20} → {language}")