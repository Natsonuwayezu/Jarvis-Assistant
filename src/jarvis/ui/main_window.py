# src/jarvis/ui/main_window.py
#
# WHY THIS FILE EXISTS:
# This is the visual "face" of JARVIS — the window you actually see and
# click on. It uses CustomTkinter, a library that adds a modern look
# (rounded corners, dark mode, clean fonts) on top of Python's built-in
# Tkinter GUI toolkit.
#
# IMPORTANT DESIGN DECISION — read this before touching this file later:
# This window does NOT know how to think, reason, listen, or speak by
# itself. It only knows how to:
#   1. Display messages in the chat area
#   2. Notice when you type (or click mic / wake-word) and hand the
#      resulting text off to a "callback" function given to it from
#      outside (see on_user_message, on_voice_capture, on_speak below)
#   3. Show a proactive routine (see notify_routine below) when the
#      background scheduler says one is due, WITHOUT any user action
#
# This keeps the UI decoupled from the "brain" (core/). We can swap the
# AI engine, the speech recognizer, or the TTS engine without ever
# touching this file — only the callbacks passed in from main.py change.
#
# THREADING NOTE (read this carefully — it covers two real bugs that
# came up while building this):
# Capturing microphone audio and speaking text OUT LOUD both BLOCK
# (pause) whatever thread they run on. So they run on background
# threads, to keep the window responsive. The tricky part: Tkinter
# widgets may ONLY be touched from the single main thread that created
# them — calling something like self.after(...) directly from a
# background thread is unsafe and can raise errors like "main thread is
# not in main loop" (confirmed while testing this exact file). The same
# issue applies to RoutineScheduler's background thread notifying the
# GUI that a reminder is due.
#
# THE FIX: background threads never touch Tkinter directly. Instead,
# they put their results into a thread-safe queue.Queue (safe to use
# from any thread by design). The MAIN thread runs a small recurring
# check (via self.after, scheduled from itself) that drains the queue
# and updates the GUI. This is the standard, safe pattern for combining
# background threads with Tkinter, and it's why notify_routine() below
# just pushes onto the same queue used for mic capture and wake word.

import queue
import threading
from typing import Callable, Optional

import customtkinter as ctk

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

# Appearance settings applied once, globally, before any window is created.
# "dark" mode and a blue accent color give the modern look we want.
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# How often (in milliseconds) the main thread checks for results left by
# background threads. 100ms is frequent enough to feel instant to a
# person, without wasting CPU checking constantly.
_QUEUE_POLL_INTERVAL_MS = 100


