from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ingestion.url_validator import validate_github_url
from app.ingestion.github_client import check_repository_exists
from app.ingestion.repository_loader import clone_repository

from app.vectorstore.index_repository import index_repository
from app.vectorstore.chroma_store import count_repository_chunks

from app.rag.pipeline import ask_repository

from app.repository.repository_manager import (
    get_repository_path,
    build_repository_tree,
)


# ==================================================
# FASTAPI APPLICATION
# ==================================================

app = FastAPI(
    title="RepoVeu",
    description="AI Software Engineering Assistant",
    version="1.0.0",
)


# ==================================================
# CORS
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# LANGUAGE DETECTION FOR FILE VIEWER
# ==================================================

LANGUAGE_BY_EXTENSION = {
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
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".rb": "ruby",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".md": "markdown",
    ".txt": "text",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".xml": "xml",
    ".sql": "sql",
    ".sh": "shell",
    ".bat": "batch",
    ".ps1": "powershell",
    ".env": "dotenv",
}


# ==================================================
# HEALTH CHECK
# ==================================================

@app.get("/")
def root():
    return {
        "success": True,
        "message": (
            "AI Software Engineering Assistant "
            "backend is running."
        ),
    }


# ==================================================
# VALIDATE REPOSITORY
# ==================================================

@app.post("/api/analyze")
def analyze_repository(data: dict):
    print()
    print("=" * 60)
    print("REPOSITORY VALIDATION")
    print("=" * 60)

    url = data.get("url")

    print("URL:", url)

    # --------------------------------------------------
    # STEP 1: VALIDATE URL
    # --------------------------------------------------

    validation = validate_github_url(url)

    if not validation["valid"]:
        print(
            "URL validation failed:",
            validation["error"],
        )

        return {
            "success": False,
            "stage": "url_validation",
            "error": validation["error"],
        }

    owner = validation["owner"]
    repository = validation["repository"]
    branch = validation.get("branch")
    selected_path = validation.get("path")

    print("Owner:", owner)
    print("Repository:", repository)
    print("Branch:", branch)
    print("Path:", selected_path)

    # --------------------------------------------------
    # STEP 2: CHECK GITHUB
    # --------------------------------------------------

    repository_check = check_repository_exists(
        owner,
        repository,
    )

    if not repository_check["exists"]:
        print(
            "GitHub repository check failed:",
            repository_check["error"],
        )

        return {
            "success": False,
            "stage": "github_check",
            "error": repository_check["error"],
        }

    # --------------------------------------------------
    # STEP 3: REPOSITORY ID
    # --------------------------------------------------

    repository_id = f"{owner}_{repository}"

    print("Repository ID:", repository_id)

    return {
        "success": True,
        "message": "Repository URL is valid.",
        "owner": owner,
        "repository": repository,
        "branch": branch,
        "path": selected_path,
        "repository_id": repository_id,
    }


# ==================================================
# CHECK LOCAL REPOSITORY STATUS
# ==================================================

@app.post("/api/repository/status")
def repository_status(data: dict):
    url = data.get("url")

    validation = validate_github_url(url)

    if not validation["valid"]:
        return {
            "success": False,
            "error": validation["error"],
        }

    owner = validation["owner"]
    repository = validation["repository"]
    repository_id = f"{owner}_{repository}"

    project_root = Path(__file__).resolve().parent.parent
    local_repository_path = (
        project_root
        / "data"
        / "repositories"
        / repository_id
    )

    indexed_chunks = count_repository_chunks(
        repository_id
    )

    return {
        "success": True,
        "repository_id": repository_id,
        "already_downloaded": local_repository_path.is_dir(),
        "indexed_chunks": indexed_chunks,
        "ready": (
            local_repository_path.is_dir()
            and indexed_chunks > 0
        ),
    }


# ==================================================
# DOWNLOAD + INDEX REPOSITORY
# ==================================================

