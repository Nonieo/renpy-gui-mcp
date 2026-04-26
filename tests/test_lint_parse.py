"""Tests for the lint-output parser.

Real Ren'Py lint runs are gated on the SDK being available, so these
tests feed canned stdout strings into ``parse_lint_output`` directly —
that way the parser stays exercised regardless of whether ``RENPY_SDK``
is set.
"""

from __future__ import annotations

from renpy_mcp.project.lint_parse import parse_lint_output


CLEAN_OUTPUT = """ï»¿Ren'Py 8.6.0.25112108 lint report, generated at: Sun Apr 26 02:28:31 2026


Statistics:

The game contains 10 dialogue blocks, containing 130 words and 709 characters,
for an average of 13.0 words and 71 characters per block.

The game contains 0 menus, 2 images, and 24 screens.


Lint is not a substitute for thorough testing. Remember to update Ren'Py
before releasing. New releases fix bugs and improve compatibility.
"""

DIRTY_OUTPUT = """ï»¿Ren'Py 8.6.0 lint report, generated at: anytime

game/script.rpy:5 The jump is to nonexistent label 'nowhere'.
It is advised to set config.check_conflicting_properties to True.

game/screens.rpy:42 Image bg missing uses file 'images/totally_missing.png', which is not loadable.

game/script.rpy:10 The label dup is defined twice, at File "game/script.rpy", line 11:

and File "game/script.rpy", line 14:


Statistics:

The game contains 1 dialogue blocks.

3 errors, 0 warnings, 0 informational messages, 0 obsolete creator-defined names.

Lint is not a substitute for thorough testing.
"""


def test_clean_output_yields_no_findings():
    parsed = parse_lint_output(CLEAN_OUTPUT)
    assert parsed["findings"] == []
    assert parsed["advisories"] == []
    # Synthesized summary when the line is missing.
    assert parsed["summary"] == {"errors": 0, "warnings": 0, "info": 0, "obsolete": 0}
    assert parsed["statistics"] is not None
    assert any("dialogue blocks" in s for s in parsed["statistics"])


def test_dirty_output_extracts_findings_with_severity():
    parsed = parse_lint_output(DIRTY_OUTPUT)
    findings = parsed["findings"]
    # Three primary findings: nonexistent jump, missing asset, defined twice.
    assert len(findings) >= 3
    by_msg = {f["message"]: f for f in findings}
    nonexistent = next(f for m, f in by_msg.items() if "nonexistent" in m)
    assert nonexistent["file"] == "game/script.rpy"
    assert nonexistent["line"] == 5
    assert nonexistent["severity"] == "error"
    not_loadable = next(f for m, f in by_msg.items() if "not loadable" in m)
    assert not_loadable["file"] == "game/screens.rpy"
    assert not_loadable["severity"] == "error"


def test_advisories_separated_from_findings():
    parsed = parse_lint_output(DIRTY_OUTPUT)
    assert any("config.check_conflicting_properties" in a for a in parsed["advisories"])
    # Advisory must NOT appear inside any finding's message.
    assert not any(
        "check_conflicting_properties" in f["message"] for f in parsed["findings"]
    )


def test_summary_line_captured_when_present():
    parsed = parse_lint_output(DIRTY_OUTPUT)
    assert parsed["summary"] == {"errors": 3, "warnings": 0, "info": 0, "obsolete": 0}
    assert parsed["summary_line"] is not None
    assert "3 errors" in parsed["summary_line"]


def test_defined_twice_collects_references():
    parsed = parse_lint_output(DIRTY_OUTPUT)
    twice = next(
        f for f in parsed["findings"] if "defined twice" in f["message"]
    )
    refs = twice.get("references") or []
    assert {"file": "game/script.rpy", "line": 14} in refs


def test_severity_inference_for_warnings():
    """A made-up "should " sentence rounds to info — confirm the
    inference treats it as advisory rather than error."""
    sample = "game/script.rpy:1 You should consider naming this label.\n"
    parsed = parse_lint_output(sample)
    assert parsed["findings"][0]["severity"] == "info"


def test_returns_summary_when_lint_omits_it():
    """Modern Ren'Py sometimes prints no summary line. We synthesize one
    so agents have a consistent shape to dispatch on."""
    sample = "game/script.rpy:5 Image bg foo uses file 'foo.png', which is not loadable.\n"
    parsed = parse_lint_output(sample)
    assert parsed["summary"]["errors"] == 1
    assert parsed["summary"]["warnings"] == 0
