# src/jarvis/__init__.py
#
# This file marks the "jarvis" folder as a Python PACKAGE, not just a folder.
# Because this file exists, Python lets us write things like:
#     from jarvis.utils.logger import get_logger
# instead of manually messing with file paths.
#
# We also store the app's version number here, in one central place,
# so every other file can import it instead of hardcoding "0.1.0" everywhere.

__version__ = "0.1.0"
