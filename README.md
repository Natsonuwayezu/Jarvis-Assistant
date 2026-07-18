# JARVIS — Personal AI Assistant

A production-quality personal AI assistant, built in Python, inspired by
Iron Man's JARVIS. This project is being built incrementally, one phase
at a time.

## Current Status: Phase 6 — Persistent Memory

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
JARVIS can also act on your computer directly, using Claude's "tool
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
  typing (requires internet — uses Google's free speech-to-text)
- **Wake word** — toggle "Wake word" on, then just say "Jarvis" and
  your next sentence to trigger a response hands-free

**Known trade-off:** voice input is NOT offline (voice output is).
Making voice input fully offline is possible in a later phase by
swapping in a different speech-recognition engine — `core/voice_input.py`
is the only file that would need to change.

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

### API key setup (required, from Phase 3)
1. Get a key at https://console.anthropic.com/ (Settings → API Keys)
2. Copy `.env.example` to a new file named `.env` in the project root
3. Paste your real key into `.env`, replacing the placeholder text
4. `.env` is already excluded from git (see `.gitignore`) — it will
   never be accidentally pushed to GitHub

## Project Structure

```
Jarvis-Assistant/
├── src/
│   └── jarvis/
│       ├── main.py          # Entry point — run this file to start the app
│       ├── config/
│       │   └── settings.py  # App-wide constants, model choice, system prompt
│       ├── core/
│       │   ├── ai_engine.py    # Talks to Claude API, manages memory + tool use
│       │   ├── tools.py        # Tool schemas + dispatcher for automation actions
│       │   ├── memory_store.py # Persistent (cross-restart) conversation memory
│       │   ├── voice_input.py  # Microphone capture + speech-to-text
│       │   ├── voice_output.py # Text-to-speech (offline)
│       │   ├── wake_word.py    # Background "Jarvis" wake-word listener
│       │   └── automation/
│       │       ├── app_launcher.py     # Opens desktop applications
│       │       ├── web_opener.py       # Opens websites / web searches
│       │       ├── file_search.py      # Searches for files by name
│       │       ├── file_manager.py     # Creates/edits files
│       │       └── command_executor.py # Runs shell commands (confirmation-gated)
│       ├── ui/
│       │   └── main_window.py # The desktop window (chat, mic, toggles)
│       └── utils/
│           └── logger.py     # Shared logging setup
├── data/                       # Persistent memory database (gitignored)
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

## Development Roadmap

| Phase | Focus |
|-------|-------|
| 1 | Architecture, folder structure, first working app |
| 2 | Graphical desktop interface |
| 3 | AI chat |
| 4 | Voice input/output + wake word |
| 5 | Automation (open apps, websites, files, confirmed commands) |
| 6 | Memory (persistent, cross-session) *(current)* |
| 7 | Plugins/modules |
| 8 | Advanced automation (deeper OS control) |
