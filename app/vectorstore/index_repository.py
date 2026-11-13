
# app/vectorstore/index_repository.py
# To run this file independently:
# python -m app.vectorstore.index_repository

from pathlib import Path

from app.analysis.repository_analyzer import analyze_repository
from app.ingestion.code_chunker import create_symbol_chunks
from app.embeddings.embedder import generate_embeddings

from app.vectorstore.chroma_store import (
    add_chunks,
    count_repository_chunks,
)


# --------------------------------------------------
# Index Repository
# --------------------------------------------------

def index_repository(
    repository_path,
    repository_id,
    branch=None,
    selected_path=None,
):
    """
    Analyze, chunk, embed and index one repository path.

    Args:
        repository_path: Root path of the downloaded repository.
        repository_id: Unique repository identifier used by ChromaDB.
        branch: Git branch selected from the GitHub URL.
        selected_path: Optional path inside the repository to index.

    Returns:
        dict: Indexing result.
    """

    repository_path = Path(repository_path)

    print()
    print("=" * 50)
    print("REPOSITORY INDEXING")
    print("=" * 50)

    print(f"Repository ID   : {repository_id}")
    print(f"Repository path : {repository_path}")
    print(f"Branch          : {branch}")
    print(f"Selected path   : {selected_path}")

    # --------------------------------------------------
    # Validate repository path
    # --------------------------------------------------

    if not repository_path.exists():
        print()
        print(
            f"Repository path does not exist: "
            f"{repository_path}"
        )

        return {
            "success": False,
            "indexed": False,
            "chunks": 0,
            "indexed_count": 0,
            "error": (
                f"Repository path does not exist: "
                f"{repository_path}"
            ),
        }

    if not repository_path.is_dir():
        print()
        print(
            f"Repository path is not a directory: "
            f"{repository_path}"
        )

        return {
            "success": False,
            "indexed": False,
            "chunks": 0,
            "indexed_count": 0,
            "error": (
                f"Repository path is not a directory: "
                f"{repository_path}"
            ),
        }

    # --------------------------------------------------
    # Resolve selected repository path
    # --------------------------------------------------

    analysis_path = repository_path

    if selected_path:
        normalized_path = selected_path.strip("/\\")
        relative_path = Path(normalized_path)

        # Prevent path traversal
        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            print()
            print(
                "Invalid selected repository path:",
                selected_path,
            )

            return {
                "success": False,
                "indexed": False,
                "chunks": 0,
                "indexed_count": 0,
                "error": "Invalid selected repository path.",
            }

        analysis_path = (
            repository_path / relative_path
        ).resolve()

        repository_root = repository_path.resolve()

        # Make sure selected path stays inside repository
        if (
            analysis_path != repository_root
            and repository_root not in analysis_path.parents
        ):
            print()
            print(
                "Selected path is outside repository:",
                selected_path,
            )

            return {
                "success": False,
                "indexed": False,
                "chunks": 0,
                "indexed_count": 0,
                "error": "Invalid selected repository path.",
            }

        if not analysis_path.exists():
            print()
            print(
                "Selected repository path does not exist:",
                analysis_path,
            )

            return {
                "success": False,
                "indexed": False,
                "chunks": 0,
                "indexed_count": 0,
                "error": (
                    "Selected repository path does not exist: "
                    f"{selected_path}"
                ),
            }

        if not analysis_path.is_dir():
            print()
            print(
                "Selected repository path is not a directory:",
                analysis_path,
            )

            return {
                "success": False,
                "indexed": False,
                "chunks": 0,
                "indexed_count": 0,
                "error": (
                    "Selected repository path is not a directory: "
                    f"{selected_path}"
                ),
            }

    print()
    print(f"Analysis path   : {analysis_path}")

    # --------------------------------------------------
    # Step 1: Analyze repository
    # --------------------------------------------------

    print()
    print("[1/5] Analyzing repository...")

    symbols = analyze_repository(
        analysis_path
    )

    print(
        f"Symbols found   : {len(symbols)}"
    )

    # --------------------------------------------------
    # Step 2: Create chunks
    # --------------------------------------------------

    print()
    print("[2/5] Creating code chunks...")

    chunks = create_symbol_chunks(
        symbols
    )

    print(
        f"Chunks created  : {len(chunks)}"
    )

    if not chunks:
        print()
        print("-" * 50)
        print("No supported code found.")
        print(
            "Repository path may contain only "
            "unsupported files or no code symbols."
        )
        print("Indexing skipped.")

        return {
            "success": False,
            "indexed": False,
            "chunks": 0,
            "indexed_count": 0,
            "error": (
                "No supported code found "
                "in repository path."
            ),
        }

    # --------------------------------------------------
    # Step 3: Generate embeddings
    # --------------------------------------------------

    print()
    print("[3/5] Generating embeddings...")

    texts = [
        chunk.content
        for chunk in chunks
    ]

    embeddings = generate_embeddings(
        texts
    )

    if embeddings is None or len(embeddings) == 0:
        print()
        print("Embedding generation failed.")
        print("Indexing skipped.")

        return {
            "success": False,
            "indexed": False,
            "chunks": len(chunks),
            "indexed_count": 0,
            "error": "Embedding generation failed.",
        }

    if len(chunks) != len(embeddings):
        print()
        print(
            "Embedding count does not match chunk count."
        )
        print("Indexing skipped.")

        return {
            "success": False,
            "indexed": False,
            "chunks": len(chunks),
            "indexed_count": 0,
            "error": (
                "Number of generated embeddings does not "
                "match the number of code chunks."
            ),
        }

    print(
        f"Embeddings      : {len(embeddings)}"
    )

    # --------------------------------------------------
    # Step 4: Store in ChromaDB
    # --------------------------------------------------

    print()
    print("[4/5] Storing chunks in ChromaDB...")

    add_chunks(
        chunks,
        embeddings,
        repository_id,
    )

    # --------------------------------------------------
    # Step 5: Verify indexed chunks
    # --------------------------------------------------

    print()
    print("[5/5] Verifying indexed chunks...")

    indexed_count = count_repository_chunks(
        repository_id
    )

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    print()
    print("-" * 50)

    print(
        f"Symbols indexed : {len(symbols)}"
    )

    print(
        f"Chunks indexed  : {len(chunks)}"
    )

    print(
        f"Embeddings      : {len(embeddings)}"
    )

    print(
        f"Repository chunks in DB : {indexed_count}"
    )

    print(
        "Vector database : ChromaDB"
    )

    print(
        "Repository isolation : Enabled"
    )

    print(
        "Status          : Indexing complete"
    )

    # --------------------------------------------------
    # Verify ChromaDB actually contains chunks
    # --------------------------------------------------

    if indexed_count == 0:
        return {
            "success": False,
            "indexed": False,
            "chunks": len(chunks),
            "indexed_count": 0,
            "error": (
                "Chunks were generated but were not "
                "successfully stored in ChromaDB."
            ),
        }

    return {
        "success": True,
        "indexed": True,
        "chunks": len(chunks),
        "indexed_count": indexed_count,
        "error": None,
    }


