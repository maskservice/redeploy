"""CLI tests for redeploy version subcommands."""
from __future__ import annotations

from pathlib import Path
import subprocess
from unittest.mock import patch

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


def _write_monorepo_version_workspace(base: Path, *, with_package_changelogs: bool = False) -> None:
    (base / ".redeploy").mkdir(parents=True, exist_ok=True)
    (base / "backend").mkdir(parents=True, exist_ok=True)
    (base / "frontend").mkdir(parents=True, exist_ok=True)
    (base / "backend" / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (base / "frontend" / "VERSION").write_text("2.0.0\n", encoding="utf-8")

    manifest = {
        "version": {
            "version": "0.0.0",
            "scheme": "semver",
            "policy": "independent",
            "sources": [],
            "packages": {
                "backend": {
                    "version": "1.0.0",
                    "sources": [
                        {"path": "backend/VERSION", "format": "plain"},
                    ],
                },
                "frontend": {
                    "version": "2.0.0",
                    "sources": [
                        {"path": "frontend/VERSION", "format": "plain"},
                    ],
                },
            },
        }
    }

    if with_package_changelogs:
        manifest["version"]["packages"]["backend"]["changelog"] = {
            "path": "backend/CHANGELOG.md",
            "format": "keepachangelog",
        }
        manifest["version"]["packages"]["frontend"]["changelog"] = {
            "path": "frontend/CHANGELOG.md",
            "format": "keepachangelog",
        }
        (base / "backend" / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [Unreleased]\n\n- backend pending\n",
            encoding="utf-8",
        )
        (base / "frontend" / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [Unreleased]\n\n- frontend pending\n",
            encoding="utf-8",
        )

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

    def test_set_package_updates_only_selected_package(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            result = runner.invoke(
                cli,
                ["version", "set", "3.3.3", "--package", "backend"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert Path("backend/VERSION").read_text(encoding="utf-8").strip() == "3.3.3"
            assert Path("frontend/VERSION").read_text(encoding="utf-8").strip() == "2.0.0"

            manifest = yaml.safe_load(Path(".redeploy/version.yaml").read_text(encoding="utf-8"))
            assert manifest["version"]["packages"]["backend"]["version"] == "3.3.3"
            assert manifest["version"]["packages"]["frontend"]["version"] == "2.0.0"
            assert manifest["version"]["version"] == "0.0.0"


class TestVersionList:
    def test_list_all_packages_shows_package_sources(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            result = runner.invoke(
                cli,
                ["version", "list", "--all-packages"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "Package version sources" in result.output
            assert "backend/VERSION" in result.output
            assert "frontend/VERSION" in result.output
            assert "backend" in result.output
            assert "frontend" in result.output

    def test_list_package_shows_only_selected_package(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            result = runner.invoke(
                cli,
                ["version", "list", "--package", "backend"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "backend/VERSION" in result.output
            assert "frontend/VERSION" not in result.output

    def test_list_all_packages_returns_error_on_drift(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())
            Path("frontend/VERSION").write_text("9.9.9\n", encoding="utf-8")

            result = runner.invoke(
                cli,
                ["version", "list", "--all-packages"],
                catch_exceptions=False,
            )

            assert result.exit_code == 1, result.output
            assert "frontend/VERSION" in result.output
            assert "Some sources are out of sync" in result.output


class TestVersionCurrent:
    def test_current_shows_manifest_version(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_version_workspace(Path.cwd(), version="2.3.4")

            result = runner.invoke(
                cli,
                ["version", "current"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "2.3.4" in result.output

    def test_current_package_shows_selected_package_version(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            result = runner.invoke(
                cli,
                ["version", "current", "--package", "backend"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "1.0.0" in result.output
            assert "2.0.0" not in result.output

    def test_current_all_packages_shows_package_versions(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            result = runner.invoke(
                cli,
                ["version", "current", "--all-packages"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "Package current versions" in result.output
            assert "backend" in result.output
            assert "frontend" in result.output
            assert "1.0.0" in result.output
            assert "2.0.0" in result.output


class TestVersionInit:
    def test_init_scan_creates_synced_manifest_from_root_sources(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("VERSION").write_text("2.3.4\n", encoding="utf-8")

            result = runner.invoke(
                cli,
                ["version", "init", "--scan"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            manifest = yaml.safe_load(Path(".redeploy/version.yaml").read_text(encoding="utf-8"))
            assert manifest["version"]["version"] == "2.3.4"
            assert manifest["version"]["policy"] == "synced"
            assert manifest["version"]["sources"] == [
                {"path": "VERSION", "format": "plain", "optional": False}
            ]

    def test_init_scan_creates_independent_manifest_from_package_dirs(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("backend").mkdir(parents=True, exist_ok=True)
            Path("frontend").mkdir(parents=True, exist_ok=True)
            Path("backend/VERSION").write_text("1.0.0\n", encoding="utf-8")
            Path("frontend/package.json").write_text(
                '{"name": "frontend", "version": "2.0.0"}\n',
                encoding="utf-8",
            )

            result = runner.invoke(
                cli,
                ["version", "init", "--scan"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            manifest = yaml.safe_load(Path(".redeploy/version.yaml").read_text(encoding="utf-8"))
            assert manifest["version"]["policy"] == "independent"
            assert manifest["version"]["version"] == "0.0.0"
            assert manifest["version"].get("sources", []) == []
            assert manifest["version"]["packages"]["backend"]["version"] == "1.0.0"
            assert manifest["version"]["packages"]["backend"]["sources"] == [
                {"path": "backend/VERSION", "format": "plain", "optional": False}
            ]
            assert manifest["version"]["packages"]["frontend"]["version"] == "2.0.0"
            assert manifest["version"]["packages"]["frontend"]["sources"] == [
                {"path": "frontend/package.json", "format": "json", "key": "version", "optional": False}
            ]
            assert "Policy: independent" in result.output
            assert "Packages: 2" in result.output

    def test_init_scan_detects_regex_source_in_nested_package(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("packages/frontend/src").mkdir(parents=True, exist_ok=True)
            Path("packages/frontend/src/version.ts").write_text(
                'export const VERSION = "2.1.0"\n',
                encoding="utf-8",
            )

            result = runner.invoke(
                cli,
                ["version", "init", "--scan"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            manifest = yaml.safe_load(Path(".redeploy/version.yaml").read_text(encoding="utf-8"))
            assert manifest["version"]["policy"] == "independent"
            assert manifest["version"]["packages"]["frontend"]["version"] == "2.1.0"
            source = manifest["version"]["packages"]["frontend"]["sources"][0]
            assert source["path"] == "packages/frontend/src/version.ts"
            assert source["format"] == "regex"
            assert source["optional"] is False
            assert "VERSION" in source["pattern"]
            assert "const|let|var" in source["pattern"]

    def test_init_scan_reports_conflict_between_scanned_sources(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("backend/src").mkdir(parents=True, exist_ok=True)
            Path("backend/VERSION").write_text("1.0.0\n", encoding="utf-8")
            Path("backend/src/version.ts").write_text(
                'export const VERSION = "1.1.0"\n',
                encoding="utf-8",
            )

            result = runner.invoke(
                cli,
                ["version", "init", "--scan"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "Version conflict in backend" in result.output
            assert "backend/VERSION=1.0.0" in result.output
            assert "backend/src/version.ts=1.1.0" in result.output
            assert "using 1.0.0" in result.output

            manifest = yaml.safe_load(Path(".redeploy/version.yaml").read_text(encoding="utf-8"))
            assert manifest["version"]["packages"]["backend"]["version"] == "1.0.0"

    def test_init_scan_review_lists_detected_sources_without_writing_manifest(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("backend/src").mkdir(parents=True, exist_ok=True)
            Path("backend/VERSION").write_text("1.0.0\n", encoding="utf-8")
            Path("backend/src/version.ts").write_text(
                'export const VERSION = "1.1.0"\n',
                encoding="utf-8",
            )

            result = runner.invoke(
                cli,
                ["version", "init", "--scan", "--review"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "Scan review" in result.output
            assert "backend: chosen version 1.0.0 (conflict)" in result.output
            assert "backend/VERSION (plain) current: 1.0.0 confidence=certain" in result.output
            assert "backend/src/version.ts (regex) current: 1.1.0 confidence=heuristic" in result.output
            assert "conflict=yes" in result.output
            assert "Review only - manifest not written" in result.output
            assert not Path(".redeploy/version.yaml").exists()

    def test_init_scan_interactive_can_reject_source_and_write_manifest(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("backend/src").mkdir(parents=True, exist_ok=True)
            Path("backend/VERSION").write_text("1.0.0\n", encoding="utf-8")
            Path("backend/src/version.ts").write_text(
                'export const VERSION = "1.1.0"\n',
                encoding="utf-8",
            )

            result = runner.invoke(
                cli,
                ["version", "init", "--scan", "--interactive"],
                input="\nn\n\n",
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "Interactive scan review" in result.output
            assert "Keep backend/VERSION (plain) current=1.0.0 confidence=certain? [Y/n]:" in result.output
            assert "Keep backend/src/version.ts (regex) current=1.1.0 confidence=heuristic conflict=yes? [y/N]:" in result.output
            assert "Write manifest to .redeploy/version.yaml?" in result.output

            manifest = yaml.safe_load(Path(".redeploy/version.yaml").read_text(encoding="utf-8"))
            assert manifest["version"]["packages"]["backend"]["version"] == "1.0.0"
            assert manifest["version"]["packages"]["backend"]["sources"] == [
                {"path": "backend/VERSION", "format": "plain", "optional": False}
            ]

    def test_init_scan_interactive_rejects_heuristic_source_by_default(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("packages/frontend/src").mkdir(parents=True, exist_ok=True)
            Path("packages/frontend/src/version.ts").write_text(
                'export const VERSION = "2.1.0"\n',
                encoding="utf-8",
            )

            result = runner.invoke(
                cli,
                ["version", "init", "--scan", "--interactive"],
                input="\n",
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "Keep packages/frontend/src/version.ts (regex) current=2.1.0 confidence=heuristic? [y/N]:" in result.output
            assert "No sources selected - manifest not written" in result.output
            assert not Path(".redeploy/version.yaml").exists()

    def test_init_interactive_requires_scan(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                cli,
                ["version", "init", "--interactive"],
                catch_exceptions=False,
            )

            assert result.exit_code == 1, result.output
            assert "--review, --interactive and --exclude require --scan" in result.output

    def test_init_scan_exclude_omits_detected_source_from_manifest(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("backend/src").mkdir(parents=True, exist_ok=True)
            Path("backend/VERSION").write_text("1.0.0\n", encoding="utf-8")
            Path("backend/src/version.ts").write_text(
                'export const VERSION = "1.1.0"\n',
                encoding="utf-8",
            )

            result = runner.invoke(
                cli,
                [
                    "version",
                    "init",
                    "--scan",
                    "--exclude",
                    "backend/src/version.ts",
                ],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            manifest = yaml.safe_load(Path(".redeploy/version.yaml").read_text(encoding="utf-8"))
            assert manifest["version"]["packages"]["backend"]["version"] == "1.0.0"
            assert manifest["version"]["packages"]["backend"]["sources"] == [
                {"path": "backend/VERSION", "format": "plain", "optional": False}
            ]
            assert "Version conflict in backend" not in result.output


class TestVersionVerify:
    def test_verify_all_packages_succeeds_when_in_sync(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            result = runner.invoke(
                cli,
                ["version", "verify", "--all-packages"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "backend: All 1 sources in sync at 1.0.0" in result.output
            assert "frontend: All 1 sources in sync at 2.0.0" in result.output

    def test_verify_package_checks_only_selected_package(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            result = runner.invoke(
                cli,
                ["version", "verify", "--package", "backend"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "backend: All 1 sources in sync at 1.0.0" in result.output
            assert "frontend:" not in result.output

    def test_verify_all_packages_returns_error_on_drift(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())
            Path("frontend/VERSION").write_text("9.9.9\n", encoding="utf-8")

            result = runner.invoke(
                cli,
                ["version", "verify", "--all-packages"],
                catch_exceptions=False,
            )

            assert result.exit_code == 1, result.output
            assert "frontend: Version drift detected" in result.output
            assert "frontend/VERSION: expected 2.0.0, found 9.9.9" in result.output

    def test_set_all_packages_updates_all_packages(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            result = runner.invoke(
                cli,
                ["version", "set", "4.4.4", "--all-packages"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert Path("backend/VERSION").read_text(encoding="utf-8").strip() == "4.4.4"
            assert Path("frontend/VERSION").read_text(encoding="utf-8").strip() == "4.4.4"

            manifest = yaml.safe_load(Path(".redeploy/version.yaml").read_text(encoding="utf-8"))
            assert manifest["version"]["packages"]["backend"]["version"] == "4.4.4"
            assert manifest["version"]["packages"]["frontend"]["version"] == "4.4.4"

    def test_set_package_dry_run_does_not_modify_monorepo(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            result = runner.invoke(
                cli,
                ["version", "set", "5.5.5", "--package", "backend", "--dry-run"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "Would set backend: 1.0.0 → 5.5.5" in result.output
            assert Path("backend/VERSION").read_text(encoding="utf-8").strip() == "1.0.0"
            assert Path("frontend/VERSION").read_text(encoding="utf-8").strip() == "2.0.0"

    def test_set_package_with_commit_and_tag_uses_git_integration(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            with patch("redeploy.version.git_integration.GitIntegration.require_clean") as require_clean, \
                 patch("redeploy.version.git_integration.GitIntegration.commit", return_value="abcdef123456") as git_commit, \
                 patch(
                     "redeploy.version.git_integration.GitIntegration._run",
                     autospec=True,
                     return_value=subprocess.CompletedProcess(["git", "tag"], 0, "", ""),
                 ) as git_run:
                result = runner.invoke(
                    cli,
                    ["version", "set", "6.0.0", "--package", "backend", "--commit", "--tag"],
                    catch_exceptions=False,
                )

            assert result.exit_code == 0, result.output
            require_clean.assert_called_once()
            git_commit.assert_called_once()
            assert "Commit: abcdef12" in result.output
            assert "Tag: backend@v6.0.0" in result.output

            tag_call = git_run.call_args.args[1]
            assert tag_call[-1] == "backend@v6.0.0"

            commit_files = [str(path) for path in git_commit.call_args.args[1]]
            assert "backend/VERSION" in commit_files
            assert ".redeploy/version.yaml" in commit_files
            assert "frontend/VERSION" not in commit_files

    def test_set_all_packages_with_push_allow_dirty_skips_clean_check(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            with patch("redeploy.version.git_integration.GitIntegration.require_clean") as require_clean, \
                 patch("redeploy.version.git_integration.GitIntegration.commit", return_value="fedcba987654") as git_commit, \
                 patch(
                     "redeploy.version.git_integration.GitIntegration._run",
                     autospec=True,
                     return_value=subprocess.CompletedProcess(["git"], 0, "", ""),
                 ) as git_run:
                result = runner.invoke(
                    cli,
                    ["version", "set", "7.0.0", "--all-packages", "--push", "--allow-dirty"],
                    catch_exceptions=False,
                )

            assert result.exit_code == 0, result.output
            require_clean.assert_not_called()
            git_commit.assert_called_once()
            run_commands = [call.args[1] for call in git_run.call_args_list]
            tag_commands = [cmd for cmd in run_commands if cmd and cmd[0] == "tag"]
            assert [cmd[-1] for cmd in tag_commands] == ["backend@v7.0.0", "frontend@v7.0.0"]
            assert [cmd for cmd in run_commands if cmd[:2] == ["push", "--follow-tags"]] == [
                ["push", "--follow-tags", "origin"]
            ]
            assert "Tag: backend@v7.0.0" in result.output
            assert "Tag: frontend@v7.0.0" in result.output
            assert "Pushed to origin" in result.output

            commit_files = [str(path) for path in git_commit.call_args.args[1]]
            assert "backend/VERSION" in commit_files
            assert "frontend/VERSION" in commit_files
            assert ".redeploy/version.yaml" in commit_files

    def test_set_all_packages_changelog_skips_global_default_without_package_configs(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            result = runner.invoke(
                cli,
                ["version", "set", "8.0.0", "--all-packages", "--changelog"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "Skipping changelog for backend" in result.output
            assert "Skipping changelog for frontend" in result.output
            assert not Path("CHANGELOG.md").exists()

    def test_set_all_packages_changelog_updates_package_changelogs(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd(), with_package_changelogs=True)

            result = runner.invoke(
                cli,
                ["version", "set", "8.1.0", "--all-packages", "--changelog"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            backend_changelog = Path("backend/CHANGELOG.md").read_text(encoding="utf-8")
            frontend_changelog = Path("frontend/CHANGELOG.md").read_text(encoding="utf-8")
            assert "## [8.1.0]" in backend_changelog
            assert "## [8.1.0]" in frontend_changelog
            assert "backend pending" in backend_changelog
            assert "frontend pending" in frontend_changelog
            assert "Updated backend/CHANGELOG.md for backend" in result.output
            assert "Updated frontend/CHANGELOG.md for frontend" in result.output
            assert not Path("CHANGELOG.md").exists()


class TestVersionBump:
    def test_bump_package_with_tag_uses_package_tag_format(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            with patch("redeploy.version.git_integration.GitIntegration.require_clean") as require_clean, \
                 patch("redeploy.version.git_integration.GitIntegration.commit", return_value="112233445566") as git_commit, \
                 patch(
                     "redeploy.version.git_integration.GitIntegration._run",
                     autospec=True,
                     return_value=subprocess.CompletedProcess(["git", "tag"], 0, "", ""),
                 ) as git_run:
                result = runner.invoke(
                    cli,
                    ["version", "bump", "patch", "--package", "backend", "--commit", "--tag"],
                    catch_exceptions=False,
                )

            assert result.exit_code == 0, result.output
            require_clean.assert_called_once()
            git_commit.assert_called_once()
            assert "Tag: backend@v1.0.1" in result.output

            tag_call = git_run.call_args.args[1]
            assert tag_call[-1] == "backend@v1.0.1"
            assert Path("backend/VERSION").read_text(encoding="utf-8").strip() == "1.0.1"
            assert Path("frontend/VERSION").read_text(encoding="utf-8").strip() == "2.0.0"

            manifest = yaml.safe_load(Path(".redeploy/version.yaml").read_text(encoding="utf-8"))
            assert manifest["version"]["packages"]["backend"]["version"] == "1.0.1"
            assert manifest["version"]["packages"]["frontend"]["version"] == "2.0.0"

    def test_bump_all_packages_changelog_updates_package_changelogs(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd(), with_package_changelogs=True)

            result = runner.invoke(
                cli,
                ["version", "bump", "patch", "--all-packages", "--changelog"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            backend_changelog = Path("backend/CHANGELOG.md").read_text(encoding="utf-8")
            frontend_changelog = Path("frontend/CHANGELOG.md").read_text(encoding="utf-8")
            assert "## [1.0.1]" in backend_changelog
            assert "## [2.0.1]" in frontend_changelog
            assert "Updated backend/CHANGELOG.md for backend" in result.output
            assert "Updated frontend/CHANGELOG.md for frontend" in result.output
            assert not Path("CHANGELOG.md").exists()


class TestVersionDiff:
    def test_diff_all_packages_shows_package_source_status(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())

            result = runner.invoke(
                cli,
                ["version", "diff", "--all-packages"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, result.output
            assert "backend" in result.output
            assert "frontend" in result.output
            assert "All 1 sources in sync at 1.0.0" in result.output
            assert "All 1 sources in sync at 2.0.0" in result.output
            assert "No version drift detected" in result.output

    def test_diff_package_spec_mismatch_returns_nonzero(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())
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
                ["version", "diff", "--package", "backend", "--spec", "migration.yaml"],
                catch_exceptions=False,
            )

            assert result.exit_code == 1, result.output
            assert "backend" in result.output
            assert "spec: 1.0.9" in result.output
            assert "Version drift detected" in result.output

    def test_diff_all_packages_rejects_spec_without_package(self, tmp_path):
        runner = _runner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            _write_monorepo_version_workspace(Path.cwd())
            Path("migration.yaml").write_text(
                """
name: test
target:
  version: "1.0.1"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            result = runner.invoke(
                cli,
                ["version", "diff", "--all-packages", "--spec", "migration.yaml"],
                catch_exceptions=False,
            )

            assert result.exit_code == 1, result.output
            assert "--spec/--live require --package for monorepo manifests" in result.output

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