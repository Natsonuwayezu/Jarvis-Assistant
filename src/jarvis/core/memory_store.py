# src/jarvis/core/memory_store.py
#
# WHY THIS FILE EXISTS:
# Phases 1-5 all forget everything the moment you close JARVIS —
# self._history in ai_engine.py lives only in RAM. This file gives
# JARVIS REAL, PERMANENT memory: every message you send and every
# reply JARVIS gives gets saved to a small database on disk, so it's
# still there the next time you open the app. It also backs the
# proactive "routines" feature (reminders JARVIS brings up on its own).
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
# instance, shared with RoutineScheduler. On startup it preloads recent
# messages into the in-session history (see AIEngine.__init__). Every
# successful exchange gets saved here too. Older history beyond what's
# preloaded is reachable via the "recall_memory" tool (see tools.py),
# which calls search_messages() below.
#
# THREADING NOTE: MemoryStore was originally documented as "only ever
# used from the main thread" — that stopped being true the moment
# RoutineScheduler (core/routine_scheduler.py) started calling routine
# methods from its own background thread. Testing that addition
# surfaced a real sqlite3.ProgrammingError ("objects created in a
# thread can only be used in that same thread"), which is why every
# database operation below is now wrapped in self._lock: sqlite3
# connections can be shared across threads if check_same_thread=False
# is set, but the library does NOT automatically serialize concurrent
# access for you — a lock is still needed to prevent two threads (the
# main thread saving a message, the scheduler thread checking routines)
# from touching the connection at the exact same moment.