@app.post("/api/repository/download")
def download_repository(data: dict):
    print()
    print("=" * 60)
    print("DOWNLOAD + INDEX REQUEST")
    print("=" * 60)

    # --------------------------------------------------
    # STEP 1: READ URL
    # --------------------------------------------------

    url = data.get("url")

    print("URL:", url)

    if not url:
        return {
            "success": False,
            "stage": "input",
            "error": "GitHub repository URL is required.",
        }

    # --------------------------------------------------
    # STEP 2: VALIDATE URL
    # --------------------------------------------------

    print()
    print("[1/5] Validating GitHub URL...")

    validation = validate_github_url(url)

    if not validation["valid"]:
        print(
            "URL validation failed:",
            validation["error"],
        )

        return {
            "success": False,
            "stage": "url_validation",
            "error": validation["error"],
        }

    owner = validation["owner"]
    repository = validation["repository"]
    branch = validation.get("branch")
    selected_path = validation.get("path")

    print("Owner:", owner)
    print("Repository:", repository)
    print("Branch:", branch)
    print("Path:", selected_path)

    # --------------------------------------------------
    # STEP 3: CHECK GITHUB
    # --------------------------------------------------

    print()
    print("[2/5] Checking GitHub repository...")

    repository_check = check_repository_exists(
        owner,
        repository,
    )

    if not repository_check["exists"]:
        print("GitHub repository does not exist.")

        return {
            "success": False,
            "stage": "github_check",
            "error": repository_check["error"],
        }

    print("GitHub repository exists.")

    # --------------------------------------------------
    # STEP 4: CREATE REPOSITORY ID
    # --------------------------------------------------

    repository_id = f"{owner}_{repository}"

    print("Repository ID:", repository_id)

    # --------------------------------------------------
    # STEP 5: DOWNLOAD / LOAD
    # --------------------------------------------------

    print()
    print("[3/5] Downloading / loading repository...")

    try:
        clone_result = clone_repository(
            owner,
            repository,
            branch,
            selected_path,
        )
    except Exception as error:
        print("Clone error:", error)

        return {
            "success": False,
            "stage": "download",
            "error": (
                "Failed to download repository: "
                f"{str(error)}"
            ),
        }

    if not clone_result:
        return {
            "success": False,
            "stage": "download",
            "error": (
                "Repository loader returned "
                "no result."
            ),
        }

    local_repository_path = clone_result.get("path")
    selected_local_path = clone_result.get("selected_path")
    clone_error = clone_result.get("error")
    cloned = clone_result.get("cloned")

    if not local_repository_path:
        return {
            "success": False,
            "stage": "download",
            "error": (
                clone_error
                or "Repository path was not returned."
            ),
        }

    print()
    print("Repository path ready.")
    print("Local repository:", local_repository_path)

    if selected_local_path:
        print("Selected path:", selected_local_path)

    # ==================================================
    # REPOSITORY ALREADY EXISTS
    # ==================================================

    if not cloned:
        if clone_error == "Repository already exists locally":
            print()
            print("=" * 60)
            print("REPOSITORY ALREADY DOWNLOADED")
            print("=" * 60)

            print("Repository ID:", repository_id)
            print("Local repository:", local_repository_path)

            if selected_local_path:
                print("Selected path:", selected_local_path)

            # --------------------------------------------------
            # CHECK INDEX
            # --------------------------------------------------

            print()
            print("[4/5] Checking repository index...")

            indexed_count = count_repository_chunks(
                repository_id
            )

            print("Indexed chunks:", indexed_count)

            if indexed_count > 0:
                print()
                print("=" * 60)
                print("REPOSITORY READY")
                print("=" * 60)

                return {
                    "success": True,
                    "already_downloaded": True,
                    "already_indexed": True,
                    "ready": True,
                    "message": (
                        "Repository is already "
                        "downloaded and indexed."
                    ),
                    "owner": owner,
                    "repository": repository,
                    "repository_id": repository_id,
                    "branch": branch,
                    "path": selected_path,
                    "local_path": str(
                        local_repository_path
                    ),
                    "selected_local_path": (
                        str(selected_local_path)
                        if selected_local_path
                        else None
                    ),
                    "indexed_chunks": indexed_count,
                }

            # --------------------------------------------------
            # INDEX EXISTING REPOSITORY
            # --------------------------------------------------

            print("Repository is not indexed.")
            print("Starting indexing...")

            print()
            print("[5/5] Indexing repository...")

            try:
                indexing_result = index_repository(
                    local_repository_path,
                    repository_id,
                    branch=branch,
                    selected_path=selected_path,
                )
            except Exception as error:
                print("Indexing error:", error)

                return {
                    "success": False,
                    "stage": "indexing",
                    "already_downloaded": True,
                    "already_indexed": False,
                    "repository_id": repository_id,
                    "error": (
                        "Repository downloaded, "
                        "but indexing failed: "
                        f"{str(error)}"
                    ),
                }

            if not indexing_result.get("success"):
                return {
                    "success": False,
                    "stage": "indexing",
                    "already_downloaded": True,
                    "already_indexed": False,
                    "repository_id": repository_id,
                    "error": indexing_result.get(
                        "error",
                        "Indexing failed.",
                    ),
                }

            indexed_count = indexing_result.get(
                "indexed_count",
                0,
            )

            print()
            print("=" * 60)
            print("DOWNLOAD + INDEXING COMPLETE")
            print("=" * 60)

            return {
                "success": True,
                "already_downloaded": True,
                "already_indexed": True,
                "ready": True,
                "message": (
                    "Repository was already downloaded "
                    "and has now been indexed."
                ),
                "owner": owner,
                "repository": repository,
                "repository_id": repository_id,
                "branch": branch,
                "path": selected_path,
                "local_path": str(
                    local_repository_path
                ),
                "selected_local_path": (
                    str(selected_local_path)
                    if selected_local_path
                    else None
                ),
                "indexed_chunks": indexed_count,
            }

        # --------------------------------------------------
        # DOWNLOAD FAILED
        # --------------------------------------------------

        print(
            "Repository download failed:",
            clone_error,
        )

        return {
            "success": False,
            "stage": "download",
            "error": (
                clone_error
                or "Repository download failed."
            ),
        }

    # ==================================================
    # NEW REPOSITORY
    # ==================================================

    print()
    print("=" * 60)
    print("NEW REPOSITORY DOWNLOADED")
    print("=" * 60)

    print("Repository ID:", repository_id)
    print("Local repository:", local_repository_path)

    if selected_local_path:
        print("Selected path:", selected_local_path)

    # --------------------------------------------------
    # INDEX NEW REPOSITORY
    # --------------------------------------------------

    print()
    print("[4/5] Indexing repository...")

    try:
        indexing_result = index_repository(
            local_repository_path,
            repository_id,
            branch=branch,
            selected_path=selected_path,
        )
    except Exception as error:
        print("Indexing error:", error)

        return {
            "success": False,
            "stage": "indexing",
            "already_downloaded": False,
            "already_indexed": False,
            "owner": owner,
            "repository": repository,
            "repository_id": repository_id,
            "error": (
                "Repository downloaded successfully, "
                "but indexing failed: "
                f"{str(error)}"
            ),
        }

    if not indexing_result.get("success"):
        return {
            "success": False,
            "stage": "indexing",
            "already_downloaded": False,
            "already_indexed": False,
            "owner": owner,
            "repository": repository,
            "repository_id": repository_id,
            "error": (
                "Repository downloaded successfully, "
                "but indexing failed: "
                f"{indexing_result.get('error', 'Unknown error')}"
            ),
        }

    indexed_count = indexing_result.get(
        "indexed_count",
        0,
    )

    print()
    print("=" * 60)
    print("DOWNLOAD + INDEXING COMPLETE")
    print("=" * 60)

    print("Repository ID:", repository_id)
    print("Branch:", branch)
    print("Selected path:", selected_path)
    print("Indexed chunks:", indexed_count)
    print("Repository is READY for AI analysis.")

    return {
        "success": True,
        "already_downloaded": False,
        "already_indexed": True,
        "ready": True,
        "message": (
            "Repository successfully "
            "downloaded and indexed."
        ),
        "owner": owner,
        "repository": repository,
        "repository_id": repository_id,
        "branch": branch,
        "path": selected_path,
        "local_path": str(
            local_repository_path
        ),
        "selected_local_path": (
            str(selected_local_path)
            if selected_local_path
            else None
        ),
        "indexed_chunks": indexed_count,
    }


