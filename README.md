# JARVIS — Personal AI Assistant

A production-quality personal AI assistant, built in Python, inspired by
Iron Man's JARVIS. This project is being built incrementally, one phase
at a time.

## Productivity Improvements (post-Phase-8)

After comparing this project against a much larger open-source
research framework (Stanford's OpenJarvis) to see what a more mature
personal-AI project prioritizes, two ideas stood out as genuinely
valuable AND cheap to add — no new installs, no local models:

- **Proactive routines** — JARVIS was 100% reactive through Phase 8:
  it never brought anything up unless you asked first. Now you can say
  "remind me to drink water every day at 3pm" or "remind me about the
  dentist tomorrow at 9am," and JARVIS will bring it up on its own,
  at the right time — spoken aloud too, if "Speak replies" is on.
  Ask "what reminders do I have?" or "cancel that reminder" any time.
  **Trade-off, stated plainly:** this only fires while JARVIS is
  actually open and running — it's not a true background OS service,
  by design, to avoid adding installers/permissions for a lightweight
  feature.
- **Conversation trimming** — session history now has a cap
  (`MAX_SESSION_HISTORY` in `settings.py`). Long conversations no
  longer grow the request sent to Gemini forever, which matters
  directly for staying within the free tier's rate/token limits.

A real, non-obvious bug came up while building routines: `MemoryStore`
was originally documented as "only ever used from the main thread,"
which stopped being true the moment the routine scheduler needed to
check the database from its own background thread. Testing that
surfaced a genuine `sqlite3.ProgrammingError` — fixed by allowing
cross-thread use and adding a lock so the main thread and the
scheduler thread can never collide on the same connection.

### PDF reading, GitHub integration, and a Settings page

Three more additions, closing gaps from the original project spec:

- **Read PDFs** — "summarize this PDF" or "what does this document say
  about X" now works. Uses `pypdf` (small, pure-Python, no heavy
  binaries). Honest limitation: it extracts real text, not images — a
  scanned PDF with no text layer won't work (that would need OCR, a
  much heavier dependency we're deliberately not adding).
- **GitHub integration** — check issues/PRs, or create a new issue, on
  any repo. Uses only Python's built-in `urllib` — zero new
  dependencies. Creating an issue is a real, visible, hard-to-undo
  external action, so — consistent with how terminal commands work —
  it always requires your explicit real-time confirmation first.
- **Settings page** — click "⚙ Settings" in the app to adjust JARVIS's
  personality (system prompt) and voice speed/volume, without ever
  opening a source file. Changes apply immediately to the running app
  and persist across restarts (`data/user_settings.json`, gitignored
  like your memory database).
- **Offline speech recognition** — a real, tested alternative to
  Google's online speech-to-text, using a local Vosk model. Genuinely
  verified end-to-end (synthesized speech → real local model →
  correct transcribed text, entirely offline). Opt-in via Settings,
  since it needs a one-time model download — see "Offline speech
  recognition setup" below.

## Current Status: Phase 7 — Plugins/Modules

Phases 1-6 built the foundation, window, AI chat, voice, automation,
and memory. Phase 7 lets JARVIS be extended with new capabilities
WITHOUT editing any of its core files — just drop a new Python file
into `src/jarvis/plugins/` and restart.

Two working example plugins are included:
- **get_current_datetime** — "what time is it?" / "what's today's date?"
- **convert_units** — "convert 100 fahrenheit to celsius", "how many
  kilometers is 5 miles?"

### Writing your own plugin

Create a new file in `src/jarvis/plugins/` (any name, e.g.
`my_plugin.py`) defining exactly two things:

```python
TOOL_DEFINITION = {
    "name": "my_tool_name",
    "description": "What this tool does and when the AI should use it.",
    "input_schema": {
        "type": "object",
        "properties": {
            "some_argument": {
                "type": "string",
                "description": "What this argument means.",
            }
        },
        "required": ["some_argument"],
    },
}

def handle(tool_input: dict) -> str:
    # Do something with tool_input["some_argument"], then return a
    # plain-text result string.
    return "result to show the user"
```

