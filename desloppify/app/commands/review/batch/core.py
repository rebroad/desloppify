"""Core public facade for holistic review batch processing helpers."""

from __future__ import annotations

from pathlib import Path

from .core_merge_support import assessment_weight
from .core_models import (
    BatchDimensionJudgmentPayload,
    BatchDimensionNotePayload,
    BatchIssuePayload,
    BatchQualityPayload,
    BatchResultPayload,
)
from .core_normalize import normalize_batch_result
from .core_parse import extract_json_payload, parse_batch_selection
from .prompt_template import render_batch_prompt


def merge_batch_results(
    batch_results: list[BatchResultPayload],
    *,
    abstraction_sub_axes: tuple[str, ...],
    abstraction_component_names: dict[str, str],
) -> dict[str, object]:
    """Deterministically merge assessments/issues across batch outputs."""
    from .merge import merge_batch_results as _merge_batch_results

    return _merge_batch_results(
        batch_results,
        abstraction_sub_axes=abstraction_sub_axes,
        abstraction_component_names=abstraction_component_names,
    )


def build_batch_prompt(
    *,
    repo_root: Path,
    packet_path: Path,
    batch_index: int,
    batch: dict[str, object],
) -> str:
    """Render one subagent prompt for a holistic investigation batch."""
    return render_batch_prompt(
        repo_root=repo_root,
        packet_path=packet_path,
        batch_index=batch_index,
        batch=batch,
    )


__all__ = [
    "assessment_weight",
    "build_batch_prompt",
    "extract_json_payload",
    "merge_batch_results",
    "normalize_batch_result",
    "parse_batch_selection",
]
