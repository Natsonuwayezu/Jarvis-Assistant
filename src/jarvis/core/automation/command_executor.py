# src/jarvis/core/automation/command_executor.py
#
# WHY THIS FILE EXISTS — READ THIS BEFORE CHANGING ANYTHING HERE:
# This module can run ANY terminal command on your computer. That is
# powerful and genuinely risky (a wrong command could delete files,
# change settings, etc.), which is exactly why your original project
# spec required this to run "only after confirmation."
#
# THE SAFETY RULE THIS FILE ENFORCES: execute_command() will REFUSE to
# run anything unless the caller passes confirmed=True. It is the
# CALLER's job (see ai_engine.py) to only ever pass confirmed=True
# after a real human has explicitly said yes — normally via a Yes/No
# dialog box shown by the GUI. This file itself has no way to show a
# dialog (staying decoupled from the UI, per our project's design), so
# it trusts its caller completely on this point. Never call this
# function with confirmed=True except immediately after a real
# human confirmation.

import subprocess

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

_COMMAND_TIMEOUT_SECONDS = 30


class CommandNotConfirmedError(Exception):
    """
    Raised when execute_command() is called without confirmed=True.
    This is not a bug to silently work around — it's the safety gate
    working correctly. Whoever is calling this function needs to get
    real user confirmation first.
    """


def execute_command(command: str, confirmed: bool = False) -> str:
    """
    Run a terminal/shell command and return its output.

    Args:
        command: The exact shell command to run, e.g. "dir" or "ls -la".
        confirmed: Must be True, and must only ever be set True right
            after a real person has explicitly approved THIS SPECIFIC
            command via a confirmation dialog. Defaults to False so
            that accidentally omitting this argument fails safely
            (refuses to run) rather than accidentally running something.

    Returns:
        The command's combined output (stdout, and stderr if the
        command failed), as a string suitable for JARVIS to summarize
        back to the user.

    Raises:
        CommandNotConfirmedError: if confirmed is not True.
    """
    if not confirmed:
        logger.warning(
            "execute_command() called WITHOUT confirmation for: %s — refusing to run.",
            command,
        )
        raise CommandNotConfirmedError(
            "This command was not confirmed by the user, so it was not run."
        )

    logger.info("Executing confirmed command: %s", command)

    try:
        result = subprocess.run(
            command,
            shell=True,  # Needed to support normal shell syntax (pipes, etc.)
            capture_output=True,
            text=True,
            timeout=_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logger.error("Command timed out after %ds: %s", _COMMAND_TIMEOUT_SECONDS, command)
        return f"The command timed out after {_COMMAND_TIMEOUT_SECONDS} seconds."

    if result.returncode == 0:
        logger.info("Command succeeded.")
        output = result.stdout.strip() or "(command completed with no output)"
    else:
        logger.warning("Command exited with code %d.", result.returncode)
        output = (
            f"(command exited with code {result.returncode})\n"
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    return output
