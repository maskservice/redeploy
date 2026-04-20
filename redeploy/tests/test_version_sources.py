"""Tests for redeploy.version.sources — all format adapters."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from redeploy.version.sources import get_adapter, register_adapter
from redeploy.version.sources.plain import PlainAdapter
from redeploy.version.sources.json_ import JsonAdapter
from redeploy.version.sources.toml_ import TomlAdapter
from redeploy.version.sources.yaml_ import YamlAdapter
from redeploy.version.sources.regex import RegexAdapter
from redeploy.version.manifest import SourceConfig


# ── helpers ───────────────────────────────────────────────────────────────────


def src(path: Path, fmt: str, key: str = None, pattern: str = None,
        optional: bool = False, value_pattern: str = None,
        write_pattern: str = None) -> SourceConfig:
    return SourceConfig(
        path=path, format=fmt, key=key, pattern=pattern,
        optional=optional, value_pattern=value_pattern,
        write_pattern=write_pattern,
    )


# ── get_adapter ───────────────────────────────────────────────────────────────


class TestGetAdapter:
    def test_known_formats(self):
        for fmt in ("plain", "toml", "json", "yaml", "regex"):
            a = get_adapter(fmt)
            assert a.format_name == fmt

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown source format"):
            get_adapter("nosuchformat")

    def test_register_custom_adapter(self):
        class FakeAdapter:
            format_name = "fake"
            def read(self, *a): return "0.0.0"
            def write(self, *a): pass
            def stage(self, *a): return Path("/dev/null")

        register_adapter("fake", FakeAdapter())
        assert get_adapter("fake").format_name == "fake"


# ── PlainAdapter ──────────────────────────────────────────────────────────────


class TestPlainAdapter:
    def test_read_version(self, tmp_path):
        p = tmp_path / "VERSION"
        p.write_text("1.2.3\n")
        assert PlainAdapter().read(p, src(p, "plain")) == "1.2.3"

    def test_read_strips_whitespace(self, tmp_path):
        p = tmp_path / "VERSION"
        p.write_text("  2.0.0  \n")
        assert PlainAdapter().read(p, src(p, "plain")) == "2.0.0"

    def test_read_missing_raises(self, tmp_path):
        p = tmp_path / "NOPE"
        with pytest.raises(FileNotFoundError):
            PlainAdapter().read(p, src(p, "plain"))

    def test_read_missing_optional_returns_empty(self, tmp_path):
        p = tmp_path / "NOPE"
        result = PlainAdapter().read(p, src(p, "plain", optional=True))
        assert result == ""

    def test_stage_creates_temp_with_newline(self, tmp_path):
        p = tmp_path / "VERSION"
        p.write_text("1.0.0\n")
        temp = PlainAdapter().stage(p, src(p, "plain"), "1.0.1")
        assert temp.exists()
        assert temp.read_text().strip() == "1.0.1"
        temp.unlink()

    def test_write_updates_file(self, tmp_path):
        p = tmp_path / "VERSION"
        p.write_text("1.0.0\n")
        PlainAdapter().write(p, src(p, "plain"), "1.0.1")
        assert p.read_text().strip() == "1.0.1"

    def test_stage_is_in_same_directory(self, tmp_path):
        p = tmp_path / "VERSION"
        p.write_text("1.0.0\n")
        temp = PlainAdapter().stage(p, src(p, "plain"), "1.0.1")
        assert temp.parent == tmp_path
        temp.unlink()


# ── JsonAdapter ───────────────────────────────────────────────────────────────


class TestJsonAdapter:
    def _write_pkg(self, tmp_path: Path, data: dict) -> Path:
        p = tmp_path / "package.json"
        p.write_text(json.dumps(data, indent=2) + "\n")
        return p

    def test_read_top_level_key(self, tmp_path):
        p = self._write_pkg(tmp_path, {"version": "3.1.0", "name": "app"})
        assert JsonAdapter().read(p, src(p, "json", key="version")) == "3.1.0"

    def test_read_nested_key(self, tmp_path):
        p = self._write_pkg(tmp_path, {"meta": {"version": "2.0.0"}})
        assert JsonAdapter().read(p, src(p, "json", key="meta.version")) == "2.0.0"

    def test_read_missing_key_raises(self, tmp_path):
        p = self._write_pkg(tmp_path, {"name": "no-version"})
        with pytest.raises(KeyError):
            JsonAdapter().read(p, src(p, "json", key="version"))

    def test_read_non_string_raises(self, tmp_path):
        p = self._write_pkg(tmp_path, {"version": 123})
        with pytest.raises(TypeError):
            JsonAdapter().read(p, src(p, "json", key="version"))

    def test_read_with_value_pattern(self, tmp_path):
        p = self._write_pkg(tmp_path, {"image": "ghcr.io/app:v1.2.3"})
        result = JsonAdapter().read(
            p, src(p, "json", key="image", value_pattern=r":v(\d+\.\d+\.\d+)")
        )
        assert result == "1.2.3"

    def test_stage_updates_version(self, tmp_path):
        p = self._write_pkg(tmp_path, {"version": "1.0.0", "name": "app"})
        temp = JsonAdapter().stage(p, src(p, "json", key="version"), "1.0.1")
        data = json.loads(temp.read_text())
        assert data["version"] == "1.0.1"
        assert data["name"] == "app"
        temp.unlink()

    def test_stage_preserves_trailing_newline(self, tmp_path):
        p = self._write_pkg(tmp_path, {"version": "1.0.0"})
        temp = JsonAdapter().stage(p, src(p, "json", key="version"), "1.0.1")
        assert temp.read_text().endswith("\n")
        temp.unlink()

    def test_stage_with_write_pattern(self, tmp_path):
        p = self._write_pkg(tmp_path, {"image": "ghcr.io/app:v1.0.0"})
        temp = JsonAdapter().stage(
            p,
            src(p, "json", key="image", write_pattern="ghcr.io/app:v{version}"),
            "2.0.0",
        )
        data = json.loads(temp.read_text())
        assert data["image"] == "ghcr.io/app:v2.0.0"
        temp.unlink()

    def test_detect_indent_2(self, tmp_path):
        content = '{\n  "a": 1\n}\n'
        assert JsonAdapter()._detect_indent(content) == 2

    def test_detect_indent_4(self, tmp_path):
        content = '{\n    "a": 1\n}\n'
        assert JsonAdapter()._detect_indent(content) == 4

    def test_detect_indent_default(self):
        assert JsonAdapter()._detect_indent("{}") == 2


# ── TomlAdapter ───────────────────────────────────────────────────────────────


class TestTomlAdapter:
    def _write_toml(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "pyproject.toml"
        p.write_text(content)
        return p

    def test_read_project_version(self, tmp_path):
        p = self._write_toml(tmp_path, '[project]\nname = "app"\nversion = "1.5.0"\n')
        result = TomlAdapter().read(p, src(p, "toml", key="project.version"))
        assert result == "1.5.0"

    def test_read_missing_key_raises(self, tmp_path):
        p = self._write_toml(tmp_path, '[tool.poetry]\nname = "app"\n')
        with pytest.raises(KeyError):
            TomlAdapter().read(p, src(p, "toml", key="project.version"))

    def test_read_without_key_raises(self, tmp_path):
        p = self._write_toml(tmp_path, '[project]\nversion = "1.0.0"\n')
        with pytest.raises(ValueError, match="key"):
            TomlAdapter().read(p, src(p, "toml", key=None))

    def test_stage_updates_version(self, tmp_path):
        content = '[project]\nname = "app"\nversion = "1.0.0"\n'
        p = self._write_toml(tmp_path, content)
        temp = TomlAdapter().stage(p, src(p, "toml", key="project.version"), "1.1.0")
        assert 'version = "1.1.0"' in temp.read_text()
        temp.unlink()

    def test_stage_preserves_other_fields(self, tmp_path):
        content = '[project]\nname = "myapp"\nversion = "0.9.0"\n'
        p = self._write_toml(tmp_path, content)
        temp = TomlAdapter().stage(p, src(p, "toml", key="project.version"), "1.0.0")
        updated = temp.read_text()
        assert 'name = "myapp"' in updated
        temp.unlink()

    def test_stage_raises_when_key_not_found(self, tmp_path):
        p = self._write_toml(tmp_path, '[project]\nname = "app"\n')
        with pytest.raises(ValueError, match="Could not find"):
            TomlAdapter().stage(p, src(p, "toml", key="project.version"), "1.0.0")


# ── YamlAdapter ───────────────────────────────────────────────────────────────


class TestYamlAdapter:
    def _write_yaml(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "chart.yaml"
        p.write_text(content)
        return p

    def test_read_top_level(self, tmp_path):
        p = self._write_yaml(tmp_path, "version: '2.3.0'\nname: chart\n")
        assert YamlAdapter().read(p, src(p, "yaml", key="version")) == "2.3.0"

    def test_read_nested(self, tmp_path):
        p = self._write_yaml(tmp_path, "app:\n  version: '4.0.0'\n")
        assert YamlAdapter().read(p, src(p, "yaml", key="app.version")) == "4.0.0"

    def test_read_missing_key_raises(self, tmp_path):
        p = self._write_yaml(tmp_path, "name: chart\n")
        with pytest.raises(KeyError):
            YamlAdapter().read(p, src(p, "yaml", key="version"))

    def test_stage_updates_version(self, tmp_path):
        p = self._write_yaml(tmp_path, "version: '1.0.0'\nname: chart\n")
        temp = YamlAdapter().stage(p, src(p, "yaml", key="version"), "1.1.0")
        content = temp.read_text()
        assert "1.1.0" in content
        temp.unlink()

    def test_stage_preserves_other_keys(self, tmp_path):
        p = self._write_yaml(tmp_path, "version: '1.0.0'\nname: chart\n")
        temp = YamlAdapter().stage(p, src(p, "yaml", key="version"), "2.0.0")
        import yaml
        data = yaml.safe_load(temp.read_text())
        assert data["name"] == "chart"
        temp.unlink()

    def test_read_non_string_raises(self, tmp_path):
        p = self._write_yaml(tmp_path, "version: 1\n")
        with pytest.raises(TypeError, match="not a string"):
            YamlAdapter().read(p, src(p, "yaml", key="version"))


# ── RegexAdapter ──────────────────────────────────────────────────────────────


class TestRegexAdapter:
    def _write(self, tmp_path: Path, content: str, name: str = "file.txt") -> Path:
        p = tmp_path / name
        p.write_text(content)
        return p

    def test_read_version_from_source(self, tmp_path):
        p = self._write(tmp_path, '__version__ = "1.2.3"\n', "version.py")
        result = RegexAdapter().read(
            p, src(p, "regex", pattern=r'__version__\s*=\s*"([^"]+)"')
        )
        assert result == "1.2.3"

    def test_read_no_match_raises(self, tmp_path):
        p = self._write(tmp_path, "no version here\n")
        with pytest.raises(ValueError, match="did not match"):
            RegexAdapter().read(p, src(p, "regex", pattern=r'"(\d+\.\d+\.\d+)"'))

    def test_read_without_pattern_raises(self, tmp_path):
        p = self._write(tmp_path, "version = 1.0.0\n")
        with pytest.raises(ValueError, match="pattern"):
            RegexAdapter().read(p, src(p, "regex", pattern=None))

    def test_stage_replaces_capture_group(self, tmp_path):
        content = '__version__ = "1.0.0"\nother = "unchanged"\n'
        p = self._write(tmp_path, content, "module.py")
        temp = RegexAdapter().stage(
            p,
            src(p, "regex", pattern=r'__version__\s*=\s*"([^"]+)"'),
            "2.0.0",
        )
        updated = temp.read_text()
        assert "2.0.0" in updated
        assert 'other = "unchanged"' in updated
        temp.unlink()

    def test_stage_simple_version_line(self, tmp_path):
        content = 'version: "1.0.0"\n'
        p = self._write(tmp_path, content)
        temp = RegexAdapter().stage(
            p,
            src(p, "regex", pattern=r'version: "([^"]+)"'),
            "1.1.0",
        )
        assert "1.1.0" in temp.read_text()
        temp.unlink()

    def test_stage_no_match_raises(self, tmp_path):
        p = self._write(tmp_path, "no version here\n")
        with pytest.raises(ValueError, match="did not match"):
            RegexAdapter().stage(
                p,
                src(p, "regex", pattern=r'version:\s*"([^"]+)"'),
                "1.0.0",
            )

    def test_stage_no_capture_group_raises(self, tmp_path):
        p = self._write(tmp_path, 'version: "1.0.0"\n')
        with pytest.raises(ValueError, match="capture group"):
            RegexAdapter().stage(
                p,
                src(p, "regex", pattern=r'version: "[^"]+"'),
                "1.0.0",
            )


# ── VersionDiff (diff.py) ─────────────────────────────────────────────────────


class TestVersionDiff:
    def _manifest(self, version: str):
        from redeploy.version.manifest import VersionManifest
        return VersionManifest(version=version)

    def test_diff_manifest_vs_spec_match(self):
        from redeploy.version.diff import diff_manifest_vs_spec
        m = self._manifest("1.0.0")
        d = diff_manifest_vs_spec(m, "1.0.0")
        assert d.match is True
        assert d.source == "spec"

    def test_diff_manifest_vs_spec_mismatch(self):
        from redeploy.version.diff import diff_manifest_vs_spec
        m = self._manifest("1.0.0")
        d = diff_manifest_vs_spec(m, "0.9.0")
        assert d.match is False
        assert d.version == "0.9.0"
        assert d.expected == "1.0.0"

    def test_diff_manifest_vs_spec_at_manifest_ref(self):
        from redeploy.version.diff import diff_manifest_vs_spec
        m = self._manifest("2.5.0")
        d = diff_manifest_vs_spec(m, "@manifest")
        assert d.match is True
        assert "@manifest" in d.source

    def test_diff_manifest_vs_live_match(self):
        from redeploy.version.diff import diff_manifest_vs_live
        m = self._manifest("3.0.0")
        d = diff_manifest_vs_live(m, "3.0.0")
        assert d.match is True
        assert d.source == "live"

    def test_diff_manifest_vs_live_mismatch(self):
        from redeploy.version.diff import diff_manifest_vs_live
        m = self._manifest("3.0.0")
        d = diff_manifest_vs_live(m, "2.9.0")
        assert d.match is False

    def test_diff_manifest_vs_live_none(self):
        from redeploy.version.diff import diff_manifest_vs_live
        m = self._manifest("1.0.0")
        d = diff_manifest_vs_live(m, None)
        assert d.match is False
        assert d.error is not None

    def test_format_diff_report_all_ok(self):
        from redeploy.version.diff import VersionDiff, format_diff_report
        diffs = [
            VersionDiff(source="spec", version="1.0.0", expected="1.0.0", match=True),
            VersionDiff(source="live", version="1.0.0", expected="1.0.0", match=True),
        ]
        report = format_diff_report(diffs, "1.0.0")
        assert "All versions in sync" in report
        assert "1.0.0" in report

    def test_format_diff_report_with_mismatch(self):
        from redeploy.version.diff import VersionDiff, format_diff_report
        diffs = [
            VersionDiff(source="live", version="0.9.0", expected="1.0.0", match=False),
        ]
        report = format_diff_report(diffs, "1.0.0")
        assert "drift" in report
        assert "0.9.0" in report

    def test_format_diff_report_with_error(self):
        from redeploy.version.diff import VersionDiff, format_diff_report
        diffs = [
            VersionDiff(source="live", version=None, expected="1.0.0",
                        match=False, error="SSH timeout"),
        ]
        report = format_diff_report(diffs, "1.0.0")
        assert "SSH timeout" in report


# ── bump_package / bump_all_packages (monorepo) ───────────────────────────────


class TestBumpPackageMonorepo:
    def _make_manifest(self, tmp_path: Path) -> tuple:
        """Create a mini monorepo manifest with two packages."""
        backend_ver = tmp_path / "backend" / "VERSION"
        backend_ver.parent.mkdir()
        backend_ver.write_text("1.0.0\n")

        frontend_ver = tmp_path / "frontend" / "VERSION"
        frontend_ver.parent.mkdir()
        frontend_ver.write_text("2.0.0\n")

        from redeploy.version.manifest import (
            VersionManifest, PackageConfig, SourceConfig,
        )
        m = VersionManifest(
            version="0.0.0",  # root unused
            policy="independent",
            packages={
                "backend": PackageConfig(
                    version="1.0.0",
                    sources=[SourceConfig(path=backend_ver, format="plain")],
                ),
                "frontend": PackageConfig(
                    version="2.0.0",
                    sources=[SourceConfig(path=frontend_ver, format="plain")],
                ),
            },
        )
        return m, backend_ver, frontend_ver

    def test_is_monorepo_true(self, tmp_path):
        m, *_ = self._make_manifest(tmp_path)
        assert m.is_monorepo() is True

    def test_list_packages(self, tmp_path):
        m, *_ = self._make_manifest(tmp_path)
        pkgs = m.list_packages()
        assert "backend" in pkgs
        assert "frontend" in pkgs

    def test_get_package_existing(self, tmp_path):
        m, *_ = self._make_manifest(tmp_path)
        pkg = m.get_package("backend")
        assert pkg is not None
        assert pkg.version == "1.0.0"

    def test_get_package_missing_returns_none(self, tmp_path):
        m, *_ = self._make_manifest(tmp_path)
        assert m.get_package("nosuchpkg") is None

    def test_get_all_package_versions(self, tmp_path):
        m, *_ = self._make_manifest(tmp_path)
        versions = m.get_all_package_versions()
        assert versions == {"backend": "1.0.0", "frontend": "2.0.0"}

    def test_bump_package_patch(self, tmp_path):
        from redeploy.version.bump import bump_package
        m, backend_ver, _ = self._make_manifest(tmp_path)
        result = bump_package(m, "backend", "patch")
        assert result["new_version"] == "1.0.1"
        assert backend_ver.read_text().strip() == "1.0.1"
        assert m.get_package("backend").version == "1.0.1"

    def test_bump_package_minor(self, tmp_path):
        from redeploy.version.bump import bump_package
        m, _, frontend_ver = self._make_manifest(tmp_path)
        result = bump_package(m, "frontend", "minor")
        assert result["new_version"] == "2.1.0"
        assert frontend_ver.read_text().strip() == "2.1.0"

    def test_bump_package_unknown_raises(self, tmp_path):
        from redeploy.version.bump import bump_package
        m, *_ = self._make_manifest(tmp_path)
        with pytest.raises(KeyError, match="nosuchpkg"):
            bump_package(m, "nosuchpkg", "patch")

    def test_bump_package_result_keys(self, tmp_path):
        from redeploy.version.bump import bump_package
        m, *_ = self._make_manifest(tmp_path)
        result = bump_package(m, "backend", "major")
        assert "package" in result
        assert "old" in result
        assert "new_version" in result
        assert result["package"] == "backend"

    def test_bump_all_packages(self, tmp_path):
        from redeploy.version.bump import bump_all_packages
        m, backend_ver, frontend_ver = self._make_manifest(tmp_path)
        results = bump_all_packages(m, "patch")
        assert len(results) == 2
        assert backend_ver.read_text().strip() == "1.0.1"
        assert frontend_ver.read_text().strip() == "2.0.1"

    def test_bump_all_packages_not_monorepo_raises(self, tmp_path):
        from redeploy.version.bump import bump_all_packages
        from redeploy.version.manifest import VersionManifest
        m = VersionManifest(version="1.0.0")
        with pytest.raises(ValueError, match="not a monorepo"):

            bump_all_packages(m, "patch")

    def test_bump_package_independent_of_other(self, tmp_path):
        from redeploy.version.bump import bump_package
        m, backend_ver, frontend_ver = self._make_manifest(tmp_path)
        bump_package(m, "backend", "major")
        # frontend unchanged
        assert frontend_ver.read_text().strip() == "2.0.0"