# ==================================================
# REPOSITORY FILE TREE
# ==================================================

@app.get("/api/repository/{repository_id}/files")
def get_repository_files(
    repository_id: str,
    path: str | None = None,
):
    print()
    print("=" * 60)
    print("REPOSITORY FILE TREE REQUEST")
    print("=" * 60)

    print("Repository ID:", repository_id)
    print("Selected path:", path)

    if not repository_id:
        return {
            "success": False,
            "error": "Repository ID is required.",
        }

    try:
        repository_path = get_repository_path(
            repository_id
        )
    except FileNotFoundError as error:
        print("Repository not found:", error)

        return {
            "success": False,
            "error": str(error),
        }

    print(
        "Resolved repository path:",
        repository_path,
    )

    tree_path = repository_path

    if path:
        normalized_path = path.strip("/\\")
        relative_path = Path(normalized_path)

        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or ".git" in relative_path.parts
        ):
            return {
                "success": False,
                "error": "Invalid repository path.",
            }

        tree_path = (
            repository_path / relative_path
        )

        try:
            tree_path = tree_path.resolve()
            repository_root = repository_path.resolve()

            if repository_root not in (
                tree_path,
                *tree_path.parents,
            ):
                return {
                    "success": False,
                    "error": "Invalid repository path.",
                }

        except Exception as error:
            print("Path resolution error:", error)

            return {
                "success": False,
                "error": "Invalid repository path.",
            }

        if not tree_path.exists():
            return {
                "success": False,
                "error": (
                    "Selected repository path "
                    f"does not exist: {path}"
                ),
            }

        if not tree_path.is_dir():
            return {
                "success": False,
                "error": (
                    "Selected repository path "
                    f"is not a directory: {path}"
                ),
            }

    print("Tree path:", tree_path)

    try:
        tree = build_repository_tree(
            tree_path
        )
    except Exception as error:
        print("Tree generation error:", error)

        return {
            "success": False,
            "error": (
                "Failed to read repository files: "
                f"{str(error)}"
            ),
        }

    print()
    print("Repository tree generated.")
    print("Repository path:", repository_path)
    print("Tree path:", tree_path)
    print("Top-level items:", len(tree))

    return {
        "success": True,
        "repository_id": repository_id,
        "repository_path": str(repository_path),
        "selected_path": path,
        "tree_path": str(tree_path),
        "tree": tree,
    }


