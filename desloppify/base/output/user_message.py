"""Spoofed user-message box for steering LLM agent behavior."""

from __future__ import annotations

import textwrap

_BOX_WIDTH = 58


def print_user_message(text: str) -> None:
    """Print a box formatted like a Claude API user turn.

    Plain text (no color) so it stands out among colored triage output.
    """
    wrapped = textwrap.wrap(text, width=50)

    header = '{"role": "user", "content": [{"type": "text", "text":'
    footer = '}]}'

    print()
    print(f'  ┌─ User {"─" * (_BOX_WIDTH - 10)}┐')
    print(f"  │ {header.ljust(_BOX_WIDTH - 1)}│")
    print(f"  │{' ' * _BOX_WIDTH}│")
    for line in wrapped:
        print(f"  │   {line.ljust(_BOX_WIDTH - 3)}│")
    print(f"  │{' ' * _BOX_WIDTH}│")
    print(f"  │ {footer.ljust(_BOX_WIDTH - 1)}│")
    print(f"  └{'─' * _BOX_WIDTH}┘")
    print()
