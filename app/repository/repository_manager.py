# app/repository/repository_manager.py

from pathlib import Path


# ==================================================
# REPOSITORY STORAGE
# ==================================================

BASE_REPOSITORY_PATH = Path("data/repositories")


# ==================================================
# GET REPOSITORY PATH
# ==================================================

def get_repository_path(repository_id: str) -> Path:
    """
    Resolve a repository ID to its actual local repository path.

    Repository ID format:
        owner_repository

    Example:
        TababrataSikder_Python_Project

    Possible local path:
        data/repositories/Python_Project
    """

    if not repository_id:
        raise FileNotFoundError(
            "Repository ID is required."
        )

    base_path = BASE_REPOSITORY_PATH

    # --------------------------------------------------
    # Check repository storage directory
    # --------------------------------------------------

    if not base_path.exists():
        raise FileNotFoundError(
            f"Repository storage directory not found: {base_path}"
        )

    if not base_path.is_dir():
        raise FileNotFoundError(
            f"Repository storage path is not a directory: {base_path}"
        )

    # --------------------------------------------------
    # FIRST:
    # Check whether the complete repository ID
    # is used as the directory name
    # --------------------------------------------------

    direct_path = base_path / repository_id

    if direct_path.exists() and direct_path.is_dir():
        return direct_path

    # --------------------------------------------------
    # SECOND:
    # Extract repository name from owner_repository
    #
    # Example:
    # TababrataSikder_Python_Project
    #
    # owner      = TababrataSikder
    # repository = Python_Project
    # --------------------------------------------------

    if "_" in repository_id:

        owner, repository = repository_id.split("_", 1)

        repository_path = base_path / repository

        if repository_path.exists() and repository_path.is_dir():
            return repository_path

    # --------------------------------------------------
    # THIRD:
    # Search all repository directories
    # --------------------------------------------------

    repository_name = None

    if "_" in repository_id:
        repository_name = repository_id.split("_", 1)[1]

    try:
        directories = base_path.iterdir()
    except PermissionError:
        raise FileNotFoundError(
            f"Permission denied while reading repository storage: {base_path}"
        )

    for directory in directories:

        if not directory.is_dir():
            continue

        # Exact repository ID match
        if directory.name == repository_id:
            return directory

        # Repository name match
        if repository_name and directory.name == repository_name:
            return directory

    # --------------------------------------------------
    # NOT FOUND
    # --------------------------------------------------

    raise FileNotFoundError(
        f"Repository not found: {base_path / repository_id}"
    )


# ==================================================
# LIST REPOSITORIES
# ==================================================

def list_repositories():
    """
    Return all locally downloaded repositories.

    Each repository is returned as a dictionary containing:

        repository_id
        repository_name
        path
    """

    base_path = BASE_REPOSITORY_PATH

    # --------------------------------------------------
    # If repository storage does not exist
    # --------------------------------------------------

    if not base_path.exists():
        return []

    if not base_path.is_dir():
        return []

    repositories = []

    # --------------------------------------------------
    # Read repository directories
    # --------------------------------------------------

    try:
        directories = sorted(
            base_path.iterdir(),
            key=lambda item: item.name.lower()
        )
    except PermissionError:
        return []

    for directory in directories:

        # Ignore files
        if not directory.is_dir():
            continue

        # Ignore Git metadata
        if directory.name == ".git":
            continue

        repositories.append(
            {
                "repository_id": directory.name,
                "repository_name": directory.name,
                "path": str(directory)
            }
        )

    return repositories


# ==================================================
# BUILD REPOSITORY TREE
# ==================================================

def build_repository_tree(repository_path: Path):
    """
    Build a nested file/folder tree for a repository.

    Returns:

    [
        {
            "name": "app",
            "path": "app",
            "type": "directory",
            "children": [
                {
                    "name": "main.py",
                    "path": "app/main.py",
                    "type": "file"
                }
            ]
        }
    ]
    """

    repository_path = Path(repository_path)

    # --------------------------------------------------
    # Validate repository path
    # --------------------------------------------------

    if not repository_path.exists():
        raise FileNotFoundError(
            f"Repository path does not exist: {repository_path}"
        )

    if not repository_path.is_dir():
        raise FileNotFoundError(
            f"Repository path is not a directory: {repository_path}"
        )

    # --------------------------------------------------
    # Recursive tree builder
    # --------------------------------------------------

    def build_tree(current_path: Path):

        items = []

        try:
            children = sorted(
                current_path.iterdir(),
                key=lambda item: (
                    not item.is_dir(),
                    item.name.lower()
                )
            )

        except PermissionError:
            return items

        for item in children:

            # ------------------------------------------
            # Ignore Git metadata
            # ------------------------------------------

            if item.name == ".git":
                continue

            # ------------------------------------------
            # Directory
            # ------------------------------------------

            if item.is_dir():

                items.append(
                    {
                        "name": item.name,
                        "path": str(
                            item.relative_to(repository_path)
                        ).replace("\\", "/"),
                        "type": "directory",
                        "children": build_tree(item)
                    }
                )

            # ------------------------------------------
            # File
            # ------------------------------------------

            elif item.is_file():

                items.append(
                    {
                        "name": item.name,
                        "path": str(
                            item.relative_to(repository_path)
                        ).replace("\\", "/"),
                        "type": "file"
                    }
                )

        return items

    return build_tree(repository_path)