# ==================================================
# READ REPOSITORY FILE
# ==================================================

@app.get("/api/repository/{repository_id}/file")
def get_repository_file(
    repository_id: str,
    path: str,
    base_path: str | None = None,
):
    print()
    print("=" * 60)
    print("REPOSITORY FILE REQUEST")
    print("=" * 60)

    print("Repository ID:", repository_id)
    print("File path:", path)
    print("Base path:", base_path)

    if not repository_id:
        return {
            "success": False,
            "error": "Repository ID is required.",
        }

    if not path or not path.strip():
        return {
            "success": False,
            "error": "File path is required.",
        }

    try:
        repository_path = get_repository_path(
            repository_id
        )
    except FileNotFoundError as error:
        print("Repository not found:", error)

        return {
            "success": False,
            "error": str(error),
        }

    repository_path = Path(
        repository_path
    ).resolve()

    relative_file_path = Path(path)

    if (
        relative_file_path.is_absolute()
        or ".." in relative_file_path.parts
        or ".git" in relative_file_path.parts
    ):
        return {
            "success": False,
            "error": "Invalid file path.",
        }

    file_root = repository_path

    if base_path:
        relative_base_path = Path(
            base_path
        )

        if (
            relative_base_path.is_absolute()
            or ".." in relative_base_path.parts
            or ".git" in relative_base_path.parts
        ):
            return {
                "success": False,
                "error": "Invalid base path.",
            }

        file_root = (
            repository_path / relative_base_path
        ).resolve()

        if (
            file_root != repository_path
            and repository_path not in file_root.parents
        ):
            return {
                "success": False,
                "error": "Invalid base path.",
            }

        if not file_root.exists() or not file_root.is_dir():
            return {
                "success": False,
                "error": (
                    "Selected base path does not exist."
                ),
            }

    file_path = (
        file_root / relative_file_path
    ).resolve()

    if (
        file_path != repository_path
        and repository_path not in file_path.parents
    ):
        return {
            "success": False,
            "error": "Invalid file path.",
        }

    if (
        base_path
        and file_path != file_root
        and file_root not in file_path.parents
    ):
        return {
            "success": False,
            "error": "File is outside the selected path.",
        }

    if ".git" in file_path.relative_to(
        repository_path
    ).parts:
        return {
            "success": False,
            "error": "Access to .git files is not allowed.",
        }

    if not file_path.exists():
        print("File does not exist:", file_path)

        return {
            "success": False,
            "error": f"File does not exist: {path}",
        }

    if not file_path.is_file():
        return {
            "success": False,
            "error": f"Path is not a file: {path}",
        }

    MAX_FILE_SIZE = 2 * 1024 * 1024

    file_size = file_path.stat().st_size

    if file_size > MAX_FILE_SIZE:
        return {
            "success": False,
            "error": (
                "File is too large to display. "
                "Maximum supported size is 2 MB."
            ),
        }

    try:
        with file_path.open(
            "r",
            encoding="utf-8",
            errors="replace",
            newline="",
        ) as file:
            content = file.read()

    except Exception as error:
        print("File read error:", error)

        return {
            "success": False,
            "error": f"Failed to read file: {str(error)}",
        }

    extension = file_path.suffix.lower()

    language = LANGUAGE_BY_EXTENSION.get(
        extension,
        "text",
    )

    try:
        display_path = file_path.relative_to(
            repository_path
        ).as_posix()
    except ValueError:
        display_path = path

    print()
    print("File loaded successfully.")
    print("File:", display_path)
    print("Language:", language)
    print("Size:", file_size, "bytes")
    print("Characters:", len(content))

    return {
        "success": True,
        "repository_id": repository_id,
        "path": display_path,
        "language": language,
        "size": file_size,
        "content": content,
    }


