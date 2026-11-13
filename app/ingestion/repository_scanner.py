from pathlib import Path

from app.ingestion.file_discover import discover_files
from app.ingestion.file_reader import read_file

from app.ingestion.language_detector import detect_language


def scan_repository(repository_path):
    """
    Discover, read, identify files from a local repository.
    Args:
        repository_path (str): Path to the repository.
    Returns:
        list: Structured information about readable files.
    """

    repository_path = Path(repository_path)
     
    files = discover_files(repository_path)

    documents = []

    for file_path in files:
        content = read_file(file_path)

        # Skip files that cannot be read
        if content is None:
            continue

        # The relative_path will be used for RAG citations 
        # and telling the LLM where a piece of code came from.
        relative_path = file_path.relative_to(repository_path)
        language = detect_language(file_path)

        documents.append({
            "path": str(file_path),
            "relative_path": str(relative_path),
            "filename": file_path.name,
            "extension": file_path.suffix.lower(),
            "language": language,
            "content": content
        })

    return documents


if __name__ == "__main__":

    repository_path = "data/repositories/CogWorksBWSI_GitPracticeRepo"

    documents = scan_repository(repository_path)

    print(f"Found {len(documents)} readable files\n")

    for document in documents:

        print("-" * 60)
        print(f"File: {document['filename']}")
        print(f"Extension: {document['extension']}")
        print(f"Path: {document['path']}")
        print(f"Relative Path: {document['relative_path']}")
        print(f"Language: {document['language']}")
        print(f"Content preview:")
        print(document["content"][:220])