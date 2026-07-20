# src/jarvis/core/routine_scheduler.py
#
# WHY THIS FILE EXISTS:
# This is what makes JARVIS proactive instead of purely reactive.
# Every prior phase only ever responds when you type, speak, or say the
# wake word — JARVIS never brings anything up on its own. This module
# adds that: a background thread that checks for due "routines"
# (reminders scheduled via the create_routine tool) and fires a
# callback for each one that's due, e.g. "remind you to drink water
# every day at 3pm."
#
# WHY THIS DESIGN (added after reviewing how other personal-AI projects
# handle scheduled/proactive behavior): a full OS-level background
# service (running even when JARVIS itself is closed) would need a lot
# of new machinery — installers, system services, permissions — for a
# feature that's meant to stay lightweight. This scheduler only runs
# WHILE JARVIS is open, checking every 30 seconds using a simple
# background thread and the SAME SQLite database already used for
# conversation memory. That's a deliberate trade-off: less powerful
# than a true OS-level scheduler, but zero new dependencies and zero
# new things to install — consistent with keeping this project simple.
#
# THREADING NOTE: this follows the exact same pattern as
# wake_word.py's WakeWordListener — a daemon background thread that
# calls a callback function. The callback itself must be safe to call
# from a background thread; in main.py, it's wired to
# MainWindow.notify_routine(), which (like trigger_mic_listen) only
# ever puts an event on the thread-safe queue — it never touches
# Tkinter directly from this thread.

import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

from jarvis.core.memory_store import MemoryStore
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

# How often (in seconds) the background thread checks for due routines.
# 30 seconds is frequent enough that a reminder never feels late by
# more than half a minute, without checking so often it wastes CPU.
_POLL_INTERVAL_SECONDS = 30.0


class RoutineScheduler:
    """
    Runs a background thread that periodically checks for due routines
    and fires a callback for each one, then reschedules or removes it.
    """

    def __init__(self, memory_store: MemoryStore, on_routine_due: Callable[[str], None]):
        """
        Args:
            memory_store: The SAME MemoryStore instance used elsewhere
                in the app (shared with AIEngine), so routines live in
                the same database as conversation history.
            on_routine_due: A function taking the routine's description
                (string), called once for every routine that's due.
                Kept simple (one string argument) — what happens with
                that description (displaying it, speaking it) is
                decided by whoever provides this callback, not by this
                class.
        """
        self._memory = memory_store
        self._on_routine_due = on_routine_due
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """
        Start checking for due routines on a background thread. Safe
        to call once; calling it again while already running has no
        effect (logged as a warning) rather than starting a duplicate.
        """
        if self._thread is not None and self._thread.is_alive():
            logger.warning("RoutineScheduler.start() called but already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Routine scheduler started (checking every %.0fs).", _POLL_INTERVAL_SECONDS)

    def stop(self) -> None:
        """
        Signal the background thread to stop after its current check
        finishes, and wait briefly for it to actually exit.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        logger.info("Routine scheduler stopped.")

    def _poll_loop(self) -> None:
        """
        The actual background loop: repeatedly check for due routines
        every _POLL_INTERVAL_SECONDS until stop() is called. Uses
        wait() (rather than sleep()) so stop() can interrupt the wait
        immediately instead of waiting out the full interval.
        """
        while not self._stop_event.wait(timeout=_POLL_INTERVAL_SECONDS):
            self._check_due_routines()

    def _check_due_routines(self) -> None:
        """
        Look up every routine that's due right now, fire the callback
        for each, and reschedule (daily) or remove (once) it.
        """
        now_iso = datetime.now().isoformat(timespec="seconds")

        due_routines = self._memory.get_due_routines(now_iso)

        for routine in due_routines:
            logger.info("Routine due: %s", routine["description"])

            try:
                self._on_routine_due(routine["description"])
            except Exception as error:
                # A problem in the callback (e.g. a GUI issue) should
                # never crash the whole background scheduler thread —
                # log it and continue checking other/future routines.
                logger.error("Error firing routine callback: %s", error)

            if routine["recurrence"] == "daily":
                # Push next_run forward by exactly one day, keeping the
                # same time of day, so a "3pm daily" reminder stays at
                # 3pm rather than drifting.
                next_run = datetime.fromisoformat(routine["next_run"]) + timedelta(days=1)
                self._memory.reschedule_or_remove_routine(
                    routine["id"], new_next_run=next_run.isoformat(timespec="seconds")
                )
            else:
                self._memory.reschedule_or_remove_routine(routine["id"], new_next_run=None)
