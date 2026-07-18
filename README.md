# JARVIS — Personal AI Assistant

A production-quality personal AI assistant, built in Python, inspired by
Iron Man's JARVIS. This project is being built incrementally, one phase
at a time.

## Current Status: Phase 1 — Foundation

Phase 1 proves the project skeleton works: folder structure, virtual
environment, logging, and a runnable entry point. No AI, voice, or
automation yet — those come in later phases.

## Project Structure

```
Jarvis-Assistant/
├── src/
│   └── jarvis/
│       ├── main.py          # Entry point — run this file to start the app
│       ├── config/
│       │   └── settings.py  # App-wide constants and configuration
│       ├── core/             # (Phase 3+) AI reasoning, conversation engine
│       ├── ui/                # (Phase 2+) Desktop graphical interface
│       └── utils/
│           └── logger.py     # Shared logging setup
├── tests/                     # Automated tests
├── docs/                      # Project documentation
├── requirements.txt           # External Python packages this project needs
├── .gitignore                 # Files git should never track
└── README.md                  # This file
```

## How to Run Phase 1

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

4. **Install dependencies** (Phase 1 has none yet, but this is the command
   you'll use from here on as we add packages):

   ```
   pip install -r requirements.txt
   ```

5. **Run the app:**

   ```
   python -m src.jarvis.main
   ```

   You should see a startup banner printed in the terminal, and a new
   `logs/jarvis.log` file will appear in the project folder.

## Development Roadmap

| Phase | Focus |
|-------|-------|
| 1 | Architecture, folder structure, first working app *(current)* |
| 2 | Graphical desktop interface |
| 3 | AI chat |
| 4 | Voice input/output + wake word |
| 5 | Automation (open apps, websites, files) |
| 6 | Memory (conversation history) |
| 7 | Plugins/modules |
| 8 | Advanced automation (Windows control, terminal commands) |