Restart JARVIS and the new tool is automatically available — no other
file needs to change. See `time_date_plugin.py` and
`unit_converter_plugin.py` in that same folder for two complete,
working examples to copy from.

**A broken plugin can't break JARVIS:** if a plugin file has a typo,
raises an error on import, or is missing `TOOL_DEFINITION`/`handle()`,
it's skipped with a warning in the log — the rest of JARVIS (and any
other plugins) keeps working normally. You can also "disable" a plugin
without deleting it by renaming it to start with an underscore (e.g.
`_my_plugin.py`).

## Current Status: Phase 8 — Advanced Automation (Window Control)

Phase 8 adds window management on top of Phase 5's app-opening: JARVIS
can now list open windows, and focus, minimize, maximize, or close one
by (partial) title — e.g. "minimize notepad", "what windows are open?",
"close the calculator."

**Important, honestly-stated platform limitation:** this uses the
`pygetwindow` library, which has:
- **Full support on Windows**
- **Partial support on Linux** — requires an EWMH-compliant window
  manager (most desktop environments — GNOME, KDE, XFCE — qualify;
  a bare/minimal Linux setup with no window manager does not)
- **Very limited support on macOS** — the OS restricts this kind of
  control much more tightly than Windows or Linux

Where window control isn't supported, JARVIS reports that plainly
rather than pretending it worked — and importantly, **the rest of
JARVIS keeps working normally either way**; only this one feature
becomes unavailable.

**A safety note, consistent with Phase 5's approach:** closing a
window is NOT gated behind a confirmation dialog like terminal
commands are — it can't touch files or run code, so it's a narrower,
more reversible action, matching your original spec (which only
required confirmation specifically for terminal commands).

### Memory (from Phase 6)
Phases 1-5 built the foundation, window, AI chat, voice, and
automation. Phase 6 gives JARVIS REAL memory — conversations now
survive closing and reopening the app, stored permanently in a small
local database (`data/jarvis_memory.db`):

- Every message you send and every reply JARVIS gives is saved
  permanently, not just kept in RAM for one session.
- On startup, the most recent messages are automatically loaded back
  in, so a conversation feels continuous across restarts.
- For anything further back, JARVIS can use a **recall_memory** tool
  to search your full conversation history — try asking something like
  "what did I tell you about my dog before?" after a restart.

**Your memory database is personal data, not source code** —
`data/` is in `.gitignore` and will never be pushed to GitHub.

### Automation (from Phase 5)
JARVIS can also act on your computer directly, using Gemini's "tool
use" (function calling) to decide when a request calls for an action:

- **Open applications** — "open notepad", "launch spotify"
- **Open websites / web search** — "open github.com", "search for the
  weather in Kigali"
- **Search your files** — "find my resume", "search for invoice.pdf"
  (searches your home folder, not the whole drive, for speed)
- **Create/edit files** — "create a file called notes.txt with..."
  (never silently overwrites an existing file)
- **Run terminal commands** — ⚠️ **always requires your explicit
  approval via a real Yes/No dialog box before running, no matter how
  the request is phrased.** This is the one capability that can
  genuinely affect or damage your system, so there is no way to skip
  the confirmation — not even by asking nicely.

**A safety note worth reading once:** the confirmation dialog shows
you the EXACT command before it runs. Read it before clicking "Yes" —
JARVIS will show you the command, but it's still up to you to judge
whether it's something you want run on your machine.

