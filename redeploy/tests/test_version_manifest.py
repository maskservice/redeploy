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
