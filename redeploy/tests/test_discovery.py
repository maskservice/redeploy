"""Tests for discovery.py — pure helpers and registry functions."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from redeploy.discovery import (
    DiscoveredHost,
    _is_ip,
    _merge,
    _scan_known_hosts,
    update_registry,
)
from redeploy.models import DeviceRegistry, KnownDevice


# ── _is_ip ────────────────────────────────────────────────────────────────────


class TestIsIp:
    def test_valid_ipv4(self):
        assert _is_ip("192.168.1.1") is True
        assert _is_ip("10.0.0.1") is True
        assert _is_ip("8.8.8.8") is True
        assert _is_ip("255.255.255.0") is True

    def test_hostname_not_ip(self):
        assert _is_ip("myserver") is False
        assert _is_ip("myserver.local") is False

    def test_partial_ip_not_ip(self):
        assert _is_ip("192.168.1") is False
        assert _is_ip("192.168") is False

    def test_empty_string(self):
        assert _is_ip("") is False

    def test_ipv6_not_matched(self):
        assert _is_ip("::1") is False
        assert _is_ip("2001:db8::1") is False


# ── _merge ────────────────────────────────────────────────────────────────────


class TestMerge:
    def test_deduplicates_by_ip(self):
        hosts = [
            DiscoveredHost(ip="192.168.1.1", source="known_hosts"),
            DiscoveredHost(ip="192.168.1.1", source="arp"),
        ]
        merged = _merge(hosts)
        assert len(merged) == 1

    def test_merges_mac_from_second(self):
        hosts = [
            DiscoveredHost(ip="192.168.1.1", source="known_hosts", mac=""),
            DiscoveredHost(ip="192.168.1.1", source="arp", mac="aa:bb:cc:dd:ee:ff"),
        ]
        merged = _merge(hosts)
        assert merged[0].mac == "aa:bb:cc:dd:ee:ff"

    def test_merges_hostname_from_second(self):
        hosts = [
            DiscoveredHost(ip="192.168.1.1", hostname="", source="arp"),
            DiscoveredHost(ip="192.168.1.1", hostname="myserver", source="mdns"),
        ]
        merged = _merge(hosts)
        assert merged[0].hostname == "myserver"

    def test_existing_hostname_not_overwritten(self):
        hosts = [
            DiscoveredHost(ip="192.168.1.1", hostname="first", source="known_hosts"),
            DiscoveredHost(ip="192.168.1.1", hostname="second", source="mdns"),
        ]
        merged = _merge(hosts)
        assert merged[0].hostname == "first"

    def test_ssh_ok_propagates(self):
        hosts = [
            DiscoveredHost(ip="192.168.1.1", ssh_ok=False),
            DiscoveredHost(ip="192.168.1.1", ssh_ok=True, ssh_user="root"),
        ]
        merged = _merge(hosts)
        assert merged[0].ssh_ok is True
        assert merged[0].ssh_user == "root"

    def test_distinct_ips_kept_separate(self):
        hosts = [
            DiscoveredHost(ip="192.168.1.1"),
            DiscoveredHost(ip="192.168.1.2"),
            DiscoveredHost(ip="192.168.1.3"),
        ]
        merged = _merge(hosts)
        assert len(merged) == 3

    def test_empty_list(self):
        assert _merge([]) == []

    def test_source_updated_from_unknown(self):
        hosts = [
            DiscoveredHost(ip="1.2.3.4", source="unknown"),
            DiscoveredHost(ip="1.2.3.4", source="arp"),
        ]
        merged = _merge(hosts)
        assert merged[0].source == "arp"

    def test_known_source_not_overwritten(self):
        hosts = [
            DiscoveredHost(ip="1.2.3.4", source="known_hosts"),
            DiscoveredHost(ip="1.2.3.4", source="arp"),
        ]
        merged = _merge(hosts)
        assert merged[0].source == "known_hosts"


# ── _scan_known_hosts ─────────────────────────────────────────────────────────


class TestScanKnownHosts:
    """_scan_known_hosts uses __import__('pathlib').Path.home() internally.
    We patch pathlib.Path.home (the live class) so the dynamic import sees it.
    """

    def _results(self, tmp_path, content: str) -> list:
        import pathlib
        home = tmp_path / "home"
        (home / ".ssh").mkdir(parents=True)
        (home / ".ssh" / "known_hosts").write_text(content)
        with patch.object(pathlib.Path, "home", classmethod(lambda cls: home)):
            return _scan_known_hosts()

    def test_parses_plain_host(self, tmp_path):
        results = self._results(tmp_path, "myserver.example.com ssh-ed25519 AAAA\n")
        assert any("myserver.example.com" in (h.hostname or h.ip) for h in results)

    def test_skips_hashed_entries(self, tmp_path):
        results = self._results(tmp_path, "|1|abc123|def456 ssh-ed25519 AAAA\n")
        assert results == []

    def test_skips_comment_lines(self, tmp_path):
        results = self._results(tmp_path, "# comment\nmyhost ssh-rsa AAAA\n")
        assert len(results) == 1

    def test_missing_known_hosts_returns_empty(self, tmp_path):
        import pathlib
        home = tmp_path / "home_empty"
        home.mkdir()
        with patch.object(pathlib.Path, "home", classmethod(lambda cls: home)):
            results = _scan_known_hosts()
        assert results == []

    def test_ip_address_entry(self, tmp_path):
        results = self._results(tmp_path, "192.168.1.100 ssh-ed25519 AAAA\n")
        assert any(h.ip == "192.168.1.100" for h in results)

    def test_bracketed_port_format(self, tmp_path):
        results = self._results(tmp_path, "[myserver]:2222 ssh-ed25519 AAAA\n")
        assert any("myserver" in (h.hostname or h.ip) for h in results)


# ── update_registry ───────────────────────────────────────────────────────────


class TestUpdateRegistry:
    def _empty_reg(self):
        return DeviceRegistry(devices=[])

    def test_adds_ssh_ok_device(self):
        host = DiscoveredHost(ip="10.0.0.1", ssh_ok=True, ssh_user="root", source="arp")
        reg = update_registry([host], registry=self._empty_reg(), save=False)
        assert len(reg.devices) == 1
        assert reg.devices[0].ip == "10.0.0.1"

    def test_does_not_add_non_ssh_device(self):
        host = DiscoveredHost(ip="10.0.0.2", ssh_ok=False)
        reg = update_registry([host], registry=self._empty_reg(), save=False)
        assert len(reg.devices) == 0

    def test_updates_existing_device_last_seen(self):
        existing = KnownDevice(
            id="root@10.0.0.1", host="root@10.0.0.1", ip="10.0.0.1",
            ssh_user="root", source="arp",
        )
        reg = DeviceRegistry(devices=[existing])
        host = DiscoveredHost(ip="10.0.0.1", ssh_ok=True, ssh_user="root", source="arp")
        updated = update_registry([host], registry=reg, save=False)
        assert len(updated.devices) == 1
        assert updated.devices[0].last_seen is not None

    def test_updates_existing_mac(self):
        existing = KnownDevice(
            id="root@10.0.0.1", host="root@10.0.0.1", ip="10.0.0.1",
            mac="", ssh_user="root", source="arp",
        )
        reg = DeviceRegistry(devices=[existing])
        host = DiscoveredHost(ip="10.0.0.1", ssh_ok=True, ssh_user="root",
                              mac="aa:bb:cc:dd:ee:ff", source="arp")
        updated = update_registry([host], registry=reg, save=False)
        assert updated.devices[0].mac == "aa:bb:cc:dd:ee:ff"

    def test_device_id_uses_user_at_ip(self):
        host = DiscoveredHost(ip="10.0.0.1", ssh_ok=True, ssh_user="pi", source="mdns")
        reg = update_registry([host], registry=self._empty_reg(), save=False)
        assert reg.devices[0].id == "pi@10.0.0.1"

    def test_device_id_without_user_uses_ip(self):
        host = DiscoveredHost(ip="10.0.0.1", ssh_ok=True, ssh_user="", source="mdns")
        reg = update_registry([host], registry=self._empty_reg(), save=False)
        assert reg.devices[0].id == "10.0.0.1"

    def test_discovered_tag_added(self):
        host = DiscoveredHost(ip="10.0.0.5", ssh_ok=True, ssh_user="root", source="ping_sweep")
        reg = update_registry([host], registry=self._empty_reg(), save=False)
        assert "discovered" in reg.devices[0].tags

    def test_skips_device_with_empty_ip(self):
        host = DiscoveredHost(ip="", ssh_ok=True, ssh_user="root")
        reg = update_registry([host], registry=self._empty_reg(), save=False)
        assert len(reg.devices) == 0

    def test_multiple_hosts(self):
        hosts = [
            DiscoveredHost(ip="10.0.0.1", ssh_ok=True, ssh_user="root", source="arp"),
            DiscoveredHost(ip="10.0.0.2", ssh_ok=True, ssh_user="pi", source="mdns"),
            DiscoveredHost(ip="10.0.0.3", ssh_ok=False),
        ]
        reg = update_registry(hosts, registry=self._empty_reg(), save=False)
        assert len(reg.devices) == 2
