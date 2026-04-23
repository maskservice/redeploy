"""Tests for redeploy.analyze.spec_analyzer checkers."""
from __future__ import annotations

from pathlib import Path

import pytest

from redeploy.analyze.spec_analyzer import (
    AnalysisResult,
    IssueSeverity,
    SpecAnalyzer,
    _DockerBuildChecker,
    _IgnoreList,
    ensure_redeployignore,
)
from redeploy.models import DeployStrategy, InfraSpec, MigrationSpec


def _spec_with_steps(extra_steps: list[dict]) -> MigrationSpec:
    target = InfraSpec(
        strategy=DeployStrategy.DOCKER_FULL,
        host="pi@10.0.0.1",
        app="test",
        version="1.0.0",
        remote_dir="~/test",
    )
    source = InfraSpec(strategy=DeployStrategy.DOCKER_FULL, host="pi@10.0.0.1")
    return MigrationSpec(name="t", source=source, target=target, extra_steps=extra_steps)


class TestDockerBuildChecker:
    def test_missing_dockerfile_error(self, tmp_path: Path):
        spec = _spec_with_steps([
            {
                "id": "build_cql",
                "action": "ssh_cmd",
                "command": "docker build -f Dockerfile.rpi5 ~/c2004/oqlos/cql/",
            },
        ])
        result = AnalysisResult()
        _DockerBuildChecker().check(spec, None, tmp_path, result)
        assert not result.passed
        err = result.errors()[0]
        assert "Dockerfile.rpi5" in err.message
        assert "missing Dockerfile" in err.message

    def test_standard_dockerfile_ok(self, tmp_path: Path):
        (tmp_path / "Dockerfile").write_text("FROM alpine\n")
        spec = _spec_with_steps([
            {
                "id": "build",
                "action": "ssh_cmd",
                "command": "docker build -f Dockerfile ~/test/",
            },
        ])
        result = AnalysisResult()
        _DockerBuildChecker().check(spec, None, tmp_path, result)
        assert result.passed
        assert len(result.issues) == 0

    def test_nonstandard_dockerfile_warning(self, tmp_path: Path):
        (tmp_path / "Dockerfile.custom").write_text("FROM alpine\n")
        spec = _spec_with_steps([
            {
                "id": "build",
                "action": "ssh_cmd",
                "command": "docker build -f Dockerfile.custom .",
            },
        ])
        result = AnalysisResult()
        _DockerBuildChecker().check(spec, None, tmp_path, result)
        assert result.passed  # warning, not error
        assert len(result.warnings()) == 1
        assert "non-standard Dockerfile name" in result.warnings()[0].message

    def test_context_mismatch_with_sync_dest(self, tmp_path: Path):
        spec = _spec_with_steps([
            {
                "id": "sync_oqlos_cql",
                "action": "rsync",
                "src": "./oqlos/cql/",
                "dst": "~/oqlos/cql/",
            },
            {
                "id": "build_cql",
                "action": "ssh_cmd",
                "command": "docker build -f Dockerfile ~/c2004/oqlos/cql/",
            },
        ])
        result = AnalysisResult()
        _DockerBuildChecker().check(spec, None, tmp_path, result)
        warns = result.warnings()
        assert any("doesn't match any sync destination" in w.message for w in warns)

    def test_context_matches_sync_dest_no_warning(self, tmp_path: Path):
        (tmp_path / "Dockerfile").write_text("FROM alpine\n")
        spec = _spec_with_steps([
            {
                "id": "sync_oqlos_cql",
                "action": "rsync",
                "src": "./oqlos/cql/",
                "dst": "~/oqlos/cql/",
            },
            {
                "id": "build_cql",
                "action": "ssh_cmd",
                "command": "docker build -f Dockerfile ~/oqlos/cql/",
            },
        ])
        result = AnalysisResult()
        _DockerBuildChecker().check(spec, None, tmp_path, result)
        # No context mismatch warning
        assert not any("doesn't match any sync destination" in w.message for w in result.warnings())


class TestIgnoreList:
    def test_simple_filename_pattern(self, tmp_path: Path):
        (tmp_path / ".redeployignore").write_text("*.pyc\n")
        ign = _IgnoreList(tmp_path)
        assert ign.is_ignored(Path("foo.pyc"))
        assert not ign.is_ignored(Path("foo.py"))

    def test_directory_pattern(self, tmp_path: Path):
        (tmp_path / ".redeployignore").write_text("__pycache__/\n")
        ign = _IgnoreList(tmp_path)
        assert ign.is_ignored(Path("__pycache__"))
        assert ign.is_ignored(Path("src/__pycache__"))

    def test_gitignore_and_redeployignore_combined(self, tmp_path: Path):
        (tmp_path / ".gitignore").write_text("node_modules/\n")
        (tmp_path / ".redeployignore").write_text("*.log\n")
        ign = _IgnoreList(tmp_path)
        assert ign.is_ignored(Path("node_modules"))
        assert ign.is_ignored(Path("debug.log"))
        assert not ign.is_ignored(Path("app.py"))

    def test_missing_ignore_files(self, tmp_path: Path):
        ign = _IgnoreList(tmp_path)
        assert not ign.is_ignored(Path("anything"))


class TestEnsureRedeployignore:
    def test_creates_file_when_missing(self, tmp_path: Path):
        ensure_redeployignore(tmp_path)
        path = tmp_path / ".redeployignore"
        assert path.exists()
        content = path.read_text()
        assert ".git/" in content
        assert "__pycache__/" in content

    def test_does_not_overwrite_existing(self, tmp_path: Path):
        (tmp_path / ".redeployignore").write_text("custom\n")
        ensure_redeployignore(tmp_path)
        assert (tmp_path / ".redeployignore").read_text() == "custom\n"


class TestSpecAnalyzerIntegration:
    def test_analyze_file_markpact(self, tmp_path: Path):
        md = tmp_path / "migration.md"
        md.write_text(
            "# migration\n\n"
            "```yaml markpact:config\n"
            "name: test\n"
            "source:\n"
            "  strategy: docker_full\n"
            "  host: pi@10.0.0.1\n"
            "target:\n"
            "  strategy: docker_full\n"
            "  host: pi@10.0.0.1\n"
            "  app: test\n"
            "  version: 1.0.0\n"
            "  remote_dir: ~/test\n"
            "extra_steps:\n"
            "  - id: build\n"
            "    action: ssh_cmd\n"
            "    command: docker build -f Dockerfile.rpi5 .\n"
            "```\n"
        )
        analyzer = SpecAnalyzer(base_dir=tmp_path)
        spec, result = analyzer.analyze_file(md)
        assert spec is not None
        assert not result.passed
        assert any("Dockerfile.rpi5" in i.message for i in result.errors())

    def test_ignored_files_not_reported_as_missing(self, tmp_path: Path):
        (tmp_path / ".redeployignore").write_text("ignored_file.txt\n")
        spec = _spec_with_steps([
            {"id": "sync", "action": "rsync", "src": "ignored_file.txt", "dst": "~/remote/"},
        ])
        analyzer = SpecAnalyzer(base_dir=tmp_path, auto_create_redeployignore=False)
        result = analyzer.analyze(spec)
        assert result.passed  # should not report ignored_file.txt as missing
        assert len(result.errors()) == 0
