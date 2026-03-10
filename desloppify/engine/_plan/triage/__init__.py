"""Triage namespace for whole-plan triage and staged triage surfaces.

Modules:
- ``core``: whole-plan triage orchestrator (``triage_epics``)
- ``apply``: plan mutation helpers
- ``dismiss``: dismissal helpers
- ``parsing``: LLM output parsing
- ``prompt``: data contracts and prompt building
- ``playbook``: staged triage command constants
"""

from __future__ import annotations

__all__ = ["apply", "core", "dismiss", "parsing", "playbook", "prompt"]
