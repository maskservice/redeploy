"""Tests for redeploy.version — VersionManifest, bump_version, legacy utils."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from redeploy.version import (
    VersionManifest,
    SourceConfig,
    GitConfig,
    ChangelogConfig,
    bump_version,
    verify_sources,
    check_version,
    check_version_http,
    read_local_version,
)


# ── VersionManifest model ─────────────────────────────────────────────────────


class TestVersionManifest:
    def test_minimal_manifest(self):
        m = VersionManifest(version="1.0.0")
        assert m.version == "1.0.0"
        assert m.scheme == "semver"
        assert m.policy == "synced"
        assert m.sources == []

    def test_with_source(self, tmp_path):
        m = VersionManifest(
            version="1.2.3",
            sources=[SourceConfig(path=tmp_path / "VERSION", format="plain")],
        )
        assert len(m.sources) == 1
        assert m.sources[0].format == "plain"

    def test_git_config_defaults(self):
        m = VersionManifest(version="1.0.0")
        assert m.git.tag_format == "v{version}"
        assert m.git.require_clean is True

    def test_format_version(self):
        m = VersionManifest(version="1.0.0")
        assert m.format_version("1.2.3") == "v1.2.3"

    def test_format_version_custom(self):
        m = VersionManifest(
            version="1.0.0",
            git=GitConfig(tag_format="release-{version}"),
        )
        assert m.format_version("2.0.0") == "release-2.0.0"

    def test_load_from_file(self, tmp_path):
        f = tmp_path / "version.yaml"
        data = {
            "version": {
                "version": "3.1.4",
                "scheme": "semver",
                "sources": [],
            }
        }
        f.write_text(yaml.dump(data))
        m = VersionManifest.load(f)
        assert m.version == "3.1.4"

    def test_load_flat_format(self, tmp_path):
        f = tmp_path / "version.yaml"
        f.write_text(yaml.dump({"version": "2.0.1", "sources": []}))
        m = VersionManifest.load(f)
        assert m.version == "2.0.1"

    def test_load_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            VersionManifest.load(tmp_path / "nonexistent.yaml")

    def test_save_and_reload(self, tmp_path):
        f = tmp_path / "version.yaml"
        m = VersionManifest(version="1.5.0")
        m.save(f)
        m2 = VersionManifest.load(f)
        assert m2.version == "1.5.0"

    def test_get_source_paths(self, tmp_path):
        m = VersionManifest(
            version="1.0.0",
            sources=[
                SourceConfig(path=tmp_path / "VERSION"),
                SourceConfig(path=tmp_path / "pyproject.toml", format="toml",
                             key="tool.poetry.version"),
            ],
        )
        paths = m.get_source_paths()
        assert len(paths) == 2

    def test_source_config_accepts_toml_with_key(self, tmp_path):
        cfg = SourceConfig(path=tmp_path / "pyproject.toml", format="toml",
                           key="tool.poetry.version")
        assert cfg.key == "tool.poetry.version"

    def test_source_config_accepts_regex_with_pattern(self, tmp_path):
        cfg = SourceConfig(path=tmp_path / "file.txt", format="regex",
                           pattern=r'version = "(\d+\.\d+\.\d+)"')
        assert cfg.pattern is not None


# ── _calculate_bump (via bump_version) ────────────────────────────────────────


class TestCalculateBump:
    def _manifest(self, version: str, tmp_path: Path) -> VersionManifest:
        plain = tmp_path / "VERSION"
        plain.write_text(version + "\n")
        return VersionManifest(
            version=version,
            sources=[SourceConfig(path=plain, format="plain")],
        )

    def test_patch_bump(self, tmp_path):
        m = self._manifest("1.2.3", tmp_path)
        result = bump_version(m, "patch")
        assert m.version == "1.2.4"
        assert result["new_version"] == "1.2.4"
        assert result["sources"][0]["old"] == "1.2.3"

    def test_minor_bump(self, tmp_path):
        m = self._manifest("1.2.3", tmp_path)
        bump_version(m, "minor")
        assert m.version == "1.3.0"

    def test_major_bump(self, tmp_path):
        m = self._manifest("1.2.3", tmp_path)
        bump_version(m, "major")
        assert m.version == "2.0.0"

    def test_prerelease_bump_fresh(self, tmp_path):
        m = self._manifest("1.2.3", tmp_path)
        bump_version(m, "prerelease")
        assert m.version == "1.2.3-rc.1"

    def test_prerelease_bump_increment(self, tmp_path):
        m = self._manifest("1.2.3-rc.1", tmp_path)
        bump_version(m, "prerelease")
        assert m.version == "1.2.3-rc.2"

    def test_explicit_version(self, tmp_path):
        m = self._manifest("1.0.0", tmp_path)
        bump_version(m, "patch", new_version="9.9.9")
        assert m.version == "9.9.9"

    def test_invalid_bump_type(self, tmp_path):
        m = self._manifest("1.0.0", tmp_path)
        with pytest.raises(ValueError, match="Unknown bump type"):
            bump_version(m, "bogus")

    def test_non_semver_raises(self, tmp_path):
        plain = tmp_path / "VERSION"
        plain.write_text("1.0\n")
        m = VersionManifest(
            version="1.0",
            sources=[SourceConfig(path=plain, format="plain")],
        )
        with pytest.raises(ValueError, match="Cannot bump non-semver"):
            bump_version(m, "patch")

    def test_file_updated_after_bump(self, tmp_path):
        plain = tmp_path / "VERSION"
        plain.write_text("1.0.0\n")
        m = VersionManifest(
            version="1.0.0",
            sources=[SourceConfig(path=plain, format="plain")],
        )
        bump_version(m, "patch")
        assert plain.read_text().strip() == "1.0.1"


# ── verify_sources ────────────────────────────────────────────────────────────


class TestVerifySources:
    def test_all_match(self, tmp_path):
        plain = tmp_path / "VERSION"
        plain.write_text("1.0.0\n")
        m = VersionManifest(
            version="1.0.0",
            sources=[SourceConfig(path=plain, format="plain")],
        )
        r = verify_sources(m)
        assert r["all_match"] is True
        assert r["sources"][0]["match"] is True

    def test_mismatch(self, tmp_path):
        plain = tmp_path / "VERSION"
        plain.write_text("0.9.0\n")
        m = VersionManifest(
            version="1.0.0",
            sources=[SourceConfig(path=plain, format="plain")],
        )
        r = verify_sources(m)
        assert r["all_match"] is False
        assert r["sources"][0]["actual"] == "0.9.0"

    def test_missing_optional_file(self, tmp_path):
        m = VersionManifest(
            version="1.0.0",
            sources=[SourceConfig(
                path=tmp_path / "MISSING",
                format="plain",
                optional=True,
            )],
        )
        r = verify_sources(m)
        assert r["sources"][0]["ok"] is True


# ── PlainAdapter (sources/plain) ──────────────────────────────────────────────


class TestPlainAdapter:
    def test_read_write(self, tmp_path):
        from redeploy.version.sources.plain import PlainAdapter
        from redeploy.version.manifest import SourceConfig

        p = tmp_path / "VERSION"
        p.write_text("1.0.0\n")
        cfg = SourceConfig(path=p, format="plain")
        adapter = PlainAdapter()

        assert adapter.read(p, cfg) == "1.0.0"
        adapter.write(p, cfg, "1.0.1")
        assert p.read_text().strip() == "1.0.1"

    def test_read_optional_missing(self, tmp_path):
        from redeploy.version.sources.plain import PlainAdapter
        from redeploy.version.manifest import SourceConfig

        p = tmp_path / "MISSING"
        cfg = SourceConfig(path=p, format="plain", optional=True)
        adapter = PlainAdapter()
        assert adapter.read(p, cfg) == ""


# ── VersionBumpTransaction ────────────────────────────────────────────────────


class TestVersionBumpTransaction:
    def test_prepare_commit(self, tmp_path):
        from redeploy.version.transaction import VersionBumpTransaction

        plain = tmp_path / "VERSION"
        plain.write_text("1.0.0\n")
        m = VersionManifest(
            version="1.0.0",
            sources=[SourceConfig(path=plain, format="plain")],
        )
        tx = VersionBumpTransaction(m, "1.0.1")
        results = tx.prepare()
        assert all(r.ok for r in results)
        tx.commit()
        assert plain.read_text().strip() == "1.0.1"

    def test_rollback_cleans_temp_files(self, tmp_path):
        from redeploy.version.transaction import VersionBumpTransaction

        plain = tmp_path / "VERSION"
        plain.write_text("1.0.0\n")
        m = VersionManifest(
            version="1.0.0",
            sources=[SourceConfig(path=plain, format="plain")],
        )
        tx = VersionBumpTransaction(m, "1.0.1")
        tx.prepare()
        tx.rollback()
        assert plain.read_text().strip() == "1.0.0"


# ── Legacy functions (backward compat) ───────────────────────────────────────


class TestLegacyFunctions:
    def test_read_local_version_from_root(self, tmp_path):
        (tmp_path / "VERSION").write_text("2.3.4\n")
        assert read_local_version(tmp_path) == "2.3.4"

    def test_read_local_version_from_app_subdir(self, tmp_path):
        app_dir = tmp_path / "myapp"
        app_dir.mkdir()
        (app_dir / "VERSION").write_text("5.0.0\n")
        assert read_local_version(tmp_path, "myapp") == "5.0.0"

    def test_read_local_version_missing(self, tmp_path):
        assert read_local_version(tmp_path) is None

    def test_check_version_match(self):
        ok, detail = check_version("1.0.0", "1.0.0")
        assert ok is True
        assert "✓" in detail

    def test_check_version_mismatch(self):
        ok, detail = check_version("1.0.0", "0.9.0")
        assert ok is False
        assert "MISMATCH" in detail

    def test_check_version_no_local(self):
        ok, detail = check_version(None, "1.0.0")
        assert ok is True
        assert "skip" in detail.lower()

    def test_check_version_no_remote(self):
        ok, detail = check_version("1.0.0", None)
        assert ok is False
        assert "not found" in detail

    def test_check_version_http_unreachable(self):
        ok, detail, payload = check_version_http("http://localhost:19999")
        assert ok is False
        assert "unreachable" in detail
        assert payload == {}


# ── JsonAdapter ───────────────────────────────────────────────────────────────


class TestJsonAdapter:
    def test_read_simple_key(self, tmp_path):
        from redeploy.version.sources.json_ import JsonAdapter

        p = tmp_path / "package.json"
        p.write_text('{"version": "1.2.3", "name": "myapp"}\n')
        cfg = SourceConfig(path=p, format="json", key="version")
        assert JsonAdapter().read(p, cfg) == "1.2.3"

    def test_read_nested_key(self, tmp_path):
        from redeploy.version.sources.json_ import JsonAdapter
        import json

        p = tmp_path / "config.json"
        p.write_text(json.dumps({"app": {"version": "3.0.0"}}))
        cfg = SourceConfig(path=p, format="json", key="app.version")
        assert JsonAdapter().read(p, cfg) == "3.0.0"

    def test_write_updates_version(self, tmp_path):
        from redeploy.version.sources.json_ import JsonAdapter
        import json

        p = tmp_path / "package.json"
        p.write_text('{\n  "version": "1.0.0",\n  "name": "app"\n}\n')
        cfg = SourceConfig(path=p, format="json", key="version")
        JsonAdapter().write(p, cfg, "1.0.1")
        data = json.loads(p.read_text())
        assert data["version"] == "1.0.1"

    def test_write_preserves_other_fields(self, tmp_path):
        from redeploy.version.sources.json_ import JsonAdapter
        import json

        p = tmp_path / "package.json"
        p.write_text('{\n  "name": "myapp",\n  "version": "1.0.0"\n}\n')
        cfg = SourceConfig(path=p, format="json", key="version")
        JsonAdapter().write(p, cfg, "2.0.0")
        data = json.loads(p.read_text())
        assert data["name"] == "myapp"
        assert data["version"] == "2.0.0"

    def test_read_missing_key_raises(self, tmp_path):
        from redeploy.version.sources.json_ import JsonAdapter

        p = tmp_path / "package.json"
        p.write_text('{"name": "app"}')
        cfg = SourceConfig(path=p, format="json", key="version")
        with pytest.raises(KeyError):
            JsonAdapter().read(p, cfg)

    def test_write_pattern(self, tmp_path):
        from redeploy.version.sources.json_ import JsonAdapter
        import json

        p = tmp_path / "conf.json"
        p.write_text('{"image": "ghcr.io/app:v1.0.0"}\n')
        cfg = SourceConfig(
            path=p, format="json", key="image",
            write_pattern="ghcr.io/app:v{version}",
        )
        JsonAdapter().write(p, cfg, "2.0.0")
        data = json.loads(p.read_text())
        assert data["image"] == "ghcr.io/app:v2.0.0"


# ── TomlAdapter ────────────────────────────────────────────────────────────────


class TestTomlAdapter:
    def test_read_pyproject(self, tmp_path):
        from redeploy.version.sources.toml_ import TomlAdapter

        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\nname = "myapp"\nversion = "1.5.0"\n')
        cfg = SourceConfig(path=p, format="toml", key="project.version")
        assert TomlAdapter().read(p, cfg) == "1.5.0"

    def test_write_pyproject(self, tmp_path):
        from redeploy.version.sources.toml_ import TomlAdapter

        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\nname = "myapp"\nversion = "1.5.0"\n')
        cfg = SourceConfig(path=p, format="toml", key="project.version")
        TomlAdapter().write(p, cfg, "1.6.0")
        assert '1.6.0' in p.read_text()

    def test_write_preserves_other_content(self, tmp_path):
        from redeploy.version.sources.toml_ import TomlAdapter

        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\nname = "myapp"\nversion = "1.0.0"\n\n[build-system]\nrequires = ["setuptools"]\n')
        cfg = SourceConfig(path=p, format="toml", key="project.version")
        TomlAdapter().write(p, cfg, "2.0.0")
        content = p.read_text()
        assert "setuptools" in content
        assert "myapp" in content

    def test_read_missing_key_raises(self, tmp_path):
        from redeploy.version.sources.toml_ import TomlAdapter

        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\nname = "myapp"\n')
        cfg = SourceConfig(path=p, format="toml", key="project.version")
        with pytest.raises(KeyError):
            TomlAdapter().read(p, cfg)

    def test_stage_without_commit(self, tmp_path):
        from redeploy.version.sources.toml_ import TomlAdapter

        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\nversion = "1.0.0"\n')
        cfg = SourceConfig(path=p, format="toml", key="project.version")
        temp = TomlAdapter().stage(p, cfg, "1.1.0")
        assert temp.exists()
        assert "1.1.0" in temp.read_text()
        assert p.read_text().startswith("[project]")
        temp.unlink()


# ── YamlAdapter ────────────────────────────────────────────────────────────────


class TestYamlAdapter:
    def test_read_simple_key(self, tmp_path):
        from redeploy.version.sources.yaml_ import YamlAdapter

        p = tmp_path / "Chart.yaml"
        p.write_text('appVersion: "1.0.0"\nname: myapp\n')
        cfg = SourceConfig(path=p, format="yaml", key="appVersion")
        assert YamlAdapter().read(p, cfg) == "1.0.0"

    def test_write_simple_key(self, tmp_path):
        from redeploy.version.sources.yaml_ import YamlAdapter

        p = tmp_path / "Chart.yaml"
        p.write_text('appVersion: "1.0.0"\nname: myapp\n')
        cfg = SourceConfig(path=p, format="yaml", key="appVersion")
        YamlAdapter().write(p, cfg, "2.0.0")
        assert '"2.0.0"' in p.read_text()

    def test_read_with_value_pattern(self, tmp_path):
        from redeploy.version.sources.yaml_ import YamlAdapter

        p = tmp_path / "values.yaml"
        p.write_text('image: "ghcr.io/app:v1.2.3"\n')
        cfg = SourceConfig(
            path=p, format="yaml", key="image",
            value_pattern=r".*:v?(.+)",
        )
        result = YamlAdapter().read(p, cfg)
        assert result == "1.2.3"

    def test_write_with_write_pattern(self, tmp_path):
        from redeploy.version.sources.yaml_ import YamlAdapter

        p = tmp_path / "values.yaml"
        p.write_text('image: ghcr.io/app:v1.0.0\n')
        cfg = SourceConfig(
            path=p, format="yaml", key="image",
            write_pattern="ghcr.io/app:v{version}",
        )
        YamlAdapter().write(p, cfg, "2.0.0")
        assert "ghcr.io/app:v2.0.0" in p.read_text()

    def test_read_missing_key_raises(self, tmp_path):
        from redeploy.version.sources.yaml_ import YamlAdapter

        p = tmp_path / "Chart.yaml"
        p.write_text('name: myapp\n')
        cfg = SourceConfig(path=p, format="yaml", key="appVersion")
        with pytest.raises(KeyError):
            YamlAdapter().read(p, cfg)

    def test_read_optional_missing(self, tmp_path):
        from redeploy.version.sources.yaml_ import YamlAdapter

        p = tmp_path / "helm" / "Chart.yaml"
        cfg = SourceConfig(path=p, format="yaml", key="appVersion", optional=True)
        assert YamlAdapter().read(p, cfg) == ""


# ── RegexAdapter ───────────────────────────────────────────────────────────────


class TestRegexAdapter:
    def test_read_python_version(self, tmp_path):
        from redeploy.version.sources.regex import RegexAdapter

        p = tmp_path / "__init__.py"
        p.write_text('"""Module."""\n__version__ = "1.2.3"\n')
        cfg = SourceConfig(
            path=p, format="regex",
            pattern=r'__version__\s*=\s*"([^"]+)"',
        )
        assert RegexAdapter().read(p, cfg) == "1.2.3"

    def test_read_const_version(self, tmp_path):
        from redeploy.version.sources.regex import RegexAdapter

        p = tmp_path / "version.ts"
        p.write_text('export const VERSION = "3.0.0";\n')
        cfg = SourceConfig(
            path=p, format="regex",
            pattern=r'VERSION\s*=\s*"([^"]+)"',
        )
        assert RegexAdapter().read(p, cfg) == "3.0.0"

    def test_write_replaces_version(self, tmp_path):
        from redeploy.version.sources.regex import RegexAdapter

        p = tmp_path / "__init__.py"
        p.write_text('__version__ = "1.0.0"\nAPP = "app"\n')
        cfg = SourceConfig(
            path=p, format="regex",
            pattern=r'__version__\s*=\s*"([^"]+)"',
        )
        RegexAdapter().write(p, cfg, "1.1.0")
        content = p.read_text()
        assert '"1.1.0"' in content
        assert "APP" in content

    def test_read_no_match_raises(self, tmp_path):
        from redeploy.version.sources.regex import RegexAdapter

        p = tmp_path / "file.py"
        p.write_text("# no version here\n")
        cfg = SourceConfig(
            path=p, format="regex",
            pattern=r'__version__\s*=\s*"([^"]+)"',
        )
        with pytest.raises(ValueError, match="did not match"):
            RegexAdapter().read(p, cfg)

    def test_write_no_match_raises(self, tmp_path):
        from redeploy.version.sources.regex import RegexAdapter

        p = tmp_path / "file.py"
        p.write_text("# no version here\n")
        cfg = SourceConfig(
            path=p, format="regex",
            pattern=r'__version__\s*=\s*"([^"]+)"',
        )
        with pytest.raises(ValueError, match="did not match"):
            RegexAdapter().write(p, cfg, "1.0.0")

    def test_stage_does_not_modify_original(self, tmp_path):
        from redeploy.version.sources.regex import RegexAdapter

        p = tmp_path / "__init__.py"
        p.write_text('__version__ = "1.0.0"\n')
        cfg = SourceConfig(
            path=p, format="regex",
            pattern=r'__version__\s*=\s*"([^"]+)"',
        )
        temp = RegexAdapter().stage(p, cfg, "2.0.0")
        assert '"2.0.0"' in temp.read_text()
        assert '"1.0.0"' in p.read_text()
        temp.unlink()


# ── Integration: c2004-style manifest ─────────────────────────────────────────


class TestC2004StyleManifest:
    """Integration tests mirroring c2004/.redeploy/version.yaml structure."""

    def test_multi_source_manifest(self, tmp_path):
        import json

        version_file = tmp_path / "VERSION"
        version_file.write_text("1.0.20\n")
        pkg_json = tmp_path / "package.json"
        pkg_json.write_text('{\n  "version": "1.0.20"\n}\n')

        m = VersionManifest(
            version="1.0.20",
            sources=[
                SourceConfig(path=version_file, format="plain"),
                SourceConfig(path=pkg_json, format="json", key="version"),
            ],
        )
        r = verify_sources(m)
        assert r["all_match"] is True
        assert len(r["sources"]) == 2

    def test_bump_multiple_sources(self, tmp_path):
        import json

        version_file = tmp_path / "VERSION"
        version_file.write_text("1.0.20\n")
        pkg_json = tmp_path / "package.json"
        pkg_json.write_text('{\n  "version": "1.0.20"\n}\n')
        init_py = tmp_path / "__init__.py"
        init_py.write_text('__version__ = "1.0.20"\n')

        m = VersionManifest(
            version="1.0.20",
            sources=[
                SourceConfig(path=version_file, format="plain"),
                SourceConfig(path=pkg_json, format="json", key="version"),
                SourceConfig(
                    path=init_py, format="regex",
                    pattern=r'__version__\s*=\s*"([^"]+)"',
                ),
            ],
        )
        bump_version(m, "patch")

        assert version_file.read_text().strip() == "1.0.21"
        assert json.loads(pkg_json.read_text())["version"] == "1.0.21"
        assert '"1.0.21"' in init_py.read_text()
        assert m.version == "1.0.21"

    def test_load_from_c2004_style_yaml(self, tmp_path):
        """VersionManifest.load() handles nested version: { version: ... } format."""
        f = tmp_path / "version.yaml"
        f.write_text("""\
version:
  version: "1.0.20"
  scheme: semver
  policy: synced
  sources:
    - path: VERSION
      format: plain
  git:
    tag_format: "v{version}"
    require_clean: true
""")
        m = VersionManifest.load(f)
        assert m.version == "1.0.20"
        assert m.git.tag_format == "v{version}"
        assert len(m.sources) == 1