### Voice features (from Phase 4)
- **Voice output** — JARVIS can speak its replies out loud (fully
  offline, via your OS's built-in speech engine)
- **Voice input** — click the 🎤 button to speak a command instead of
  typing. Two modes, switchable in "⚙ Settings":
  - **Online (default)** — uses Google's free speech-to-text. No setup,
    but requires internet and sends audio to Google's servers.
  - **Offline** — uses a local model (Vosk), fully private, no internet
    needed for recognition. Requires a one-time model download (see
    below). Trade-off, stated plainly: noticeably less accurate than
    the online option, especially with background noise or unusual
    phrasing — genuinely tested and confirmed working, but don't expect
    Google-level accuracy from a ~40MB local model.
- **Wake word** — toggle "Wake word" on, then just say "Jarvis" and
  your next sentence to trigger a response hands-free

### Offline speech recognition setup

Only needed if you turn on "Offline speech recognition" in Settings —
online voice input needs none of this.

1. Install the extra dependency (already in `requirements.txt`):
   `pip install vosk`
2. Download a model from the official source:
   https://alphacephei.com/vosk/models — for English, get
   **vosk-model-small-en-us-0.15** (~40MB; larger models exist and are
   more accurate, but also slower to load).
3. Unzip it so the folder structure looks like:
   `Jarvis-Assistant/data/vosk-model/am/`, `.../conf/`, `.../graph/`,
   etc. (i.e., the *contents* of the zip go directly into
   `data/vosk-model/`, not into a nested subfolder).
4. Open JARVIS → "⚙ Settings" → turn on "Offline speech recognition" →
   Save → **restart JARVIS** (loading the model happens once at
   startup, so this setting needs a restart to take effect, unlike
   personality/voice speed which apply immediately).

If the model isn't found or fails to load, JARVIS logs a clear warning
and voice input is simply unavailable for that session — the rest of
the app (including typing) keeps working normally.

### Platform-specific setup for voice features

**PyAudio (microphone access)** can be the trickiest part to install:
- **Windows:** `pip install pyaudio` usually works directly.
- **macOS:** install PortAudio first: `brew install portaudio`, then
  `pip install pyaudio`.
- **Linux:** install PortAudio's dev headers first:
  `sudo apt install portaudio19-dev`, then `pip install pyaudio`.

**Text-to-speech (pyttsx3) on Linux specifically:** requires
`espeak-ng` (NOT the older `espeak` package — they use different voice
naming and pyttsx3 will crash on plain `espeak`). Install it with:
`sudo apt install espeak-ng`. Windows and macOS use their built-in
speech engines and need no extra install.

If voice input or output can't be set up on your machine (no
microphone/speakers, or a missing dependency), JARVIS will still run —
it just runs in text-only mode and logs a warning explaining why.

### API key setup (required — now using Google Gemini, free)
JARVIS runs on Google's Gemini API — chosen specifically because it has
a genuinely free tier (no credit card required), which matters while
you're still testing.
1. Get a **free** key at https://aistudio.google.com/apikey (sign in
   with a Google account, click "Create API key")
2. Copy `.env.example` to a new file named `.env` in the project root
3. Paste your real key into `.env`, replacing the placeholder text
4. `.env` is already excluded from git (see `.gitignore`) — it will
   never be accidentally pushed to GitHub

**Free tier limits to know about:** Gemini's free tier is generous but
rate-limited (currently around 15 requests/minute and a daily cap). If
JARVIS says it's having trouble reaching the AI service, you may have
hit that limit — wait a bit and try again.

## Project Structure

