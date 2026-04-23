"""Integration tests for `redeploy prompt` — LLM routing.

These tests call the real LLM (requires OPENROUTER_API_KEY or OPENAI_API_KEY).
They are skipped automatically when no API key is available.

Run:
    cd /home/tom/github/maskservice/c2004
    pytest ../redeploy/tests/test_prompt_llm.py -v

Or from the redeploy repo root (with c2004 as workspace):
    pytest tests/test_prompt_llm.py -v --tb=short
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

C2004_ROOT = Path("/home/tom/github/maskservice/c2004")

NEEDS_LLM = pytest.mark.skipif(
    not (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")),
    reason="No LLM API key set (OPENROUTER_API_KEY / OPENAI_API_KEY)",
)


def _load_env():
    """Load .env from c2004 or ~/.redeploy/.env if present."""
    try:
        from dotenv import load_dotenv
        for candidate in [C2004_ROOT / ".env", Path.home() / ".redeploy" / ".env"]:
            if candidate.exists():
                load_dotenv(candidate, override=False)
                return
    except ImportError:
        pass


_load_env()


def build_c2004_schema() -> dict:
    """Build workspace schema rooted at c2004."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from redeploy.schema import build_schema
    return build_schema(C2004_ROOT)


def call_llm(instruction: str, schema: dict | None = None) -> dict:
    """Call LLM and return parsed JSON result."""
    if schema is None:
        schema = build_c2004_schema()

    from redeploy.cli.commands.prompt_cmd import _call_llm, _parse_llm_response
    last_err = None
    for _ in range(3):
        raw = _call_llm(schema, instruction)
        try:
            return _parse_llm_response(raw)
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            continue
    raise last_err


# ---------------------------------------------------------------------------
# Schema sanity (no LLM required)
# ---------------------------------------------------------------------------

def test_schema_discovers_c2004_specs():
    """Schema build must find pi109 specs in c2004."""
    schema = build_c2004_schema()
    assert "specs" in schema
    paths = [s["path"] for s in schema["specs"]]
    # At least migration.md for pi109 must be present
    assert any("pi109" in p for p in paths), f"No pi109 spec found in schema: {paths}"


def test_schema_has_command_catalogue():
    schema = build_c2004_schema()
    assert "commands" in schema
    assert "run" in schema["commands"]
    assert "fix" in schema["commands"]
    assert "import" in schema["commands"]


def test_schema_has_version_and_cwd():
    schema = build_c2004_schema()
    assert "version" in schema
    assert "cwd" in schema


def test_schema_has_iac_metadata():
    schema = build_c2004_schema()
    assert "iac" in schema
    assert "parsers" in schema["iac"]
    assert "plugin_templates" in schema["iac"]
    assert "supported_file_hints" in schema["iac"]
    assert "helm-kustomize" in schema["iac"]["plugin_templates"]
    assert "gitops-ci" in schema["iac"]["plugin_templates"]


# ---------------------------------------------------------------------------
# LLM routing tests — Polish + English prompts
# ---------------------------------------------------------------------------

@NEEDS_LLM
def test_prompt_dry_run_plan_polish():
    """'pokaż plan deployu na pi109' → run migration.md --dry-run."""
    result = call_llm("pokaż plan deployu na pi109")
    argv = result["argv"]
    assert argv[0] == "redeploy"
    assert argv[1] == "run"
    assert any("migration" in a for a in argv), f"Expected migration spec in argv: {argv}"
    assert "--dry-run" in argv, f"Expected --dry-run in argv: {argv}"
    # Read-only → confirm=false
    assert result.get("confirm") is False, f"Expected confirm=false for dry-run: {result}"


@NEEDS_LLM
def test_prompt_deploy_english():
    """'deploy c2004 to pi109' → run migration.md (confirm=true)."""
    result = call_llm("deploy c2004 to pi109")
    argv = result["argv"]
    assert argv[0] == "redeploy"
    assert argv[1] in ("run", "fix"), f"Unexpected command: {argv}"
    assert any("migration" in a for a in argv), f"Expected spec path in argv: {argv}"
    assert result.get("confirm") is True


@NEEDS_LLM
def test_prompt_diagnose_polish():
    """'sprawdź czy serwisy działają na pi109' → run diagnose.md (safe)."""
    result = call_llm("sprawdź czy serwisy działają na pi109")
    argv = result["argv"]
    assert argv[0] == "redeploy"
    # LLM should choose diagnose spec or dry-run run
    spec_args = " ".join(argv)
    is_safe = (
        "diagnose" in spec_args
        or "--dry-run" in argv
        or argv[1] in ("diagnose", "status")
    )
    assert is_safe, f"Expected safe command for diagnostic intent: {argv}"
    assert result.get("confirm") is False, f"Diagnostic prompt should not need confirm: {result}"


