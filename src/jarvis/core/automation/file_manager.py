# src/jarvis/core/automation/file_manager.py
#
# WHY THIS FILE EXISTS:
# Lets JARVIS create new files and edit existing ones, e.g. "create a
# file called shopping_list.txt with milk, eggs, bread" or "add 'buy
# candles' to my shopping list."
#
# SAFETY DECISION: creating a file will NOT silently overwrite an
# existing file with the same name unless you explicitly pass
# overwrite=True. This prevents an accidental "create a file called
# notes.txt" from destroying a notes.txt you already had important
# content in.

from pathlib import Path

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


class FileOperationError(Exception):
    """Raised when a file could not be created, read, or edited."""


def create_file(filepath: str, content: str = "", overwrite: bool = False) -> str:
    """
    Create a new file with the given text content.

    Args:
        filepath: Where to create the file, e.g. "~/Desktop/notes.txt"
            or a relative path like "notes.txt" (created in the
            current working directory).
        content: The text to write into the new file.
        overwrite: Must be explicitly True to replace an existing file
            at that path. Defaults to False as a safety net.

    Returns:
        A short human-readable confirmation message.

    Raises:
        FileOperationError: if the file already exists and overwrite
            is False, or if writing fails for another reason (e.g. no
            permission to write to that location).
    """
    # expanduser() turns "~" into the real home folder path, so paths
    # like "~/Desktop/notes.txt" work the way a person would expect.
    path = Path(filepath).expanduser()

    if path.exists() and not overwrite:
        raise FileOperationError(
            f"A file already exists at '{path}'. "
            "Say to overwrite it explicitly if that's really what you want."
        )

    try:
        # Create any missing parent folders too (e.g. if "Desktop/notes"
        # subfolder doesn't exist yet), matching what a person would
        # expect "create a file" to do rather than failing on that.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as error:
        logger.error("Failed to create file '%s': %s", path, error)
        raise FileOperationError(f"I couldn't create that file: {error}")

    logger.info("Created file: %s", path)
    return f"Created {path}."


def edit_file(filepath: str, content: str, mode: str = "append") -> str:
    """
    Edit an existing file by appending to it or overwriting it.

    Args:
        filepath: Path to the file to edit. Must already exist.
        content: The text to write.
        mode: "append" adds content to the end of the file (keeping
            what's already there); "overwrite" replaces the file's
            entire contents.

    Returns:
        A short human-readable confirmation message.

    Raises:
        FileOperationError: if the file doesn't exist, mode is invalid,
            or writing fails.
    """
    path = Path(filepath).expanduser()

    if not path.exists():
        raise FileOperationError(
            f"'{path}' doesn't exist yet — create it first, or ask me to create it."
        )

    if mode not in ("append", "overwrite"):
        raise FileOperationError(f"Unknown edit mode '{mode}' — use 'append' or 'overwrite'.")

    try:
        if mode == "append":
            with path.open("a", encoding="utf-8") as file:
                file.write(content)
        else:
            path.write_text(content, encoding="utf-8")
    except OSError as error:
        logger.error("Failed to edit file '%s': %s", path, error)
        raise FileOperationError(f"I couldn't edit that file: {error}")

    logger.info("Edited file (%s): %s", mode, path)
    return f"Updated {path} ({mode})."
