import requests


def check_repository_exists(owner, repository):
    """
    Check whether a GitHub repository exists.
    Args:
        owner (str): GitHub username or organization.
        repository (str): Repository name.
    Returns:
        dict: Result of the repository check.
    """

    # Github API URL for the repository
    url = f"https://api.github.com/repos/{owner}/{repository}"

    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        return {
            "exists": True,
            "owner": owner,
            "repository": repository,
            "error": None
        }

    if response.status_code == 404:
        return {
            "exists": False,
            "owner": owner,
            "repository": repository,
            "error": "Repository not found"
        }

    return {
        "exists": False,
        "owner": owner,
        "repository": repository,
        "error": f"GitHub API returned status {response.status_code}"
    }