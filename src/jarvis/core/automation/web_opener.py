# src/jarvis/core/automation/web_opener.py
#
# WHY THIS FILE EXISTS:
# Opens websites in the user's default browser. Uses Python's built-in
# "webbrowser" module — no external dependency needed, and it already
# knows how to find the default browser on Windows, macOS, and Linux.
#
# DESIGN DECISION: this function accepts EITHER a direct URL/domain
# ("github.com") OR a plain search phrase ("best pizza in Chicago").
# We decide which one we were given using a simple heuristic: if it
# looks like a domain (no spaces, contains a dot), treat it as a URL;
# otherwise, treat it as a search query and open a search engine with it.

import webbrowser

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


def open_website(destination: str) -> str:
    """
    Open a website or a web search in the user's default browser.

    Args:
        destination: Either a URL/domain (e.g. "github.com",
            "https://openai.com") or a plain-language search query
            (e.g. "weather in Kigali").

    Returns:
        A short human-readable confirmation message.
    """
    destination_clean = destination.strip()
    looks_like_a_domain = (" " not in destination_clean) and ("." in destination_clean)

    if looks_like_a_domain:
        # Add a scheme if one wasn't given, since webbrowser.open()
        # requires a full URL to work reliably across browsers.
        if not destination_clean.startswith(("http://", "https://")):
            url = f"https://{destination_clean}"
        else:
            url = destination_clean

        logger.info("Opening website: %s", url)
        webbrowser.open(url)
        return f"Opened {destination_clean} in your browser."

    # Treat it as a search query instead of a direct URL.
    from urllib.parse import quote_plus

    search_url = f"https://www.google.com/search?q={quote_plus(destination_clean)}"
    logger.info("Opening web search for: %s", destination_clean)
    webbrowser.open(search_url)
    return f'Searched the web for "{destination_clean}".'