import sqlite3
import threading
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
    Manages JARVIS's permanent, cross-session conversation memory and
    scheduled routines, backed by a small SQLite database file on disk.

    THREAD-SAFE: this class is used from BOTH the main thread (via
    AIEngine, for conversation history) and the background scheduler
    thread (via RoutineScheduler, for routines) — every method below
    acquires self._lock before touching the database connection, so
    calls from either thread can't corrupt or crash on the shared
    connection.
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

        # check_same_thread=False lets this connection be used from a
        # thread other than the one that created it (needed for
        # RoutineScheduler's background thread). This alone does NOT
        # make concurrent access safe — self._lock (below) is what
        # actually prevents two threads from colliding.
        self._connection = sqlite3.connect(self._db_path, check_same_thread=False)
        self._lock = threading.Lock()

        with self._lock:
            self._create_table_if_needed()

        logger.info("MemoryStore opened at %s", self._db_path)

    def _create_table_if_needed(self) -> None:
        """
        Create the "messages" and "routines" tables the first time
        JARVIS ever runs. "IF NOT EXISTS" makes this safe to call every
        startup — it does nothing if the tables already exist from a
        previous run.

        NOTE: callers of this private method must already hold
        self._lock — it does not acquire it itself, since __init__
        (its only caller) acquires it around this call.
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

        # "routines" backs the proactive-reminders feature (added
        # alongside a review of OpenJarvis's scheduled-agent designs):
        # a routine is something JARVIS should say/remind you of at a
        # specific time, optionally repeating daily. It lives in the
        # SAME database as conversation history, since it's really just
        # more persistent JARVIS state — not a separate concern needing
        # its own file or connection.
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS routines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                next_run TEXT NOT NULL,
                recurrence TEXT NOT NULL DEFAULT 'once'
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
        with self._lock:
            # Using "?" placeholders (rather than inserting role/content
            # directly into the SQL string) prevents SQL injection —
            # this is the standard, safe way to include variable data.
            self._connection.execute(
                "INSERT INTO messages (role, content) VALUES (?, ?)", (role, content)
            )
            self._connection.commit()

        logger.debug("Saved %s message to persistent memory (%d chars).", role, len(content))

    def get_recent_messages(self, limit: int) -> List[Dict[str, str]]:
        """
        Retrieve the most recent messages, in chronological order
        (oldest of the selected batch first) — the order most chat AI
        APIs expect for conversation history.

        Args:
            limit: Maximum number of messages to retrieve.

        Returns:
            A list of {"role": ..., "content": ...} dictionaries, ready
            to be used directly as conversation history for most chat AI APIs.
        """
        with self._lock:
            # We select the most recent rows first (DESC = newest first),
            # then reverse the Python list afterward — this is simpler
            # than writing more complex SQL to get "last N, but in order."
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
        with self._lock:
            # LOWER(content) LIKE LOWER(?) makes the search
            # case-insensitive. The % wildcards mean "the query can
            # appear anywhere in the text."
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

    def create_routine(self, description: str, next_run: str, recurrence: str = "once") -> int:
        """
        Schedule a new proactive routine (a reminder JARVIS will bring
        up on its own at the given time, without you asking first).

        Args:
            description: What JARVIS should say/remind you of, e.g.
                "remind you to drink water".
            next_run: ISO 8601 datetime string (e.g.
                "2026-07-20T15:00:00") for when this should next fire.
            recurrence: "once" (fires a single time, then is removed)
                or "daily" (fires every day at the same time, and
                reschedules itself automatically afterward).

        Returns:
            The new routine's database ID (useful for cancel_routine).
        """
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO routines (description, next_run, recurrence) VALUES (?, ?, ?)",
                (description, next_run, recurrence),
            )
            self._connection.commit()
            new_id = cursor.lastrowid

        logger.info("Created routine #%d: '%s' at %s (%s)", new_id, description, next_run, recurrence)
        return new_id

    def list_routines(self) -> List[Dict]:
        """
        List every currently scheduled routine.

        Returns:
            A list of {"id", "description", "next_run", "recurrence"}
            dictionaries, soonest first.
        """
        with self._lock:
            cursor = self._connection.execute(
                "SELECT id, description, next_run, recurrence FROM routines ORDER BY next_run ASC"
            )
            rows = cursor.fetchall()

        return [
            {"id": row_id, "description": description, "next_run": next_run, "recurrence": recurrence}
            for row_id, description, next_run, recurrence in rows
        ]

    def get_due_routines(self, now_iso: str) -> List[Dict]:
        """
        Fetch every routine whose next_run time has already passed —
        used by the background scheduler (core/routine_scheduler.py)
        to know what to fire right now.

        Args:
            now_iso: The current time as an ISO 8601 string. Passed in
                (rather than computed here) so calling code controls
                exactly what "now" means, which also makes this method
                easy to test with a fixed, predictable time.

        Returns:
            A list of {"id", "description", "next_run", "recurrence"}
            dictionaries that are due to fire.
        """
        with self._lock:
            cursor = self._connection.execute(
                "SELECT id, description, next_run, recurrence FROM routines WHERE next_run <= ?",
                (now_iso,),
            )
            rows = cursor.fetchall()

        return [
            {"id": row_id, "description": description, "next_run": next_run, "recurrence": recurrence}
            for row_id, description, next_run, recurrence in rows
        ]

    def reschedule_or_remove_routine(self, routine_id: int, new_next_run: str = None) -> None:
        """
        After a routine fires, either remove it (one-time routines) or
        push its next_run forward (recurring routines).

        Args:
            routine_id: Which routine just fired.
            new_next_run: The new ISO 8601 next_run time for a
                recurring routine. If None, the routine is deleted
                instead (used for "once" routines).
        """
        with self._lock:
            if new_next_run is None:
                self._connection.execute("DELETE FROM routines WHERE id = ?", (routine_id,))
            else:
                self._connection.execute(
                    "UPDATE routines SET next_run = ? WHERE id = ?", (new_next_run, routine_id)
                )
            self._connection.commit()

        if new_next_run is None:
            logger.info("Routine #%d completed and removed (one-time).", routine_id)
        else:
            logger.info("Routine #%d rescheduled to %s.", routine_id, new_next_run)

    def cancel_routine(self, routine_id: int) -> bool:
        """
        Cancel (permanently delete) a scheduled routine.

        Args:
            routine_id: The routine's database ID (from list_routines).

        Returns:
            True if a routine was actually found and deleted, False if
            no routine with that ID existed.
        """
        with self._lock:
            cursor = self._connection.execute("DELETE FROM routines WHERE id = ?", (routine_id,))
            self._connection.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info("Cancelled routine #%d.", routine_id)
        return deleted

    def close(self) -> None:
        """
        Close the database connection cleanly. Called once, when the
        whole application is shutting down (see main.py).
        """
        with self._lock:
            self._connection.close()
        logger.info("MemoryStore closed.")
