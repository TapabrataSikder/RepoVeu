from urllib.parse import urlparse

def validate_github_url(url):
    """
    Validate a GitHub repository URL.

    Supported formats:
    https://github.com/owner/repository
    https://github.com/owner/repository.git
    https://github.com/owner/repository/tree/branch
    https://github.com/owner/repository/tree/branch/path
    """
    # Check that input is a string
    if not isinstance(url, str):
        return {
            "valid": False,
            "owner": None,
            "repository": None,
            "branch": None,
            "path": None,
            "error": "URL must be a string"
        }

    url = url.strip()

    if not url:
        return {
            "valid": False,
            "owner": None,
            "repository": None,
            "branch": None,
            "path": None,
            "error": "URL cannot be empty"
        }

    parsed_url = urlparse(url)

    # Check protocol
    if parsed_url.scheme != "https":
        return {
            "valid": False,
            "owner": None,
            "repository": None,
            "branch": None,
            "path": None,
            "error": "URL must use HTTPS"
        }

    # Check domain
    if parsed_url.netloc.lower() != "github.com":
        return {
            "valid": False,
            "owner": None,
            "repository": None,
            "branch": None,
            "path": None,
            "error": "URL must be a GitHub URL"
        }

    # Split GitHub path
    parts = [
        part
        for part in parsed_url.path.strip("/").split("/")
        if part
    ]

    # Minimum required:
    # github.com/<owner>/<repository>
    if len(parts) < 2:
        return {
            "valid": False,
            "owner": None,
            "repository": None,
            "branch": None,
            "path": None,
            "error": "URL must contain owner and repository"
        }

    owner = parts[0]
    repository = parts[1]

    # Remove .git suffix if present
    if repository.endswith(".git"):
        repository = repository[:-4]

    # Owner and repository names must be non-empty
    if not owner or not repository:
        return {
            "valid": False,
            "owner": None,
            "repository": None,
            "branch": None,
            "path": None,
            "error": "Owner and repository cannot be empty"
        }

    branch = None
    repository_path = None

    # --------------------------------------------------
    # REPOSITORY ROOT
    # --------------------------------------------------
    if len(parts) == 2:
        pass

    # --------------------------------------------------
    # TREE URL
    # --------------------------------------------------
    elif parts[2] == "tree":
        if len(parts) < 4:
            return {
                "valid": False,
                "owner": None,
                "repository": None,
                "branch": None,
                "path": None,
                "error": "Tree URL must contain a branch name"
            }

        branch = parts[3]

        if not branch:
            return {
                "valid": False,
                "owner": None,
                "repository": None,
                "branch": None,
                "path": None,
                "error": "Branch name cannot be empty"
            }

        # Everything after the branch is the repository path
        if len(parts) > 4:
            repository_path = "/".join(parts[4:])

    # --------------------------------------------------
    # BLOB URL
    # --------------------------------------------------
    elif parts[2] == "blob":
        if len(parts) < 4:
            return {
                "valid": False,
                "owner": None,
                "repository": None,
                "branch": None,
                "path": None,
                "error": "Blob URL must contain a branch name"
            }

        branch = parts[3]

        if not branch:
            return {
                "valid": False,
                "owner": None,
                "repository": None,
                "branch": None,
                "path": None,
                "error": "Branch name cannot be empty"
            }

        if len(parts) > 4:
            repository_path = "/".join(parts[4:])

    # --------------------------------------------------
    # UNSUPPORTED GITHUB PATH
    # --------------------------------------------------
    else:
        return {
            "valid": False,
            "owner": None,
            "repository": None,
            "branch": None,
            "path": None,
            "error": (
                "Unsupported GitHub URL. "
                "Use a repository, tree, or blob URL."
            )
        }

    return {
        "valid": True,
        "owner": owner,
        "repository": repository,
        "branch": branch,
        "path": repository_path,
        "error": None
    }