# --------------------------------------------------
# Standalone execution
# --------------------------------------------------

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]

    repositories_dir = (
        project_root / "data" / "repositories"
    )

    # --------------------------------------------------
    # Check repository directory
    # --------------------------------------------------

    if not repositories_dir.exists():
        print("=" * 50)
        print("REPOSITORY INDEXING")
        print("=" * 50)

        print()
        print("No downloaded repositories found.")

        print(
            "Download a GitHub repository first."
        )

        exit()

    # --------------------------------------------------
    # Find repositories
    # --------------------------------------------------

    repositories = [
        directory
        for directory in repositories_dir.iterdir()
        if directory.is_dir()
        and directory.name != ".git"
    ]

    # --------------------------------------------------
    # No repositories
    # --------------------------------------------------

    if not repositories:
        print("=" * 50)
        print("REPOSITORY INDEXING")
        print("=" * 50)

        print()
        print("No downloaded repositories found.")

        print(
            "Download a GitHub repository first."
        )

        exit()

    # --------------------------------------------------
    # Show repositories
    # --------------------------------------------------

    print("=" * 50)
    print("AVAILABLE REPOSITORIES")
    print("=" * 50)

    print()

    for index, repository in enumerate(
        repositories,
        start=1,
    ):
        print(
            f"{index}. {repository.name}"
        )

    # --------------------------------------------------
    # Select repository
    # --------------------------------------------------

    print()

    try:
        choice = int(
            input(
                "Select repository number: "
            )
        )
    except ValueError:
        print(
            "Invalid input. "
            "Please enter a number."
        )

        exit()

    # --------------------------------------------------
    # Validate selection
    # --------------------------------------------------

    if (
        choice < 1
        or choice > len(repositories)
    ):
        print(
            "Invalid repository selection."
        )

        exit()

    # --------------------------------------------------
    # Get selected repository
    # --------------------------------------------------

    selected_repository = repositories[
        choice - 1
    ]

    repository_name = (
        selected_repository.name
    )

    repository_path = (
        selected_repository
    )

    # --------------------------------------------------
    # Repository ID
    # --------------------------------------------------

    repository_id = repository_name

    # --------------------------------------------------
    # Display selection
    # --------------------------------------------------

    print()

    print(
        f"Selected repository : "
        f"{repository_name}"
    )

    print(
        f"Repository ID       : "
        f"{repository_id}"
    )

    print(
        f"Repository path     : "
        f"{repository_path}"
    )

    # --------------------------------------------------
    # Start indexing
    # --------------------------------------------------

    index_repository(
        repository_path,
        repository_id,
    )