class MainWindow(ctk.CTk):
    """
    The main JARVIS application window.

    This class represents the entire visible app: title bar, scrollable
    chat history, a text input box, a Send button, a mic button, and
    toggles for voice reply and wake-word listening.
    """

    def __init__(
        self,
        on_user_message: Callable[[str], str],
        on_voice_capture: Optional[Callable[[], str]] = None,
        on_speak: Optional[Callable[[str], None]] = None,
        on_toggle_wake_word: Optional[Callable[[bool], None]] = None,
    ):
        """
        Args:
            on_user_message: A function that takes the user's message
                (a string, whether typed or spoken) and returns JARVIS's
                reply (a string).
            on_voice_capture: A function with no arguments that BLOCKS
                while listening to the microphone, then returns the
                transcribed text (or "" if nothing was understood). If
                not provided, the mic button is hidden — this keeps
                Phase 2/3 usage of this class working unchanged.
            on_speak: A function that takes JARVIS's reply text and
                speaks it out loud (blocking until finished). If not
                provided, the "speak replies" toggle is hidden.
            on_toggle_wake_word: A function that takes True/False —
                called when the user turns the wake-word toggle on/off.
                If not provided, the wake-word toggle is hidden.
        """
        super().__init__()

        # Store callbacks so button clicks / key presses can use them.
        self._on_user_message = on_user_message
        self._on_voice_capture = on_voice_capture
        self._on_speak = on_speak
        self._on_toggle_wake_word = on_toggle_wake_word

        # Tracks whether "speak replies out loud" is currently enabled.
        self._speak_replies_enabled = False

        # THE THREAD-SAFE QUEUE (see the module-level note above).
        # Any background thread (mic capture, wake-word listener) puts
        # small ("event_type", data) tuples in here. Only the MAIN
        # thread ever reads from it and touches the GUI as a result.
        self._event_queue: "queue.Queue" = queue.Queue()

        # --- Window setup ---
        self.title("JARVIS — Personal AI Assistant")
        self.geometry("700x640")
        self.minsize(500, 400)

        # Make the chat area expand to fill the window when resized.
        # (Row 0 = status bar, fixed height; row 1 = chat history, grows;
        # row 2 = input bar, fixed height.)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_status_bar()
        self._build_chat_area()
        self._build_input_bar()

        # Start the recurring queue-check loop. This first call is made
        # from __init__, which always runs on the main thread (the one
        # that will go on to call mainloop()) — so this is safe. It
        # reschedules itself every _QUEUE_POLL_INTERVAL_MS from then on.
        self.after(_QUEUE_POLL_INTERVAL_MS, self._poll_event_queue)

        logger.info("MainWindow initialized.")

    def _build_status_bar(self) -> None:
        """
        Create the top row of toggles: "Speak Replies" and "Wake Word."
        Each toggle is hidden entirely if its corresponding callback
        wasn't provided — e.g. running with only on_user_message (as in
        Phases 2-3) shows a window with no voice controls at all.
        """
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.grid(row=0, column=0, padx=15, pady=(15, 0), sticky="ew")

        if self._on_speak is not None:
            self.speak_toggle = ctk.CTkSwitch(
                status_frame,
                text="Speak replies",
                command=self._handle_speak_toggle,
            )
            self.speak_toggle.pack(side="left", padx=(0, 20))

        if self._on_toggle_wake_word is not None:
            self.wake_word_toggle = ctk.CTkSwitch(
                status_frame,
                text='Wake word ("Jarvis")',
                command=self._handle_wake_word_toggle,
            )
            self.wake_word_toggle.pack(side="left")

    def _build_chat_area(self) -> None:
        """
        Create the scrollable text box that displays the conversation
        history. It is READ-ONLY from the user's perspective — they can't
        type directly into it, only we (the code) write into it.
        """
        self.chat_display = ctk.CTkTextbox(
            self,
            wrap="word",          # Wrap long lines at word boundaries, not mid-word
            state="disabled",     # Starts locked so the user can't type into it directly
            font=ctk.CTkFont(size=14),
            corner_radius=10,
        )
        self.chat_display.grid(row=1, column=0, padx=15, pady=(10, 5), sticky="nsew")

        # Greet the user immediately so the window doesn't look empty/broken.
        self._append_message("JARVIS", "Systems online. How can I help you?")

    def _build_input_bar(self) -> None:
        """
        Create the bottom row: a text entry box, a mic button (if voice
        capture is available), and a Send button, docked to the bottom
        of the window.
        """
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=2, column=0, padx=15, pady=(5, 15), sticky="ew")

        # The input box should stretch to fill available space;
        # the mic/Send buttons stay a fixed width.
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type a message to JARVIS...",
            font=ctk.CTkFont(size=14),
            height=40,
        )
        self.input_box.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        # Pressing Enter while focused on the input box also sends the message,
        # so the user isn't forced to click the button every time.
        self.input_box.bind("<Return>", lambda event: self._handle_send())

        next_column = 1

        if self._on_voice_capture is not None:
            self.mic_button = ctk.CTkButton(
                input_frame,
                text="🎤",
                width=45,
                height=40,
                command=self._handle_mic_click,
            )
            self.mic_button.grid(row=0, column=next_column, padx=(0, 10))
            next_column += 1

        self.send_button = ctk.CTkButton(
            input_frame,
            text="Send",
            width=80,
            height=40,
            command=self._handle_send,
        )
        self.send_button.grid(row=0, column=next_column)

    def _handle_send(self) -> None:
        """
        Called when the user clicks Send or presses Enter.

        Steps:
          1. Read the text from the input box.
          2. Ignore it if it's empty (no point sending nothing).
          3. Display the user's message in the chat area.
          4. Clear the input box for the next message.
          5. Call the callback to get JARVIS's reply, and display that too.
          6. If "speak replies" is on, speak the reply out loud.
        """
        message = self.input_box.get().strip()

        if not message:
            return  # Nothing typed — do nothing, rather than sending a blank message.

        self._append_message("You", message)
        self.input_box.delete(0, "end")

        self._process_message(message)

    def _process_message(self, message: str) -> None:
        """
        Shared logic for handling a message regardless of whether it
        came from typing or voice: get JARVIS's reply, display it, and
        optionally speak it aloud. Pulled into its own method so both
        _handle_send() and the mic-capture flow can reuse it identically.

        NOTE: this method itself always runs on the MAIN thread (it's
        only ever called from _handle_send or _on_voice_captured, both
        of which run on the main thread). Only the actual speaking is
        pushed onto a background thread, since speak() blocks.
        """
        logger.info("User message received: %s", message)

        # This is where the AI engine (or, in earlier phases, a
        # placeholder) gets called. The window doesn't know or care
        # which one it is.
        reply = self._on_user_message(message)

        self._append_message("JARVIS", reply)

        if self._speak_replies_enabled and self._on_speak is not None:
            # Speaking blocks until finished, so it runs on its own
            # background thread — otherwise the window would freeze
            # (unresponsive to clicks/typing) for the whole reply.
            # speak() doesn't touch any Tkinter widgets, so — unlike
            # voice capture below — this thread needs no queue; it has
            # nothing to report back to the GUI.
            threading.Thread(
                target=self._on_speak, args=(reply,), daemon=True
            ).start()

    def _handle_mic_click(self) -> None:
        """
        Called when the mic button is clicked. Runs the (blocking)
        voice capture on a background thread so the window stays
        responsive while listening. The result is placed on the
        thread-safe queue rather than being handed back directly,
        since this method call itself may be running as a result of
        a queued event from ANOTHER thread (the wake-word listener) —
        see _poll_event_queue below.
        """
        self.mic_button.configure(state="disabled", text="...")
        threading.Thread(target=self._capture_voice_in_background, daemon=True).start()

    def _capture_voice_in_background(self) -> None:
        """
        Runs on a background thread: performs the actual (blocking)
        microphone capture + transcription, then places the result on
        the thread-safe queue. Does NOT touch any Tkinter widget or
        call self.after directly — that is the whole point of routing
        through the queue instead.
        """
        text = self._on_voice_capture()
        self._event_queue.put(("mic_result", text))

    def _poll_event_queue(self) -> None:
        """
        Runs on the MAIN thread only, every _QUEUE_POLL_INTERVAL_MS.
        Drains any pending events left by background threads and
        processes them safely, then reschedules itself.

        This is the ONLY place background-thread results ever touch
        the GUI — keeping all actual widget updates on the main thread.
        """
        try:
            while True:
                # get_nowait() raises queue.Empty immediately if there's
                # nothing waiting, instead of blocking — exactly what we
                # want in a polling loop that must return quickly.
                event_type, data = self._event_queue.get_nowait()

                if event_type == "mic_result":
                    self._on_voice_captured(data)
                elif event_type == "trigger_mic":
                    self._handle_mic_click()
                elif event_type == "routine_fired":
                    self._on_routine_fired(data)
        except queue.Empty:
            pass

        # Reschedule ourselves. Since this method only ever runs on the
        # main thread (it's only ever invoked via self.after), calling
        # self.after again here is always safe.
        self.after(_QUEUE_POLL_INTERVAL_MS, self._poll_event_queue)

    def _on_routine_fired(self, description: str) -> None:
        """
        Runs on the main thread (called only from _poll_event_queue)
        when a scheduled routine becomes due. Displays it as a JARVIS
        message WITHOUT calling the AI again — a routine is a simple,
        pre-written reminder, not a new question, so there's no need to
        spend an API call (and free-tier quota) generating a reply for
        something we already know what to say.
        """
        message = f"Reminder: {description}"
        self._append_message("JARVIS", message)

        if self._speak_replies_enabled and self._on_speak is not None:
            threading.Thread(target=self._on_speak, args=(message,), daemon=True).start()

    def _on_voice_captured(self, text: str) -> None:
        """
        Runs on the main thread (called only from _poll_event_queue)
        once voice capture finishes. Re-enables the mic button, and if
        something was actually understood, processes it exactly like a
        typed message.
        """
        self.mic_button.configure(state="normal", text="🎤")

        if not text:
            # Nothing was understood — silently do nothing rather than
            # sending an empty message or showing a scary error.
            logger.debug("Voice capture returned no text.")
            return

        self._append_message("You (voice)", text)
        self._process_message(text)

    def trigger_mic_listen(self) -> None:
        """
        Public method that starts a mic-capture cycle, identical to
        clicking the mic button. Exists so the wake-word listener
        (running on ITS OWN background thread in main.py) can safely
        request listening after hearing "Jarvis."

        SAFE FROM ANY THREAD: unlike calling self.after() directly,
        putting an item on a queue.Queue is explicitly thread-safe by
        design, so this method can be called from the wake-word
        thread, the main thread, or anywhere else without issue.
        """
        if self._on_voice_capture is None:
            return
        self._event_queue.put(("trigger_mic", None))

    def notify_routine(self, description: str) -> None:
        """
        Public method that tells the window a scheduled routine is due.
        Exists so RoutineScheduler (running on ITS OWN background
        thread in main.py) can safely notify the GUI a reminder should
        be shown — following the exact same thread-safe queue pattern
        as trigger_mic_listen above.

        SAFE FROM ANY THREAD: same reasoning as trigger_mic_listen —
        queue.Queue.put() is thread-safe by design.
        """
        self._event_queue.put(("routine_fired", description))

    def _handle_speak_toggle(self) -> None:
        """Called when the 'Speak replies' switch is flipped."""
        self._speak_replies_enabled = bool(self.speak_toggle.get())
        logger.info("Speak replies toggled: %s", self._speak_replies_enabled)

    def _handle_wake_word_toggle(self) -> None:
        """
        Called when the 'Wake word' switch is flipped. Delegates the
        actual starting/stopping of the background listener thread to
        main.py via the on_toggle_wake_word callback — this window only
        knows the toggle's on/off state, not how wake-word listening
        is implemented.
        """
        enabled = bool(self.wake_word_toggle.get())
        logger.info("Wake word toggled: %s", enabled)
        self._on_toggle_wake_word(enabled)

    def _append_message(self, sender: str, message: str) -> None:
        """
        Add a new line to the chat display.

        The textbox is normally "disabled" (read-only) so the user can't
        type into it directly. We briefly re-enable it, insert the new
        text, then disable it again — this is the standard Tkinter pattern
        for a read-only-but-programmatically-updatable text widget.
        """
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"{sender}: {message}\n\n")
        self.chat_display.configure(state="disabled")

        # Auto-scroll to the bottom so the newest message is always visible.
        self.chat_display.see("end")