# ==================================================
# REPOSITORY INSIGHTS
# ==================================================

@app.post("/api/repository/insights")
def repository_insights(data: dict):
    print()
    print("=" * 60)
    print("REPOSITORY INSIGHT REQUEST")
    print("=" * 60)

    repository_id = data.get("repository_id")
    question = data.get("question")

    print("Repository ID:", repository_id)
    print("Question:", question)

    # --------------------------------------------------
    # VALIDATE REPOSITORY
    # --------------------------------------------------

    if not repository_id:
        return {
            "success": False,
            "stage": "repository",
            "error": (
                "Repository ID is required. "
                "Please download the repository first."
            ),
        }

    # --------------------------------------------------
    # VALIDATE QUESTION
    # --------------------------------------------------

    if not question or not question.strip():
        return {
            "success": False,
            "stage": "question",
            "error": "Question is required.",
        }

    question = question.strip()

    # --------------------------------------------------
    # CHECK INDEX
    # --------------------------------------------------

    print()
    print("Checking repository index...")

    try:
        indexed_count = count_repository_chunks(
            repository_id
        )
    except Exception as error:
        print("Index check error:", error)

        return {
            "success": False,
            "stage": "index_check",
            "error": (
                "Could not check repository index: "
                f"{str(error)}"
            ),
        }

    print("Indexed chunks:", indexed_count)

    if indexed_count <= 0:
        return {
            "success": False,
            "stage": "index_check",
            "error": (
                "Repository has not been indexed yet. "
                "Please download the repository first."
            ),
        }

    # --------------------------------------------------
    # RUN RAG
    # --------------------------------------------------

    print()
    print("Repository is ready.")
    print("Starting RAG pipeline...")

    try:
        answer = ask_repository(
            question=question,
            repository_id=repository_id,
        )
    except Exception as error:
        print()
        print("RAG error:", error)

        return {
            "success": False,
            "stage": "rag",
            "repository_id": repository_id,
            "error": (
                "Failed to generate repository insights: "
                f"{str(error)}"
            ),
        }

    # --------------------------------------------------
    # RETURN ANSWER
    # --------------------------------------------------

    print()
    print("=" * 60)
    print("INSIGHT GENERATION COMPLETE")
    print("=" * 60)

    print(
        "Answer length:",
        len(answer) if answer else 0,
    )

    return {
        "success": True,
        "repository_id": repository_id,
        "question": question,
        "indexed_chunks": indexed_count,
        "answer": answer,
    }
