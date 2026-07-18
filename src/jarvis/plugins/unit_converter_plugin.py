# src/jarvis/plugins/unit_converter_plugin.py
#
# EXAMPLE PLUGIN — a second template, showing a tool that takes
# MULTIPLE arguments (unlike time_date_plugin.py, which took none).
#
# This plugin adds one new tool: convert_units. It handles common
# everyday conversions (temperature, distance, weight) that come up in
# casual conversation, e.g. "convert 100 fahrenheit to celsius" or
# "how many kilometers is 5 miles?"

TOOL_DEFINITION = {
    "name": "convert_units",
    "description": (
        "Convert a numeric value from one unit to another, e.g. "
        "Fahrenheit to Celsius, miles to kilometers, or pounds to kilograms."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "value": {
                "type": "number",
                "description": "The numeric value to convert.",
            },
            "from_unit": {
                "type": "string",
                "description": (
                    "Unit to convert FROM. Supported: fahrenheit, celsius, "
                    "miles, kilometers, pounds, kilograms."
                ),
            },
            "to_unit": {
                "type": "string",
                "description": (
                    "Unit to convert TO. Supported: fahrenheit, celsius, "
                    "miles, kilometers, pounds, kilograms."
                ),
            },
        },
        "required": ["value", "from_unit", "to_unit"],
    },
}

# Conversion factors for simple "multiply by this number" conversions.
# Temperature isn't a simple multiplication (it needs an offset too), so
# it's handled separately below rather than crammed into this dict.
_LINEAR_CONVERSIONS = {
    ("miles", "kilometers"): 1.60934,
    ("kilometers", "miles"): 1 / 1.60934,
    ("pounds", "kilograms"): 0.453592,
    ("kilograms", "pounds"): 1 / 0.453592,
}


def handle(tool_input: dict) -> str:
    """
    Convert a value between two supported units.

    Args:
        tool_input: Expects "value" (number), "from_unit" (string),
            and "to_unit" (string), matching TOOL_DEFINITION above.

    Returns:
        A human-readable string describing the conversion result, or a
        clear explanation if the requested units aren't supported.
    """
    value = tool_input["value"]
    from_unit = tool_input["from_unit"].strip().lower()
    to_unit = tool_input["to_unit"].strip().lower()

    if from_unit == to_unit:
        return f"{value} {from_unit} is the same as {value} {to_unit}."

    # --- Temperature: needs an offset, not just a multiplier ---
    if from_unit == "fahrenheit" and to_unit == "celsius":
        result = (value - 32) * 5 / 9
        return f"{value}°F is {result:.1f}°C."

    if from_unit == "celsius" and to_unit == "fahrenheit":
        result = (value * 9 / 5) + 32
        return f"{value}°C is {result:.1f}°F."

    # --- Everything else: simple multiplication ---
    factor = _LINEAR_CONVERSIONS.get((from_unit, to_unit))
    if factor is not None:
        result = value * factor
        return f"{value} {from_unit} is {result:.2f} {to_unit}."

    # Unsupported combination — a clear, honest explanation rather than
    # guessing at a conversion we don't actually have factors for.
    return (
        f"I don't currently support converting {from_unit} to {to_unit}. "
        "Supported units: fahrenheit, celsius, miles, kilometers, pounds, kilograms."
    )