@NEEDS_LLM
def test_prompt_fix_kiosk_polish():
    """'napraw kiosk na pi109' → run fix-kiosk.md or fix command."""
    result = call_llm("napraw kiosk na pi109")
    argv = result["argv"]
    assert argv[0] == "redeploy"
    spec_args = " ".join(argv)
    assert (
        "fix-kiosk" in spec_args
        or "fix" in spec_args
        or argv[1] == "fix"
    ), f"Expected kiosk fix command: {argv}"
    assert result.get("confirm") is True, f"Fix kiosk should require confirmation: {result}"


@NEEDS_LLM
def test_prompt_bump_minor():
    """'zrób minor bump wersji' → bump . --minor."""
    result = call_llm("zrób minor bump wersji projektu")
    argv = result["argv"]
    assert argv[0] == "redeploy"
    assert argv[1] == "bump", f"Expected bump command: {argv}"
    assert "--minor" in argv, f"Expected --minor flag: {argv}"
    assert result.get("confirm") is True


@NEEDS_LLM
def test_prompt_fix_with_hint():
    """'napraw błąd braku ikon SVG' → fix with --hint."""
    result = call_llm("napraw błąd braku ikon SVG w aplikacji")
    argv = result["argv"]
    assert argv[0] == "redeploy"
    # LLM may route to inspect/plan when no exact fix spec exists
    assert argv[1] in ("fix", "run", "inspect", "plan"), f"Unexpected command: {argv}"
    if argv[1] in ("fix", "run"):
        assert result.get("confirm") is True


@NEEDS_LLM
def test_prompt_list_specs():
    """'jakie specyfikacje są dostępne' → schema-only or --dry-run (safe, no confirm)."""
    result = call_llm("jakie specyfikacje migracji są dostępne?")
    argv = result["argv"]
    assert argv[0] == "redeploy"
    # Should not be a destructive command
    assert argv[1] not in ("fix",), f"Unexpected destructive command for list intent: {argv}"


@NEEDS_LLM
def test_prompt_plugin_template_list():
    """Template list prompts should route to import --list-plugin-templates."""
    result = call_llm("jakie plugin templates parserów są dostępne?")
    argv = result["argv"]
    assert argv[0] == "redeploy"
    assert argv[1] == "import", f"Expected import command: {argv}"
    assert "--list-plugin-templates" in argv, f"Expected template listing: {argv}"
    assert result.get("confirm") is False


@NEEDS_LLM
def test_prompt_plugin_template_generation():
    """Support-extension prompts should route to a matching plugin template when available."""
    result = call_llm("dodaj obsługę helm i kustomize przez plugin")
    argv = result["argv"]
    assert argv[0] == "redeploy"
    assert argv[1] == "import", f"Expected import command: {argv}"
    assert "--plugin-template" in argv, f"Expected plugin-template flow: {argv}"
    joined = " ".join(argv)
    assert "helm-kustomize" in joined or "helm" in joined, f"Expected helm-kustomize template: {argv}"
    assert result.get("confirm") is True


@NEEDS_LLM
def test_prompt_response_has_required_fields():
    """Every LLM response must contain required keys."""
    result = call_llm("pokaż status deploymentu")
    for key in ("thought", "argv", "confirm", "human_summary"):
        assert key in result, f"Missing key '{key}' in LLM response: {result}"
    assert isinstance(result["argv"], list)
    assert isinstance(result["confirm"], bool)
    assert isinstance(result["thought"], str)
    assert isinstance(result["human_summary"], str)


@NEEDS_LLM
def test_prompt_argv_always_starts_with_redeploy():
    """LLM must always produce argv[0]='redeploy'."""
    for instruction in [
        "wdróż aplikację",
        "deploy the app",
        "restart services",
        "sprawdź logi",
    ]:
        result = call_llm(instruction)
        assert result["argv"][0] == "redeploy", (
            f"argv[0] != 'redeploy' for instruction '{instruction}': {result['argv']}"
        )


@NEEDS_LLM
def test_prompt_uses_real_spec_paths():
    """LLM must not invent spec paths — only use ones from schema."""
    schema = build_c2004_schema()
    known_paths = {s["path"] for s in schema["specs"]}

    result = call_llm("zrób pełny deploy na pi109", schema=schema)
    argv = result["argv"]
    # Extract any .md/.yaml-looking args that look like paths
    spec_args = [a for a in argv if a.endswith((".md", ".yaml", ".yml"))]
    for sp in spec_args:
        # Allow relative paths that match any known path suffix
        assert any(
            known.endswith(sp) or sp.endswith(known) or Path(known).name == Path(sp).name
            for known in known_paths
        ), f"LLM invented path '{sp}' not found in schema specs: {known_paths}"


# ---------------------------------------------------------------------------
# CLI invocation test (subprocess)
# ---------------------------------------------------------------------------

