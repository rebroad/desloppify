"""`update-skill` command package with backward-compatible exports."""

from __future__ import annotations

import argparse
import urllib.error

from . import cmd as _cmd

SKILL_BEGIN = _cmd.SKILL_BEGIN
SKILL_END = _cmd.SKILL_END
SKILL_TARGETS = _cmd.SKILL_TARGETS
SKILL_VERSION = _cmd.SKILL_VERSION
SKILL_VERSION_RE = _cmd.SKILL_VERSION_RE
SkillInstall = _cmd.SkillInstall

_RAW_BASE = _cmd._RAW_BASE
_FRONTMATTER_FIRST_INTERFACES = _cmd._FRONTMATTER_FIRST_INTERFACES
_download = _cmd._download
_build_section = _cmd._build_section
_ensure_frontmatter_first = _cmd._ensure_frontmatter_first
_replace_section = _cmd._replace_section

find_installed_skill = _cmd.find_installed_skill
get_project_root = _cmd.get_project_root
safe_write_text = _cmd.safe_write_text
colorize = _cmd.colorize


def resolve_interface(
    explicit: str | None = None,
    install: SkillInstall | None = None,
) -> str | None:
    """Resolve which interface to update."""
    if explicit:
        return explicit.lower()

    if install is None:
        install = find_installed_skill()
    if not install:
        return None

    if install.overlay:
        return install.overlay.lower()

    for name, (target, _overlay, _ded) in SKILL_TARGETS.items():
        if target == install.rel_path:
            return name
    return None


def update_installed_skill(interface: str) -> bool:
    """Download and install the skill document for the given interface."""
    target_rel, overlay_name, dedicated = SKILL_TARGETS[interface]
    target_path = get_project_root() / target_rel

    print(colorize(f"Downloading skill document ({interface})...", "dim"))
    try:
        skill_content = _download("SKILL.md")
        overlay_content = _download(f"{overlay_name}.md") if overlay_name else None
    except (urllib.error.URLError, OSError) as exc:
        print(colorize(f"Download failed: {exc}", "red"))
        return False

    if "desloppify-skill-version" not in skill_content:
        print(colorize("Downloaded content doesn't look like a skill document.", "red"))
        return False

    new_section = _build_section(skill_content, overlay_content)
    if interface in _FRONTMATTER_FIRST_INTERFACES:
        new_section = _ensure_frontmatter_first(new_section)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    if dedicated:
        result = new_section
    elif target_path.is_file():
        existing = target_path.read_text(encoding="utf-8", errors="replace")
        result = _replace_section(existing, new_section)
    else:
        result = new_section

    safe_write_text(target_path, result)

    version_match = SKILL_VERSION_RE.search(new_section)
    version = version_match.group(1) if version_match else "?"
    print(
        colorize(
            f"Updated {target_rel} (v{version}, tool expects v{SKILL_VERSION})",
            "green",
        )
    )
    return True


def cmd_update_skill(args: argparse.Namespace) -> None:
    """Install or update the desloppify skill document."""
    interface = resolve_interface(getattr(args, "interface", None))

    if not interface:
        print(colorize("No installed skill document found.", "yellow"))
        print()
        names = ", ".join(sorted(SKILL_TARGETS))
        print(f"Install with: desloppify update-skill <{names}>")
        return

    if interface not in SKILL_TARGETS:
        names = ", ".join(sorted(SKILL_TARGETS))
        print(colorize(f"Unknown interface '{interface}'.", "red"))
        print(f"Available: {names}")
        return

    update_installed_skill(interface)


__all__ = [
    "SKILL_BEGIN",
    "SKILL_END",
    "SKILL_TARGETS",
    "SKILL_VERSION",
    "SKILL_VERSION_RE",
    "SkillInstall",
    "_FRONTMATTER_FIRST_INTERFACES",
    "_RAW_BASE",
    "_build_section",
    "_download",
    "_ensure_frontmatter_first",
    "_replace_section",
    "cmd_update_skill",
    "colorize",
    "find_installed_skill",
    "get_project_root",
    "resolve_interface",
    "update_installed_skill",
]
