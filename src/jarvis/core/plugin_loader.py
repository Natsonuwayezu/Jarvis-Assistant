# src/jarvis/core/plugin_loader.py
#
# WHY THIS FILE EXISTS:
# This is what makes plugins/ actually work: it scans the plugins
# folder, imports every valid plugin file it finds, and hands back a
# ready-to-use registry that tools.py merges into JARVIS's full set of
# capabilities.
#
# RESILIENCE IS THE WHOLE POINT OF THIS FILE: plugins are meant to be
# written by a person still learning (possibly you, later). A typo or
# mistake in ONE plugin file must never crash JARVIS or block other,
# correctly-written plugins from loading. Every failure mode below is
# caught and logged as a warning, then loading continues with the next file.

import importlib.util
from pathlib import Path
from typing import Callable, Dict

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

_PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"


class LoadedPlugin:
    """
    A simple container holding one successfully-loaded plugin's tool
    definition and its handler function together.
    """

    def __init__(self, tool_definition: dict, handler: Callable[[dict], str]):
        self.tool_definition = tool_definition
        self.handler = handler


def discover_plugins() -> Dict[str, LoadedPlugin]:
    """
    Scan the plugins/ folder and load every valid plugin file found.

    A plugin file is considered valid if it:
      1. Is a .py file directly inside plugins/ (not starting with "_",
         which excludes __init__.py and lets you "disable" a plugin by
         renaming it to start with an underscore)
      2. Imports without raising an exception
      3. Defines a TOOL_DEFINITION dict with at least a "name" key
      4. Defines a callable handle() function

    Any file that fails one of these checks is skipped with a warning
    logged — it does NOT stop the rest of the plugins from loading, and
    does NOT prevent JARVIS from starting.

    Returns:
        A dict mapping tool name -> LoadedPlugin, ready to be merged
        into TOOL_DEFINITIONS and used for dispatch in tools.py.
    """
    loaded: Dict[str, LoadedPlugin] = {}

    if not _PLUGINS_DIR.exists():
        logger.warning("Plugins folder not found at %s — skipping plugin loading.", _PLUGINS_DIR)
        return loaded

    for plugin_file in sorted(_PLUGINS_DIR.glob("*.py")):
        if plugin_file.name.startswith("_"):
            # Skips __init__.py, and lets someone "disable" a plugin
            # without deleting it by renaming it to start with "_".
            continue

        plugin_name = plugin_file.stem  # filename without ".py"

        try:
            # This is the standard way to import a Python file when you
            # only have its file PATH (rather than a proper importable
            # module name) — it builds a module object directly from
            # the file's location.
            spec = importlib.util.spec_from_file_location(
                f"jarvis.plugins.{plugin_name}", plugin_file
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

        except Exception as error:
            # A broad "except Exception" is intentional and correct
            # here: a plugin file could fail in literally any way (bad
            # syntax, a missing import, code that raises on load) and
            # every one of those must be treated the same way — log it,
            # skip this one file, and keep going.
            logger.warning("Failed to load plugin '%s': %s", plugin_name, error)
            continue

        tool_definition = getattr(module, "TOOL_DEFINITION", None)
        handler = getattr(module, "handle", None)

        if not isinstance(tool_definition, dict) or "name" not in tool_definition:
            logger.warning(
                "Plugin '%s' is missing a valid TOOL_DEFINITION dict — skipping.",
                plugin_name,
            )
            continue

        if not callable(handler):
            logger.warning(
                "Plugin '%s' is missing a callable handle() function — skipping.",
                plugin_name,
            )
            continue

        tool_name = tool_definition["name"]
        loaded[tool_name] = LoadedPlugin(tool_definition=tool_definition, handler=handler)
        logger.info("Loaded plugin '%s' (tool name: '%s').", plugin_name, tool_name)

    logger.info("Plugin loading complete. %d plugin(s) loaded.", len(loaded))
    return loaded
