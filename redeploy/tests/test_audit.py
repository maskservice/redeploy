"""Tests for redeploy.audit — spec-vs-host expectation analyzer."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from redeploy.audit import (
    AuditCheck,
    AuditReport,
    Auditor,
    _Extractor,
    _extract_port,
    audit_spec,
)
from redeploy.models import DeployStrategy, InfraSpec, MigrationSpec


def _spec(**target_overrides) -> MigrationSpec:
    target = InfraSpec(
        strategy=DeployStrategy.PODMAN_QUADLET,
        host="pi@10.0.0.1",
        app="c2004",
        version="1.0.0",
        remote_dir="~/c2004",
        verify_url="http://localhost:8100/api/v3/health",
        **target_overrides,
    )
    source = InfraSpec(strategy=DeployStrategy.DOCKER_FULL, host="pi@10.0.0.1")
    return MigrationSpec(name="t", source=source, target=target)


# ── Extractor ─────────────────────────────────────────────────────────────────

class TestExtractor:
    def test_strategy_binaries_for_podman(self):
        spec = _spec()
        out = _Extractor(spec).collect()
        names = {(e.category, e.name) for e in out}
        assert ("binary", "podman") in names
        assert ("binary", "systemctl") in names

    def test_target_remote_dir_emits_directory(self):
        spec = _spec()
        out = _Extractor(spec).collect()
        assert any(e.category == "directory" and e.name == "~/c2004" for e in out)

    def test_verify_url_emits_port(self):
        spec = _spec()
        out = _Extractor(spec).collect()
        assert any(e.category == "port_listening" and e.name == "8100" for e in out)

    def test_extra_step_podman_build_image(self):
        spec = _spec()
        spec.extra_steps = [{
            "id": "build_backend",
            "action": "ssh_cmd",
            "command": "cd ~/c2004 && podman build -t localhost/c2004-backend:1.0.22 -f backend/Dockerfile .",
        }]
        out = _Extractor(spec).collect()
        assert any(
            e.category == "container_image"
            and e.name == "localhost/c2004-backend:1.0.22"
            for e in out
        )

    def test_extra_step_apt_install(self):
        spec = _spec()
        spec.extra_steps = [{
            "id": "install_podman",
            "action": "ssh_cmd",
            "command": "sudo apt-get install -y podman uidmap slirp4netns",
        }]
        out = _Extractor(spec).collect()
        names = {(e.category, e.name) for e in out}
        assert ("apt_package", "podman") in names
        assert ("apt_package", "uidmap") in names

    def test_rsync_dst_emits_directory(self):
        spec = _spec()
        spec.extra_steps = [{
            "id": "sync",
            "action": "rsync",
            "src": "./",
            "dst": "~/c2004",
        }]
        out = _Extractor(spec).collect()
        assert any(e.category == "directory" and e.name == "~/c2004" for e in out)

    def test_dedup(self):
        spec = _spec()
        spec.extra_steps = [
            {"id": "a", "action": "ssh_cmd", "command": "mkdir -p ~/c2004"},
            {"id": "b", "action": "ssh_cmd", "command": "mkdir -p ~/c2004"},
        ]
        out = _Extractor(spec).collect()
        dirs = [e for e in out if e.category == "directory" and e.name == "~/c2004"]
        assert len(dirs) == 1


# ── Helpers ───────────────────────────────────────────────────────────────────

class TestExtractPort:
    @pytest.mark.parametrize("url,expected", [
        ("http://localhost:8100/api/v3/health", 8100),
        ("https://example.com:8443/", 8443),
        ("http://example.com/", 80),
        ("https://example.com/", 443),
        ("ftp://example.com/", None),
    ])
    def test_cases(self, url, expected):
        assert _extract_port(url) == expected


# ── Auditor (with mocked SSH) ─────────────────────────────────────────────────

class _FakeProbe:
    """Replaces Auditor.probe with a scriptable fake."""

    def __init__(self, *, free_gib=10.0, has_binary=True, has_path=True,
                 port=False, image=False, unit=False, apt=True):
        self.free_gib = free_gib
        self._binary = has_binary
        self._path = has_path
        self._port = port
        self._image = image
        self._unit = unit
        self._apt = apt
        self.client = MagicMock()
        self.client.is_reachable.return_value = True

    def has_binary(self, name):
        return bool(self._binary), "/usr/bin/" + name if self._binary else ""

    def has_path(self, path, kind="any"):
        return self._path, "OK" if self._path else "MISSING"

    def port_listening(self, port):
        return self._port, f"*:{port}" if self._port else ""

    def has_image(self, ref):
        return self._image, "podman:abc123" if self._image else "missing"

    def has_systemd_unit(self, unit, user=False):
        return self._unit, unit if self._unit else ""

    def apt_package(self, name):
        return self._apt, "install ok installed" if self._apt else "not-installed"

    def disk_free_gib(self, path="~"):
        return self.free_gib


class TestAuditor:
    def test_unreachable_short_circuits(self):
        spec = _spec()
        a = Auditor(spec, host="pi@10.0.0.1")
        a.probe = _FakeProbe()
        a.probe.client.is_reachable.return_value = False
        report = a.run()
        assert not report.ok
        assert any(c.category == "connectivity" and c.status == "fail"
                   for c in report.checks)

    def test_all_pass(self):
        spec = _spec()
        a = Auditor(spec, host="pi@10.0.0.1")
        a.probe = _FakeProbe(has_binary=True, has_path=True, port=True)
        report = a.run()
        # connectivity pass + disk pass + at least binary + dir + port
        assert report.ok
        assert len(report.passed) >= 4

    def test_missing_binary_fails(self):
        spec = _spec()
        a = Auditor(spec, host="pi@10.0.0.1")
        a.probe = _FakeProbe(has_binary=False)
        report = a.run()
        assert not report.ok
        assert any(c.category == "binary" and c.status == "fail"
                   for c in report.failed)

    def test_low_disk_fails(self):
        spec = _spec()
        a = Auditor(spec, host="pi@10.0.0.1")
        a.probe = _FakeProbe(free_gib=1.0)
        report = a.run()
        assert any(c.category == "disk" and c.status == "fail"
                   for c in report.checks)

    def test_image_missing_is_warn_not_fail(self):
        spec = _spec()
        spec.extra_steps = [{
            "id": "build",
            "action": "ssh_cmd",
            "command": "podman build -t localhost/myapp:1 .",
        }]
        a = Auditor(spec, host="pi@10.0.0.1")
        a.probe = _FakeProbe(image=False)
        report = a.run()
        img_check = [c for c in report.checks
                     if c.category == "container_image"]
        assert img_check and img_check[0].status == "warn"


# ── AuditReport ───────────────────────────────────────────────────────────────

class TestReport:
    def test_summary_counts(self):
        r = AuditReport(spec_path="x", host="h", target_strategy="podman_quadlet")
        r.add(AuditCheck("binary", "podman", "pass"))
        r.add(AuditCheck("binary", "missing", "fail"))
        r.add(AuditCheck("directory", "/foo", "warn"))
        assert "1/3 passed" in r.summary()
        assert "1 missing" in r.summary()
        assert not r.ok

    def test_to_dict_serializable(self):
        r = AuditReport(spec_path="x", host="h", target_strategy="podman_quadlet")
        r.add(AuditCheck("binary", "podman", "pass"))
        d = r.to_dict()
        assert d["host"] == "h"
        assert d["checks"][0]["name"] == "podman"


# ── audit_spec convenience ────────────────────────────────────────────────────

class TestAuditSpec:
    def test_loads_yaml_spec(self, tmp_path, monkeypatch):
        spec_file = tmp_path / "m.yaml"
        spec_file.write_text(
            "name: t\n"
            "source:\n  strategy: docker_full\n  host: local\n"
            "target:\n  strategy: docker_full\n  host: local\n  remote_dir: /tmp/x\n"
        )

        def fake_run(self):
            self.spec.target.remote_dir  # touch attr
            return AuditReport(spec_path=str(spec_file), host="local",
                               target_strategy="docker_full")

        monkeypatch.setattr(Auditor, "run", fake_run)
        report = audit_spec(spec_file)
        assert report.host == "local"
