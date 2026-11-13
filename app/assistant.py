from app.ingestion.url_validator import validate_github_url
from app.ingestion.github_client import check_repository_exists
from app.ingestion.repository_loader import clone_repository
from app.vectorstore.index_repository import index_repository
from app.vectorstore.chroma_store import count_repository_chunks
from app.rag.pipeline import ask_repository


def process_repository_question(url, question):

    print()
    print("=" * 60)
    print("AI SOFTWARE ENGINEERING ASSISTANT")
    print("=" * 60)

    # ==================================================
    # 1. Validate URL
    # ==================================================

    print()
    print("[1/7] Validating GitHub URL...")

    validation = validate_github_url(url)

    if not validation["valid"]:

        print("URL validation failed.")

        return {
            "success": False,
            "stage": "url_validation",
            "error": validation["error"]
        }

    owner = validation["owner"]
    repository = validation["repository"]
    branch = validation.get("branch")
    selected_path = validation.get("path")

    repository_id = f"{owner}_{repository}"

    print(
        f"Owner      : {owner}"
    )

    print(
        f"Repository : {repository}"
    )

    print(
        f"Branch     : {branch}"
    )

    print(
        f"Path       : {selected_path}"
    )

    # ==================================================
    # 2. Check GitHub repository
    # ==================================================

    print()
    print("[2/7] Checking GitHub repository...")

    repository_check = check_repository_exists(
        owner,
        repository
    )

    if not repository_check["exists"]:

        print(
            "GitHub repository check failed."
        )

        return {
            "success": False,
            "stage": "github_check",
            "error": repository_check["error"]
        }

    print(
        "GitHub repository exists."
    )

    # ==================================================
    # 3. Check / download repository
    # ==================================================

    print()
    print(
        "[3/7] Downloading / loading repository..."
    )

    clone_result = clone_repository(
        owner,
        repository,
        branch=branch,
        repository_path=selected_path
    )

    if not clone_result:

        return {
            "success": False,
            "stage": "download",
            "error": (
                "Repository loader returned "
                "no result."
            )
        }

    local_repository_path = (
        clone_result.get("path")
    )

    indexed_path = (
        clone_result.get("selected_path")
    )

    if not local_repository_path:

        print(
            "Repository download failed."
        )

        return {
            "success": False,
            "stage": "download",
            "error": clone_result.get(
                "error",
                "Failed to download repository."
            )
        }

    if not indexed_path:

        return {
            "success": False,
            "stage": "download",
            "error": (
                "Selected repository path "
                "could not be resolved."
            )
        }

    print(
        "Repository path ready."
    )

    print(
        "Local repository:",
        local_repository_path
    )

    print(
        "Selected path:",
        indexed_path
    )

    # ==================================================
    # 4. Check whether repository is already indexed
    # ==================================================

    print()
    print(
        "[4/7] Checking repository index..."
    )

    indexed_count = count_repository_chunks(
        repository_id
    )

    if indexed_count > 0:

        print()
        print("=" * 50)
        print("REPOSITORY READY")
        print("=" * 50)

        print(
            f"Repository    : {repository_id}"
        )

        print(
            f"Branch        : {branch}"
        )

        print(
            f"Path          : {selected_path}"
        )

        print(
            f"Indexed chunks: {indexed_count}"
        )

    # ==================================================
    # 5. Index repository if necessary
    # ==================================================

    else:

        print()
        print("=" * 50)
        print("REPOSITORY INDEXING")
        print("=" * 50)

        print(
            f"Repository : {repository_id}"
        )

        print(
            f"Branch     : {branch}"
        )

        print(
            f"Path       : {selected_path}"
        )

        print(
            f"Local path : {indexed_path}"
        )

        indexing_result = index_repository(
            indexed_path,
            repository_id
        )

        if not indexing_result.get("success"):

            print(
                "Repository indexing failed."
            )

            return {
                "success": False,
                "stage": "indexing",
                "owner": owner,
                "repository": repository,
                "repository_id": repository_id,
                "branch": branch,
                "path": selected_path,
                "error": indexing_result.get(
                    "error",
                    "Repository indexing failed."
                )
            }

        # ==================================================
        # VERIFY INDEX
        # ==================================================

        print()
        print(
            "Verifying repository index..."
        )

        indexed_count = count_repository_chunks(
            repository_id
        )

        print(
            f"Verified indexed chunks: "
            f"{indexed_count}"
        )

        if indexed_count == 0:

            print(
                "Repository indexing completed "
                "but no chunks were found."
            )

            return {
                "success": False,
                "stage": "indexing",
                "owner": owner,
                "repository": repository,
                "repository_id": repository_id,
                "branch": branch,
                "path": selected_path,
                "error": (
                    "Repository was downloaded and "
                    "indexing completed, but no repository "
                    "chunks were available for retrieval."
                )
            }

        print()
        print(
            "Repository indexing completed successfully."
        )

    # ==================================================
    # 6. Ask RAG
    # ==================================================

    print()
    print("=" * 50)
    print("REPOSITORY INSIGHT REQUEST")
    print("=" * 50)

    print(
        f"Repository : {repository_id}"
    )

    print(
        f"Branch     : {branch}"
    )

    print(
        f"Path       : {selected_path}"
    )

    print(
        f"Question   : {question}"
    )

    print(
        f"Chunks     : {indexed_count}"
    )

    print()
    print(
        "[6/7] Sending question to RAG pipeline..."
    )

    try:

        answer = ask_repository(
            question=question,
            repository_id=repository_id
        )

    except Exception as error:

        print()
        print("=" * 50)
        print("RAG PIPELINE ERROR")
        print("=" * 50)

        print(
            f"Error type: {type(error).__name__}"
        )

        print(
            f"Error: {error}"
        )

        return {
            "success": False,
            "stage": "rag",
            "owner": owner,
            "repository": repository,
            "repository_id": repository_id,
            "branch": branch,
            "path": selected_path,
            "error": (
                "Failed to generate "
                "repository insights."
            )
        }

    # ==================================================
    # 7. Validate answer
    # ==================================================

    print()
    print(
        "[7/7] Validating Gemini answer..."
    )

    if answer is None:

        print(
            "ERROR: Gemini answer is None."
        )

        return {
            "success": False,
            "stage": "llm",
            "owner": owner,
            "repository": repository,
            "repository_id": repository_id,
            "branch": branch,
            "path": selected_path,
            "error": (
                "Gemini returned no answer."
            )
        }

    if not isinstance(answer, str):

        print(
            "ERROR: Gemini answer is not a string."
        )

        print(
            f"Answer type: "
            f"{type(answer).__name__}"
        )

        return {
            "success": False,
            "stage": "llm",
            "owner": owner,
            "repository": repository,
            "repository_id": repository_id,
            "branch": branch,
            "path": selected_path,
            "error": (
                "Gemini returned an invalid answer."
            )
        }

    answer = answer.strip()

    print(
        repr(answer[:200])
    )

    if not answer:

        print(
            "ERROR: Gemini returned an empty answer."
        )

        return {
            "success": False,
            "stage": "llm",
            "owner": owner,
            "repository": repository,
            "repository_id": repository_id,
            "branch": branch,
            "path": selected_path,
            "error": (
                "Gemini returned an empty answer. "
                "Please try again."
            )
        }

    print()
    print("=" * 50)
    print("ANSWER READY")
    print("=" * 50)

    print(
        f"Answer length: {len(answer)} characters"
    )

    print()
    print(
        "Returning response to FastAPI..."
    )

    # ==================================================
    # FINAL RESPONSE
    # ==================================================

    result = {
        "success": True,
        "owner": owner,
        "repository": repository,
        "repository_id": repository_id,
        "branch": branch,
        "path": selected_path,
        "indexed_chunks": indexed_count,
        "answer": answer
    }

    print()
    print(
        "Backend response created successfully."
    )

    print(
        type(answer)
    )

    return result