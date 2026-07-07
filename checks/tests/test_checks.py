"""Layer2 チェックの pure function に対する pytest。

ネットワークには一切出ない。fetch/parse で得られる想定の list/str を直接渡し、
判定ロジック(diff_models / parse_from_line / judge_tag)だけを検証する。
"""

from checks.check_anthropic_models import diff_models
from checks.check_litellm_image import parse_from_line, judge_tag


# --- diff_models ---------------------------------------------------------

def test_diff_models_all_referenced_present_and_no_new_models_is_ok():
    referenced = ["claude-sonnet-4-5-20250929", "claude-opus-4-1-20250805"]
    available = ["claude-sonnet-4-5-20250929", "claude-opus-4-1-20250805"]
    result = diff_models(referenced, available)
    assert result["status"] == "ok"
    assert result["details"] == []


def test_diff_models_referenced_slug_missing_from_api_is_drift():
    # config が参照している架空モデルが Anthropic API 一覧に存在しない -> drift
    referenced = ["claude-sonnet-4-5-20250929", "claude-nonexistent-9"]
    available = ["claude-sonnet-4-5-20250929", "claude-opus-4-1-20250805"]
    result = diff_models(referenced, available)
    assert result["status"] == "drift"
    assert any("claude-nonexistent-9" in d for d in result["details"])


def test_diff_models_new_model_not_referenced_is_warn():
    referenced = ["claude-sonnet-4-5-20250929"]
    available = ["claude-sonnet-4-5-20250929", "claude-fable-6-20261201"]
    result = diff_models(referenced, available)
    assert result["status"] == "warn"
    assert any("claude-fable-6-20261201" in d for d in result["details"])


def test_diff_models_drift_takes_precedence_over_warn():
    referenced = ["claude-nonexistent-9"]
    available = ["claude-opus-4-1-20250805", "claude-fable-6-20261201"]
    result = diff_models(referenced, available)
    assert result["status"] == "drift"


def test_diff_models_ignores_non_claude_new_models():
    referenced = ["claude-sonnet-4-5-20250929"]
    available = ["claude-sonnet-4-5-20250929", "gemini-3-pro"]
    result = diff_models(referenced, available)
    assert result["status"] == "ok"


# --- parse_from_line ------------------------------------------------------

def test_parse_from_line_extracts_tag():
    assert parse_from_line("FROM ghcr.io/berriai/litellm:main-v1.55.0") == "main-v1.55.0"


def test_parse_from_line_with_as_builder_stage():
    assert parse_from_line("FROM ghcr.io/berriai/litellm:v1.55.0 AS builder") == "v1.55.0"


def test_parse_from_line_implicit_latest_when_no_colon():
    assert parse_from_line("FROM ghcr.io/berriai/litellm") == "latest"


def test_parse_from_line_returns_none_for_non_from_line():
    assert parse_from_line("RUN pip install -r requirements.txt") is None


def test_parse_from_line_ignores_leading_whitespace():
    assert parse_from_line("   FROM python:3.12-slim") == "3.12-slim"


# --- judge_tag --------------------------------------------------------------

def test_judge_tag_unpinned_main_latest_is_warn():
    result = judge_tag("main-latest", "v1.60.0")
    assert result["status"] == "warn"


def test_judge_tag_unpinned_latest_is_warn():
    result = judge_tag("latest", "v1.60.0")
    assert result["status"] == "warn"


def test_judge_tag_unpinned_main_is_warn():
    result = judge_tag("main", "v1.60.0")
    assert result["status"] == "warn"


def test_judge_tag_matches_latest_release_is_ok():
    result = judge_tag("v1.60.0", "v1.60.0")
    assert result["status"] == "ok"


def test_judge_tag_matches_latest_release_ignoring_v_prefix():
    result = judge_tag("1.60.0", "v1.60.0")
    assert result["status"] == "ok"


def test_judge_tag_older_than_latest_is_warn():
    result = judge_tag("v1.40.0", "v1.60.0")
    assert result["status"] == "warn"


def test_judge_tag_unknown_when_latest_release_unavailable():
    result = judge_tag("v1.40.0", None)
    assert result["status"] == "unknown"
