from pathlib import Path


def read_file(file_path):
    """
    Read a text file and return its contents.
    Args:
        file_path (str | Path): Path to the file.
    Returns:
        str | None: File contents, or None if the file cannot be read.
    """

    file_path = Path(file_path)
    if not file_path.exists():
        return None

    if not file_path.is_file():
        return None

    try:
        return file_path.read_text(encoding="utf-8")

    except UnicodeDecodeError:
        return None

    except OSError:
        return None


if __name__ == "__main__":

    file_path = "data/repositories/CogWorksBWSI_GitPracticeRepo/README.md"

    content = read_file(file_path)

    if content is None:
        print("File is empty or corrupted.")
    else:
        print(f"Content: {content[:210]}")

