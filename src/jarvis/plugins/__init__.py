# src/jarvis/plugins/__init__.py
#
# WHY THIS FOLDER EXISTS:
# This is JARVIS's plugin folder. Any .py file placed directly in here
# (not starting with "_") is automatically discovered and loaded the
# next time JARVIS starts — no changes to any other file needed.
#
# HOW TO WRITE YOUR OWN PLUGIN — every plugin file must define exactly
# two things:
#
#   1. TOOL_DEFINITION — a dict describing the tool to the AI, in the
#      SAME format used for built-in tools in core/tools.py:
#
#        TOOL_DEFINITION = {
#            "name": "my_tool_name",
#            "description": "What this tool does and when to use it.",
#            "input_schema": {
#                "type": "object",
#                "properties": {
#                    "some_argument": {
#                        "type": "string",
#                        "description": "What this argument means.",
#                    }
#                },
#                "required": ["some_argument"],
#            },
#        }
#
#   2. handle(tool_input: dict) -> str — a function that actually
#      performs the action and returns a plain-text result string.
#      tool_input is a dict matching whatever properties you declared
#      in input_schema above, e.g. tool_input["some_argument"].
#
# See time_date_plugin.py and unit_converter_plugin.py in this same
# folder for two complete, working examples to copy from.
#
# WHAT HAPPENS IF A PLUGIN IS BROKEN: core/plugin_loader.py validates
# every plugin file when JARVIS starts. If one is missing
# TOOL_DEFINITION or handle(), or fails to import at all (e.g. a typo),
# that ONE plugin is skipped with a warning in the log — it will not
# prevent JARVIS from starting or affect any other plugin.