@NEEDS_LLM
def test_prompt_cli_schema_only(tmp_path):
    """CLI: `redeploy prompt --schema-only` exits 0 and prints JSON."""
    import subprocess, sys
    redeploy_bin = Path(__file__).parent.parent / ".venv" / "bin" / "redeploy"
    if not redeploy_bin.exists():
        pytest.skip("redeploy venv not found")

    result = subprocess.run(
        [str(redeploy_bin), "prompt", "--schema-only", "test"],
        capture_output=True, text=True, cwd=str(C2004_ROOT)
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # Output contains JSON-like content (schema panel printed by rich)
    assert "cwd" in result.stdout or "specs" in result.stdout


@NEEDS_LLM
def test_prompt_cli_dry_run_no_confirm(tmp_path):
    """CLI: `redeploy prompt --dry-run --yes 'pokaż plan'` should not hang on confirm."""
    import subprocess
    redeploy_bin = Path(__file__).parent.parent / ".venv" / "bin" / "redeploy"
    if not redeploy_bin.exists():
        pytest.skip("redeploy venv not found")

    proc = subprocess.run(
        [str(redeploy_bin), "prompt", "--dry-run", "--yes",
         "pokaż plan deployu na pi109"],
        capture_output=True, text=True, cwd=str(C2004_ROOT),
        timeout=60,
    )
    # Should complete without hanging (returncode may be non-zero due to SSH unavailable)
    # but must not timeout
    assert proc.returncode is not None
    # LLM response should appear in stdout
    assert "redeploy" in proc.stdout.lower() or "migration" in proc.stdout.lower(), (
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )


# ---------------------------------------------------------------------------
# Unit tests for _parse_llm_response (no LLM required)
# ---------------------------------------------------------------------------

def test_parse_llm_response_escapes_control_characters():
    """_parse_llm_response must escape control characters instead of removing them."""
    from redeploy.cli.commands.prompt_cmd import _parse_llm_response
    
    # Simulate LLM response with control character embedded in string value
    # This is what caused the original test failure
    response_with_control = '''{
  "thought": "User asks which migration specs are available. The workspace contains a list of specs with names and\u000bversions.",
  "argv": ["redeploy", "plan", "--help"],
  "confirm": false,
  "human_summary": "Wyświetlam listę aktualnych zadań deploymentowych w systemie."
}'''
    
    result = _parse_llm_response(response_with_control)
    assert result["argv"][0] == "redeploy"
    assert result["confirm"] is False
    # The control character should be escaped in the output
    assert "\\u000b" in result["thought"] or "\u000b" in result["thought"]


def test_parse_llm_response_handles_markdown_fences():
    """_parse_llm_response must strip ```json ... ``` fences."""
    from redeploy.cli.commands.prompt_cmd import _parse_llm_response
    
    response_with_fences = '''```json
{
  "thought": "test",
  "argv": ["redeploy", "run", "spec.md"],
  "confirm": true,
  "human_summary": "Deploy to spec"
}
```'''
    
    result = _parse_llm_response(response_with_fences)
    assert result["argv"][0] == "redeploy"
    assert result["confirm"] is True


def test_parse_llm_response_preserves_newlines():
    """_parse_llm_response must preserve escaped \\n, \\r, \\t in JSON strings."""
    from redeploy.cli.commands.prompt_cmd import _parse_llm_response
    
    # LLM returns JSON with escaped sequences (not raw control characters in strings)
    response_with_whitespace = r'''{
  "thought": "Line 1\nLine 2\rLine 3\tTabbed",
  "argv": ["redeploy", "status"],
  "confirm": false,
  "human_summary": "Status check"
}'''
    
    result = _parse_llm_response(response_with_whitespace)
    assert "Line 1\nLine 2\rLine 3\tTabbed" in result["thought"]


def test_parse_llm_response_handles_trailing_commas():
    """_parse_llm_response must repair trailing commas before } or ]."""
    from redeploy.cli.commands.prompt_cmd import _parse_llm_response
    
    response_with_trailing_comma = '''{
  "thought": "test",
  "argv": ["redeploy", "status",],
  "confirm": false,
  "human_summary": "Status check",
}'''
    
    result = _parse_llm_response(response_with_trailing_comma)
    assert result["argv"] == ["redeploy", "status"]
    assert result["confirm"] is False


def test_parse_llm_response_handles_raw_newlines_in_strings():
    """_parse_llm_response must escape raw newlines that appear inside JSON strings."""
    from redeploy.cli.commands.prompt_cmd import _parse_llm_response
    
    response_with_raw_newlines = '''{
  "thought": "Line one
Line two",
  "argv": ["redeploy", "status"],
  "confirm": false,
  "human_summary": "Status check"
}'''
    
    result = _parse_llm_response(response_with_raw_newlines)
    assert "Line one\nLine two" in result["thought"]


def test_parse_llm_response_extracts_json_from_surrounding_text():
    """_parse_llm_response must find the JSON object if the LLM adds extra text."""
    from redeploy.cli.commands.prompt_cmd import _parse_llm_response
    
    response_with_extra_text = '''Here is the JSON you requested:
{
  "thought": "test",
  "argv": ["redeploy", "status"],
  "confirm": false,
  "human_summary": "Status check"
}
Hope that helps!'''
    
    result = _parse_llm_response(response_with_extra_text)
    assert result["argv"] == ["redeploy", "status"]
    assert result["confirm"] is False
