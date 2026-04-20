"""CLI tests for redeploy version subcommands."""
from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from redeploy.cli import cli


def _runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


def _write_version_workspace(base: Path, version: str = "1.0.0") -> None:
    (base / ".redeploy").mkdir(parents=True, exist_ok=True)
    (base / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    manifest = {
        "version": {
            "version": version,
            "scheme": "semver",
            "policy": "synced",
            "sources": [
                {"path": "VERSION", "format": "plain"},
            ],
        }
    }
    (base / ".redeploy" / "version.yaml").write_text(
        yaml.dump(manifest, sort_keys=False),
        encoding="utf-8",
    )


class TestVersionSet:
    def test_set_updates_manifest_and_sources(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_version_workspace(Path.cwd(), version="1.0.0")

            result = runner.invoke(cli, ["version", "set", "2.3.4"], catch_exceptions=False)

            assert result.exit_code == 0, result.output
            assert Path("VERSION").read_text(encoding="utf-8").strip() == "2.3.4"

            manifest = yaml.safe_load(Path(".redeploy/version.yaml").read_text(encoding="utf-8"))
            assert manifest["version"]["version"] == "2.3.4"

    def test_set_dry_run_does_not_modify_files(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_version_workspace(Path.cwd(), version="1.0.0")

            result = runner.invoke(
                cli,
                ["version", "set", "2.3.4", "--dry-run"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "DRY RUN" in result.output
            assert Path("VERSION").read_text(encoding="utf-8").strip() == "1.0.0"


class TestVersionDiff:
    def test_diff_spec_match_returns_zero(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_version_workspace(Path.cwd(), version="1.0.1")
            Path("migration.yaml").write_text(
                """
name: test
source:
  strategy: docker_full
  host: local
  app: myapp
  version: "1.0.0"
target:
  strategy: docker_full
  host: local
  app: myapp
  version: "1.0.1"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            result = runner.invoke(
                cli,
                ["version", "diff", "--spec", "migration.yaml"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "No version drift detected" in result.output

    def test_diff_spec_manifest_reference_returns_zero(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_version_workspace(Path.cwd(), version="1.0.1")
            Path("migration.yaml").write_text(
                """
name: test
source:
  strategy: docker_full
  host: local
  app: myapp
  version: "1.0.0"
target:
  strategy: docker_full
  host: local
  app: myapp
  version: "@manifest"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            result = runner.invoke(
                cli,
                ["version", "diff", "--spec", "migration.yaml"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "spec (@manifest)" in result.output

    def test_diff_spec_mismatch_returns_nonzero(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_version_workspace(Path.cwd(), version="1.0.1")
            Path("migration.yaml").write_text(
                """
name: test
source:
  strategy: docker_full
  host: local
  app: myapp
  version: "1.0.0"
target:
  strategy: docker_full
  host: local
  app: myapp
  version: "1.0.9"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            result = runner.invoke(
                cli,
                ["version", "diff", "--spec", "migration.yaml"],
                catch_exceptions=False,
            )

            assert result.exit_code == 1
            assert "Version drift detected" in result.output
            assert "spec: 1.0.9" in result.output

    def test_diff_missing_spec_returns_nonzero(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_version_workspace(Path.cwd(), version="1.0.1")

            result = runner.invoke(
                cli,
                ["version", "diff", "--spec", "missing.yaml"],
                catch_exceptions=False,
            )

            assert result.exit_code == 1
            assert "Spec not found" in result.output