```
Jarvis-Assistant/
├── src/
│   └── jarvis/
│       ├── main.py          # Entry point — run this file to start the app
│       ├── config/
│       │   └── settings.py  # App-wide constants, model choice, system prompt
│       ├── core/
│       │   ├── ai_engine.py    # Talks to Gemini API, manages memory + tool use
│       │   ├── tools.py        # Tool schemas + dispatcher (built-in + plugins)
│       │   ├── plugin_loader.py # Discovers and loads plugins/ at startup
│       │   ├── memory_store.py # Persistent (cross-restart) conversation memory + routines
│       │   ├── routine_scheduler.py # Background thread that fires due proactive routines
│       │   ├── user_settings.py # Personality + voice prefs (data/user_settings.json)
│       │   ├── voice_input.py  # Mic capture + speech-to-text (online/Google or offline/Vosk)
│       │   ├── voice_output.py # Text-to-speech (offline)
│       │   ├── wake_word.py    # Background "Jarvis" wake-word listener
│       │   └── automation/
│       │       ├── app_launcher.py     # Opens desktop applications
│       │       ├── web_opener.py       # Opens websites / web searches
│       │       ├── file_search.py      # Searches for files by name
│       │       ├── file_manager.py     # Creates/edits files
│       │       ├── command_executor.py # Runs shell commands (confirmation-gated)
│       │       ├── window_manager.py   # Lists/focuses/minimizes/maximizes/closes windows
│       │       ├── pdf_reader.py       # Extracts text from PDF files
│       │       └── github_client.py    # Repo info, issues, PRs (create_issue is confirmation-gated)
│       ├── plugins/            # Drop new tools here — see "Writing your own plugin"
│       │   ├── time_date_plugin.py
│       │   └── unit_converter_plugin.py
│       ├── ui/
│       │   ├── main_window.py     # The desktop window (chat, mic, toggles, settings button)
│       │   └── settings_window.py # In-app personality + voice settings dialog
│       └── utils/
│           └── logger.py     # Shared logging setup
├── data/                       # Persistent memory database + user settings (gitignored)
├── tests/                     # Automated tests
├── docs/                      # Project documentation
├── requirements.txt           # External Python packages this project needs
├── .env.example                # Template for your API key (copy to .env)
├── .gitignore                 # Files git should never track
└── README.md                  # This file
```

## How to Run

These steps assume Python 3.10+ is installed on your machine.

1. **Open a terminal in the project folder** (the folder containing this
   README).

2. **Create a virtual environment** (an isolated space for this project's
   Python packages, separate from the rest of your system):

   ```
   python -m venv venv
   ```

3. **Activate the virtual environment:**

   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`

   Your terminal prompt should now show `(venv)` at the start of the line.

4. **Install dependencies:**

   ```
   pip install -r requirements.txt
   ```

5. **Set up your API key** (see "API key setup" above) and, if you
   want voice features, the platform-specific setup above.

6. **Run the app:**

   ```
   python -m src.jarvis.main
   ```

   Try things like:
   - "Open notepad" / "open calculator"
   - "Open github.com" / "search for the weather in Kigali"
   - "Find my resume" / "search for invoice.pdf"
   - "Create a file called notes.txt with 'hello world'"
   - "Run the command dir" (or `ls` on macOS/Linux) — you'll see a
     confirmation dialog; nothing runs until you click Yes
   - Tell it a fact about yourself, close the app completely, reopen
     it, and ask about that fact again — it should remember
   - "What time is it?" / "convert 100 fahrenheit to celsius" (these
     come from the example plugins, not built-in code)
   - "Remind me to stretch every day at 2pm" / "what reminders do I
     have?" / "cancel that reminder" (proactive routines — fire on
     their own later, while JARVIS stays open)
   - "What windows are open?" / "minimize notepad" / "close the
     calculator" (full support on Windows; partial on Linux; limited
     on macOS — see the Phase 8 notes above)
   - "Read ~/Documents/report.pdf and summarize it"
   - "What are the open issues on octocat/Hello-World?" (works without
     a GITHUB_TOKEN for public repos, just more rate-limited)
   - Click "⚙ Settings" to change JARVIS's personality or voice
     speed/volume — takes effect immediately

## Development Roadmap

| Phase | Focus |
|-------|-------|
| 1 | Architecture, folder structure, first working app |
| 2 | Graphical desktop interface |
| 3 | AI chat |
| 4 | Voice input/output + wake word |
| 5 | Automation (open apps, websites, files, confirmed commands) |
| 6 | Memory (persistent, cross-session) |
| 7 | Plugins/modules |
| 8 | Advanced automation (window control) *(current — final phase)* |
