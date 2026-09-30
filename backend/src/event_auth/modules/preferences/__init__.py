"""Reusable member preference matching; no customer or food-specific rules."""

from typing import Any


def match_defaults(slots: list[dict[str, Any]], preference: str | None) -> dict[str, str]:
    if not preference:
        return {}
    choices = {}
    for slot in slots:
        matches = [
            option
            for option in slot["options"]
            if option["label"].strip().casefold() == preference.strip().casefold()
        ]
        # Missing or ambiguous labels require an explicit choice, never the first option.
        if len(matches) == 1:
            choices[slot["id"]] = matches[0]["id"]
    return choices
