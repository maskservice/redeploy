from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from redeploy.cli import cli


def _write_workflow(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_gh_workflow_list(tmp_path: Path):
    wf = tmp_path / ".github" / "workflows"
    _write_workflow(
        wf / "version-drift.yml",
        """
name: Version Drift Check
on:
  workflow_dispatch:
  push:
    branches: [main]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
""".strip()
        + "\n",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["gh-workflow", "list", "--repo-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "version-drift.yml" in result.output
    assert "GitHub Workflows" in result.output


def test_gh_workflow_analyze_missing_dispatch_hint(tmp_path: Path):
    wf = tmp_path / ".github" / "workflows"
    _write_workflow(
        wf / "code-quality.yml",
        """
name: Code Quality
on:
  push:
    branches: [main]
jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - run: echo check
""".strip()
        + "\n",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["gh-workflow", "analyze", "code-quality", "--repo-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "dispatchable: no" in result.output
    assert "add 'workflow_dispatch:'" in result.output


def test_gh_workflow_run_dry_run(tmp_path: Path):
    wf = tmp_path / ".github" / "workflows"
    _write_workflow(
        wf / "version-drift.yml",
        """
name: Version Drift Check
on:
  workflow_dispatch:
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
""".strip()
        + "\n",
    )

    runner = CliRunner()
    with patch("redeploy.cli.commands.gh_workflow._gh_available", return_value=True):
        result = runner.invoke(
            cli,
            [
                "gh-workflow",
                "run",
                "version-drift",
                "--repo-root",
                str(tmp_path),
                "--ref",
                "main",
                "--field",
                "service=backend",
                "--dry-run",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "gh workflow run version-drift.yml --ref main -f service=backend" in result.output


def test_gh_workflow_run_rejects_non_dispatchable(tmp_path: Path):
    wf = tmp_path / ".github" / "workflows"
    _write_workflow(
        wf / "release.yml",
        """
name: Release
on:
  push:
    tags:
      - v*.*.*
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - run: echo release
""".strip()
        + "\n",
    )

    runner = CliRunner()
    with patch("redeploy.cli.commands.gh_workflow._gh_available", return_value=True):
        result = runner.invoke(cli, ["gh-workflow", "run", "release", "--repo-root", str(tmp_path)])

    assert result.exit_code != 0
    assert "not dispatchable" in result.output
