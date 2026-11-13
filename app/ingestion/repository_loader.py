import subprocess
from pathlib import Path


def clone_repository(owner, repository, branch=None, repository_path=None):
    """
    Clone a GitHub repository and optionally select a branch/path.
    """

    repo_url = f"https://github.com/{owner}/{repository}.git"

    project_root = Path(__file__).resolve().parents[2]

    repositories_dir = (
        project_root
        / "data"
        / "repositories"
    )

    repositories_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    local_repository_path = (
        repositories_dir
        / f"{owner}_{repository}"
    )

    # ==================================================
    # EXISTING REPOSITORY
    # ==================================================

    if local_repository_path.exists():

        selected_path = local_repository_path

        if repository_path:

            selected_path = (
                local_repository_path
                / Path(repository_path)
            )

            if not selected_path.exists():

                return {
                    "cloned": False,
                    "path": str(local_repository_path),
                    "selected_path": None,
                    "error": (
                        f"Selected repository path does not exist: "
                        f"{repository_path}"
                    )
                }

        return {
            "cloned": False,
            "path": str(local_repository_path),
            "selected_path": str(selected_path),
            "branch": branch,
            "repository_path": repository_path,
            "error": (
                "Repository already exists locally"
            )
        }

    # ==================================================
    # BUILD GIT COMMAND
    # ==================================================

    command = [
        "git",
        "clone"
    ]

    if branch:

        command.extend([
            "--branch",
            branch,
            "--single-branch"
        ])

    command.extend([
        repo_url,
        str(local_repository_path)
    ])

    # ==================================================
    # CLONE REPOSITORY
    # ==================================================

    try:

        subprocess.run(
            command,
            check=True
        )

    except FileNotFoundError:

        return {
            "cloned": False,
            "path": None,
            "selected_path": None,
            "branch": branch,
            "repository_path": repository_path,
            "error": (
                "Git is not installed or "
                "not available in PATH"
            )
        }

    except subprocess.CalledProcessError:

        return {
            "cloned": False,
            "path": None,
            "selected_path": None,
            "branch": branch,
            "repository_path": repository_path,
            "error": (
                "Failed to clone repository"
            )
        }

    # ==================================================
    # SELECTED PATH
    # ==================================================

    selected_path = local_repository_path

    if repository_path:

        selected_path = (
            local_repository_path
            / Path(repository_path)
        )

        if not selected_path.exists():

            return {
                "cloned": True,
                "path": str(local_repository_path),
                "selected_path": None,
                "branch": branch,
                "repository_path": repository_path,
                "error": (
                    f"Selected repository path does not exist: "
                    f"{repository_path}"
                )
            }

    # ==================================================
    # SUCCESS
    # ==================================================

    return {
        "cloned": True,
        "path": str(local_repository_path),
        "selected_path": str(selected_path),
        "branch": branch,
        "repository_path": repository_path,
        "error": None
    }