"""Escape Ren'Py text-tag and substitution metacharacters in dialogue.

Ren'Py treats `{...}` as text tags and `[...]` as variable substitutions
inside say-statement strings. A literal `{` or `[` in the prose has to be
doubled. LLMs forget this constantly.

The rule: when the *agent* gives us the dialogue text as a separate field,
we escape `{`, `}`, `[`, `]` ourselves so the agent never has to think
about it. The agent CAN bypass escaping by providing already-escaped text
via a `raw: true` flag on the relevant write tool.
"""

from __future__ import annotations


def escape_dialogue(text: str) -> str:
    """Double every Ren'Py text-tag / substitution metacharacter in `text`."""
    return (
        text.replace("{", "{{")
        .replace("}", "}}")
        .replace("[", "[[")
        .replace("]", "]]")
    )
