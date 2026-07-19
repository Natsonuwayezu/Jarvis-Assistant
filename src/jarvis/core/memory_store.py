# src/jarvis/core/memory_store.py
#
# WHY THIS FILE EXISTS:
# Phases 1-5 all forget everything the moment you close JARVIS —
# self._history in ai_engine.py lives only in RAM. This file gives
# JARVIS REAL, PERMANENT memory: every message you send and every
# reply JARVIS gives gets saved to a small database on disk, so it's
# still there the next time you open the app.
#
# WHY SQLITE (not a plain JSON/text file): SQLite is part of Python's
# standard library (no new dependency), handles many small writes
# reliably (each message is its own transaction — a JSON file, by
# contrast, means rewriting the ENTIRE file on every single message,
# which is slower and risks corruption if the app closes mid-write),
# and lets us actually SEARCH old messages efficiently (see
# search_messages below) rather than having to load and scan
# everything by hand.
#
# HOW THIS FITS THE PROJECT'S DESIGN: ai_engine.py owns one MemoryStore
# instance. On startup it preloads recent messages into the in-session
# history (see AIEngine.__init__). Every successful exchange gets
# saved here too. Older history beyond what's preloaded is reachable
# via the "recall_memory" tool (see tools.py), which calls
# search_messages() below.

import sqlite3
from pathlib import Path
from typing import List, Dict

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

# Where this file lives: .../Jarvis-Assistant/src/jarvis/core/memory_store.py
# .parents[3] walks up three folders to the project root, matching the
# same pattern used in utils/logger.py for finding the project root.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "jarvis_memory.db"


class MemoryStore:
    """
    Manages JARVIS's permanent, cross-session conversation memory,
    backed by a small SQLite database file on disk.

    THREADING NOTE: this class is only ever used from AIEngine, whose
    methods (per the design established in Phases 4-5) only ever run
    on the main thread — so we don't need to worry about multiple
    threads writing to the database at once here.
    """

    def __init__(self, db_path: Path = None):
        """
        Open (or create) the memory database.

        Args:
            db_path: Where the database file should live. Defaults to
                data/jarvis_memory.db in the project root.
        """
        self._db_path = db_path or _DEFAULT_DB_PATH

        # Make sure the "data" folder exists before SQLite tries to
        # create the database file inside it.
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = sqlite3.connect(self._db_path)
        self._create_table_if_needed()

        logger.info("MemoryStore opened at %s", self._db_path)

    def _create_table_if_needed(self) -> None:
        """
        Create the "messages" table the first time JARVIS ever runs.
        "IF NOT EXISTS" makes this safe to call every startup — it
        does nothing if the table is already there from a previous run.
        """
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        self._connection.commit()

    def save_message(self, role: str, content: str) -> None:
        """
        Permanently save one message to the conversation history.

        Args:
            role: Either "user" or "assistant".
            content: The plain-text message content.
        """
        # Using "?" placeholders (rather than inserting role/content
        # directly into the SQL string) prevents SQL injection — this
        # is the standard, safe way to include variable data in a query.
        self._connection.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)", (role, content)
        )
        self._connection.commit()

        logger.debug("Saved %s message to persistent memory (%d chars).", role, len(content))

    def get_recent_messages(self, limit: int) -> List[Dict[str, str]]:
        """
        Retrieve the most recent messages, in chronological order
        (oldest of the selected batch first) — the order most chat AI APIs
        expects for conversation history.

        Args:
            limit: Maximum number of messages to retrieve.

        Returns:
            A list of {"role": ..., "content": ...} dictionaries, ready
            to be used directly as conversation history for most chat AI APIs.
        """
        # We select the most recent rows first (DESC = newest first),
        # then reverse the Python list afterward — this is simpler than
        # writing more complex SQL to get "last N, but in forward order."
        cursor = self._connection.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = cursor.fetchall()
        rows.reverse()

        return [{"role": role, "content": content} for role, content in rows]

    def search_messages(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Search past messages for ones containing the given text —
        used by the "recall_memory" tool when the AI needs to look
        further back than what's preloaded into normal context.

        Args:
            query: Text to search for (case-insensitive substring match).
            limit: Maximum number of matches to return.

        Returns:
            A list of {"role", "content", "timestamp"} dictionaries for
            matching messages, most recent match first.
        """
        # LOWER(content) LIKE LOWER(?) makes the search case-insensitive.
        # The % wildcards mean "the query can appear anywhere in the text."
        cursor = self._connection.execute(
            """
            SELECT role, content, timestamp FROM messages
            WHERE LOWER(content) LIKE LOWER(?)
            ORDER BY id DESC
            LIMIT ?
            """,
            (f"%{query}%", limit),
        )
        rows = cursor.fetchall()

        return [
            {"role": role, "content": content, "timestamp": timestamp}
            for role, content, timestamp in rows
        ]

    def close(self) -> None:
        """
        Close the database connection cleanly. Called once, when the
        whole application is shutting down (see main.py).
        """
        self._connection.close()
        logger.info("MemoryStore closed.")
