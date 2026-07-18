# src/jarvis/core/automation/file_search.py
#
# WHY THIS FILE EXISTS:
# Lets JARVIS search your computer for files by name, e.g. "find my
# resume" or "search for invoice.pdf".
#
# DESIGN DECISIONS (worth understanding before changing this):
#   1. SCOPE: we search starting from the user's home folder (e.g.
#      C:\Users\YourName or /home/yourname), not the entire hard drive.
#      Scanning an entire drive can take minutes and hit thousands of
#      irrelevant system files — the home folder covers Documents,
#      Desktop, Downloads, etc., which is what "search my computer" means
#      to a person in practice.
#   2. TIME LIMIT: the search stops after a few seconds even if it
#      hasn't finished, so JARVIS never appears to "hang" on a huge
#      folder structure. Whatever matches were found by then are returned.
#   3. SKIPPED FOLDERS: hidden folders (starting with ".") and common
#      huge/irrelevant folders (node_modules, virtual environments) are
#      skipped, since they're never what a person means by "my files."

import os
import time
from pathlib import Path
from typing import List

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

# Folder names to skip entirely while searching — these are large,
# machine-generated, or system folders that are essentially never what
# someone means when they ask JARVIS to find a file for them.
_SKIP_DIRS = {"node_modules", "venv", ".venv", "__pycache__", ".git", "$Recycle.Bin"}

_MAX_SEARCH_SECONDS = 5.0
_MAX_RESULTS = 20


def search_files(query: str, search_root: str = None) -> List[str]:
    """
    Search for files whose name contains the given query text.

    Args:
        query: Text to search for within filenames (case-insensitive).
            e.g. "invoice" will match "invoice.pdf", "Invoice_2024.docx".
        search_root: Folder to search within. Defaults to the current
            user's home directory if not given.

    Returns:
        A list of matching file paths (as strings), capped at
        _MAX_RESULTS entries. Returns an empty list if nothing matched
        or if the search timed out before finding anything.
    """
    root = Path(search_root) if search_root else Path.home()
    query_lower = query.strip().lower()

    logger.info("Searching for files matching '%s' under %s", query_lower, root)

    matches: List[str] = []
    start_time = time.time()

    # os.walk lets us visit every folder and file under `root`, one
    # directory at a time, without loading the whole tree into memory
    # at once — important for potentially large folder structures.
    for current_dir, subdirs, files in os.walk(root):
        # Stop early if we've spent too long searching — better to
        # return partial, fast results than to make the user wait.
        if time.time() - start_time > _MAX_SEARCH_SECONDS:
            logger.debug("Search time limit reached; returning partial results.")
            break

        # Modifying `subdirs` IN PLACE (rather than reassigning it) is
        # how os.walk lets us prune which folders it descends into next
        # — this is the standard way to skip folders with os.walk.
        subdirs[:] = [
            d for d in subdirs if d not in _SKIP_DIRS and not d.startswith(".")
        ]

        for filename in files:
            if query_lower in filename.lower():
                matches.append(str(Path(current_dir) / filename))
                if len(matches) >= _MAX_RESULTS:
                    logger.debug("Result limit reached; returning early.")
                    return matches

    logger.info("Search complete. Found %d match(es).", len(matches))
    return matches
