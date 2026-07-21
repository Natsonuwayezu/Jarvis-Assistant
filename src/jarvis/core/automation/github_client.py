# src/jarvis/core/automation/github_client.py
#
# WHY THIS FILE EXISTS:
# Lets JARVIS check a GitHub repo's issues and pull requests, and (with
# your explicit confirmation) create a new issue — e.g. "what issues
# are open on my Jarvis-Assistant repo?" or "create an issue about the
# login bug."
#
# WHY urllib.request INSTEAD OF A NEW LIBRARY (like PyGithub or
# requests): GitHub's REST API is simple enough to call directly with
# Python's built-in urllib, which means ZERO new dependencies — nothing
# new to pip install, matching the "no more things to download" scope
# for this round of additions.
#
# AUTHENTICATION: reading PUBLIC repos' issues/PRs works without any
# token (just rate-limited more strictly — 60 requests/hour instead of
# 5,000). Creating an issue, or reading a PRIVATE repo, requires a
# GITHUB_TOKEN in your .env file. If it's missing, read-only calls on
# public repos still work; anything requiring auth reports clearly that
# a token is needed, rather than failing with a confusing raw error.

import json
import os
import urllib.request
import urllib.error

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

_API_BASE = "https://api.github.com"

# GitHub's API requires a User-Agent header on every request, or it
# rejects the request outright — this isn't optional.
_USER_AGENT = "JARVIS-Personal-Assistant"


class GitHubError(Exception):
    """Raised when a GitHub API request fails for any reason."""


def _request(method: str, path: str, body: dict = None, require_token: bool = False) -> dict:
    """
    Internal helper: make one authenticated (if a token is available)
    request to the GitHub API and return the parsed JSON response.

    Args:
        method: HTTP method, e.g. "GET" or "POST".
        path: API path starting with "/", e.g. "/repos/owner/repo/issues".
        body: For POST requests, a dict to send as the JSON request body.
        require_token: If True, raises GitHubError immediately when no
            GITHUB_TOKEN is configured, rather than attempting the
            request and getting a confusing 403/401 from GitHub itself.

    Returns:
        The parsed JSON response (a dict, or a list for endpoints that
        return arrays — callers know which shape to expect).

    Raises:
        GitHubError: for a missing required token, a network failure,
            or any non-2xx response from GitHub.
    """
    token = os.environ.get("GITHUB_TOKEN")

    if require_token and not token:
        raise GitHubError(
            "This action needs a GitHub token. Add GITHUB_TOKEN to your .env file — "
            "create one at https://github.com/settings/tokens"
        )

    url = _API_BASE + path
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(body).encode("utf-8") if body is not None else None

    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        # HTTPError bodies from GitHub are themselves JSON with a
        # "message" field explaining what went wrong (e.g. "Not Found",
        # "Bad credentials") — surfacing that is far more useful than a
        # generic "request failed."
        try:
            error_body = json.loads(error.read().decode("utf-8"))
            github_message = error_body.get("message", str(error))
        except (json.JSONDecodeError, AttributeError):
            github_message = str(error)

        logger.warning("GitHub API error (%d): %s", error.code, github_message)
        raise GitHubError(f"GitHub API error: {github_message}")

    except urllib.error.URLError as error:
        logger.error("GitHub network error: %s", error)
        raise GitHubError(f"Couldn't reach GitHub — check your internet connection: {error}")


def get_repo_info(repo: str) -> str:
    """
    Get basic information about a repository.

    Args:
        repo: Repository in "owner/name" format, e.g. "octocat/Hello-World".

    Returns:
        A short human-readable summary of the repo.
    """
    data = _request("GET", f"/repos/{repo}")
    return (
        f"{data['full_name']}: {data.get('description') or '(no description)'}\n"
        f"⭐ {data['stargazers_count']} stars | 🍴 {data['forks_count']} forks | "
        f"Open issues: {data['open_issues_count']}\n"
        f"Default branch: {data['default_branch']} | "
        f"{'Private' if data['private'] else 'Public'}"
    )


def list_issues(repo: str, state: str = "open") -> str:
    """
    List issues on a repository (excludes pull requests, which
    GitHub's API otherwise returns mixed in with issues).

    Args:
        repo: Repository in "owner/name" format.
        state: "open", "closed", or "all".

    Returns:
        A human-readable, newline-separated list of issues.
    """
    items = _request("GET", f"/repos/{repo}/issues?state={state}&per_page=20")

    # GitHub's /issues endpoint also returns pull requests (a PR IS an
    # issue, internally, on GitHub) — items that have a "pull_request"
    # key are PRs, not real issues, so we filter those out here.
    issues_only = [item for item in items if "pull_request" not in item]

    if not issues_only:
        return f"No {state} issues found on {repo}."

    lines = [f"#{item['number']}: {item['title']}" for item in issues_only]
    return f"{state.capitalize()} issues on {repo}:\n" + "\n".join(lines)


def list_pull_requests(repo: str, state: str = "open") -> str:
    """
    List pull requests on a repository.

    Args:
        repo: Repository in "owner/name" format.
        state: "open", "closed", or "all".

    Returns:
        A human-readable, newline-separated list of pull requests.
    """
    items = _request("GET", f"/repos/{repo}/pulls?state={state}&per_page=20")

    if not items:
        return f"No {state} pull requests found on {repo}."

    lines = [f"#{item['number']}: {item['title']}" for item in items]
    return f"{state.capitalize()} pull requests on {repo}:\n" + "\n".join(lines)


def create_issue(repo: str, title: str, body: str = "") -> str:
    """
    Create a new issue on a repository. REQUIRES a GITHUB_TOKEN — this
    is a real, visible, hard-to-fully-undo external action (an issue
    can be closed but not deleted through the API), which is why the
    caller (tools.py) gates this behind explicit user confirmation
    before ever reaching this function.

    Args:
        repo: Repository in "owner/name" format.
        title: The issue's title.
        body: The issue's description text.

    Returns:
        A confirmation message including a link to the new issue.
    """
    result = _request(
        "POST", f"/repos/{repo}/issues", body={"title": title, "body": body}, require_token=True
    )
    logger.info("Created issue #%d on %s: %s", result["number"], repo, title)
    return f"Created issue #{result['number']} on {repo}: {result['html_url']}"
