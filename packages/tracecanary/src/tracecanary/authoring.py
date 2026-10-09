"""Guided contract authoring with conservative, actionable diagnostics.

Contract drafts are ordinary strict TraceCanary contracts: editing applies
as a whole or not at all, and the runtime validator remains authoritative.
Synthetic canary values are protected configuration — diagnostics never
include them, and an explicit contract export (which necessarily contains
canary values) is a separate, clearly labeled action from a value-free
report export.

The runtime validator already rejects structurally invalid drafts,
duplicate rules, and unusable canary configuration, so this review covers
what it cannot: direct retention conflicts, malformed wildcard paths, and
conservatively detectable ineffective or shadowed rules. Every diagnostic
names a safe structural location (rule ordinal or key), explains the issue,
and suggests a correction without silently weakening the contract.
"""

from __future__ import annotations

import functools
import re
from typing import Any

from tracecanary.contract import ContractError, parse_contract
from tracecanary.report import (
    BatchReport,
    Report,
    Status,
    build_report,
    ensure_object_values_absent,
    render_batch_human,
    render_human,
    render_json,
    render_junit,
    render_sarif,
)

REVIEW_VERSION = "tracecanary.contract-review/v1"
MAX_PATH_SEGMENTS = 32
_SEGMENT = re.compile(r"(?:\*|[^*/]+)")
# These JSON keys are arrays in the supported OTLP shape. The checker records
# an index there, so a literal next segment can never reach a scalar.
_ARRAY_FIELDS = {"resourceSpans", "scopeSpans", "spans", "attributes", "events", "links", "values"}
_ARRAY_STEP = re.compile(r"\*|0|[1-9][0-9]*")
_VOCABULARY_MODES = ("validate", "check", "diff", "batch", "demo", "starter")
_VOCABULARY_STATUSES: tuple[Status, ...] = ("pass", "regression", "unresolved")


def empty_template() -> dict[str, Any]:
    """A minimal, valid contract the user can extend."""
    return {
        "contract_version": "tracecanary/v1",
        "semantic_conventions_version": "opentelemetry/semconv/1.43.0",
        "canaries": [{"label": "synthetic-canary", "category": "prompt", "value": "TCANARY_REPLACE_ME_0000000000000000"}],
        "forbidden_attribute_keys": ["gen_ai.prompt"],
        "forbidden_attribute_key_prefixes": ["enduser."],
        "forbidden_path_prefixes": [],
        "required_retained_fields": [{"scope": "resource", "key": "service.name"}],
    }


def validate_draft(raw: Any) -> dict[str, Any]:
    """Validate a draft contract without weakening anything.

    Raises ContractError exactly like the runtime validator; the returned
    document is the draft itself.
    """
    if not isinstance(raw, dict):
        raise ContractError("a contract draft must be a JSON object")
    parse_contract(raw)
    return raw


@functools.lru_cache(maxsize=1)
def _report_vocabulary() -> str:
    """TraceCanary's own fixed report wording, rendered from value-free skeletons.

    Only the real renderers are used, so the text tracks the wording users
    see. Nothing here applies the protected-value check: the skeletons carry
    no contract, and building them must never be able to fail closed.
    """
    from tracecanary.campaign import render_campaign_human

    parts: list[str] = []
    for status in _VOCABULARY_STATUSES:
        for mode in _VOCABULARY_MODES:
            report = build_report("tracecanary/v1", status, [], mode=mode)
            parts.extend((render_human(report), render_json(report)))
        batch: BatchReport = {"batch_version": "tracecanary.batch/v1", "contract_version": "tracecanary/v1",
                              "status": status, "items": []}
        parts.extend((render_batch_human(batch), render_json(batch), render_sarif(batch), render_junit(batch)))
        campaign = {
            "status": status,
            "contract_version": "tracecanary/v1",
            "phases": {name: {"status": status} for name in ("contract", "control", "baseline", "candidates", "batch", "population_gate")},
            "summary": {"finding_counts": {}},
        }
        parts.append(render_campaign_human(campaign))
        review = build_report("tracecanary/v1", status, [], mode="contract-review")
        review["review"] = {"findings": [], "counts": {}}  # type: ignore[typeddict-unknown-key]
        parts.extend((render_review_human(review), render_json(review)))
    return "\n".join(parts)


def draft_canary_values(raw: Any) -> tuple[str, ...]:
    """The protected canary values a contract draft declares.

    Callers check every rendering of a review against these values, so a
    review whose own text would contain one is withheld rather than printed.
    """
    canaries = raw.get("canaries", []) if isinstance(raw, dict) else []
    if not isinstance(canaries, list):
        return ()
    return tuple(str(canary.get("value", "")) for canary in canaries if isinstance(canary, dict))


def review_contract(raw: Any) -> Report:
    """Value-free diagnostics for a contract draft.

    Diagnostics are structural: rule ordinals, scope/key-safe locations, and
    never canary values. Conflicts, duplicates, malformed paths, and
    conservatively provable ineffective rules are regressions.
    """
    if not isinstance(raw, dict):
        raise ContractError("a contract draft must be a JSON object")
    findings: list[dict[str, Any]] = []

    def add(severity: str, location: str, message: str, suggestion: str) -> None:
        findings.append({"severity": severity, "location": location, "message": message, "suggestion": suggestion})

    # Parse strictly first: structural validity is a precondition for the
    # conservative review below.
    parse_contract(raw)

    required = raw.get("required_retained_fields", [])
    forbidden_keys = list(raw.get("forbidden_attribute_keys", []))
    forbidden_prefixes = list(raw.get("forbidden_attribute_key_prefixes", []))
    path_prefixes = list(raw.get("forbidden_path_prefixes", []))

    # 1. Direct retention conflicts (the same provable conflict the CLI
    #    inspect-contract reports, here with actionable locations).
    for index, field in enumerate(required, start=1):
        identity = (field.get("scope", ""), field.get("key", ""))
        if identity[1] in forbidden_keys:
            add("conflict", f"required_retained_fields[{index}]",
                f"requires key {identity[1]!r}, which forbidden_attribute_keys forbids",
                "drop one of the two rules; a requirement and a prohibition cannot both hold")
        elif any(identity[1].startswith(prefix) for prefix in forbidden_prefixes):
            add("conflict", f"required_retained_fields[{index}]",
                f"requires key {identity[1]!r}, which a forbidden_attribute_key_prefixes entry forbids",
                "narrow the forbidden prefix or drop the requirement")

    # 3. Malformed wildcard path prefixes: the checker only ever matches
    #    literal segments and single-segment wildcards, so anything else can
    #    never match and silently protects nothing.
    for index, prefix in enumerate(path_prefixes, start=1):
        problem = _path_prefix_problem(prefix)
        if problem is not None:
            add("malformed", f"forbidden_path_prefixes[{index}]", problem,
                "use literal '/'-separated segments with '*' matching exactly one segment, and stop at a scalar value")

    # 4. Ineffective configuration, determined conservatively.
    for index, prefix in enumerate(path_prefixes, start=1):
        if "value" not in prefix.split("/"):
            add("ineffective", f"forbidden_path_prefixes[{index}]",
                "the path stops before a scalar value, so it can never block a value",
                "extend the path to the value leaf, for example .../attributes/*/value/stringValue")
    shadowed_keys = [key for key in forbidden_keys
                     if any(key != other and key.startswith(other) for other in forbidden_keys)
                     or any(key.startswith(prefix) for prefix in forbidden_prefixes)]
    for key in shadowed_keys:
        # Locations elsewhere in this review are 1-based rule ordinals.
        # list.index is 0-based, so the second key was reported as the first.
        ordinal = forbidden_keys.index(key) + 1
        add("ineffective", f"forbidden_attribute_keys[{ordinal}]",
            f"another forbidden prefix already covers {key!r}",
            "keep the broader prefix rule and drop the redundant exact key")

    # 5. Canary configuration is validated strictly by the runtime validator
    #    (unique non-empty labels and values, required-field uniqueness, JSON
    #    pointer shape); diagnostics only cover what it does not catch.
    #    A canary that occurs in TraceCanary's own report wording makes every
    #    report containing that wording fail closed with no output, so flag it
    #    here, before any run. The value itself is never echoed.
    vocabulary = _report_vocabulary()
    for index, value in enumerate(draft_canary_values(raw), start=1):
        if value and value in vocabulary:
            add("conflict", f"canaries[{index}]",
                "this canary value occurs in TraceCanary report text, so reports containing that text are withheld (exit 2, no output)",
                "use a unique synthetic value such as TCANARY_<random hex>")

    severity_order = {"conflict": 0, "malformed": 1, "ineffective": 2}
    findings.sort(key=lambda item: (severity_order[item["severity"]], item["location"]))
    status: Status = "regression" if findings else "pass"
    report = build_report(raw.get("contract_version", "tracecanary/v1"), status, [], mode="contract-review")
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
    report["review"] = {"findings": findings, "counts": counts}
    ensure_object_values_absent(report, draft_canary_values(raw))
    return report


def render_review_human(report: Report) -> str:
    """Value-free review rendering shared by the CLI and the desktop."""
    counts = report["review"]["counts"]
    headline = ", ".join(f"{count} {severity}" for severity, count in sorted(counts.items())) or "no findings"
    lines = [f"TraceCanary contract review: {report['status'].upper()} ({headline})"]
    for finding in report["review"]["findings"]:
        lines.append(f"- {finding['severity']} at {finding['location']}: {finding['message']}")
        lines.append(f"  suggestion: {finding['suggestion']}")
    lines.append("Diagnostics are structural and value-free; canary values never appear. Validation is not a privacy guarantee.")
    return "\n".join(lines) + "\n"


def _path_prefix_problem(prefix: Any) -> str | None:
    if not isinstance(prefix, str) or not prefix.startswith("/") or not prefix.strip("/"):
        return "path prefixes must start with '/' and name at least one segment"
    # A single trailing slash is an empty segment. endswith("//") missed it,
    # and pointer_matches then never reached the scalar the prefix named.
    if "//" in prefix or prefix.endswith("/"):
        return "path prefixes must not contain empty segments"
    segments = prefix.strip("/").split("/")
    if len(segments) > MAX_PATH_SEGMENTS:
        return f"path prefixes are limited to {MAX_PATH_SEGMENTS} segments"
    for segment in segments:
        if segment != "*" and ("/" in segment or "*" in segment):
            return "only whole segments may be '*'; partial wildcards can never match"
    for index, segment in enumerate(segments[:-1]):
        if segment in _ARRAY_FIELDS and _ARRAY_STEP.fullmatch(segments[index + 1]) is None:
            return "an array field must be followed by '*' or an index; a literal next segment can never match a scalar"
    return None
