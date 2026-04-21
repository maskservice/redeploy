"""Example external parser plugin: Helm + Ansible.

How to use locally:
1. Copy this file to ./redeploy_iac_parsers/helm_ansible.py
2. Run: redeploy import path/to/chart/Chart.yaml
3. Run: redeploy import playbook.yml

The local parser loader will auto-import files from:
- ./redeploy_iac_parsers/*.py
- ~/.redeploy/iac_parsers/*.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

from redeploy.iac.base import ParsedSpec, ServiceInfo


class HelmChartParser:
    name = "helm_chart"
    format_label = "Helm Chart"
    extensions = [".yaml", ".yml"]
    path_patterns = ["Chart.yaml", "values.yaml"]

    def can_parse(self, path: Path) -> bool:
        return path.name in {"Chart.yaml", "values.yaml"}

    def parse(self, path: Path) -> ParsedSpec:
        spec = ParsedSpec(source_file=path, source_format=self.name, confidence=0.8)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

        if path.name == "Chart.yaml":
            app_name = str(data.get("name", path.parent.name))
            spec.services.append(ServiceInfo(name=app_name))
            spec.runtime_hints.append("k3s")
            return spec

        # values.yaml best-effort extraction
        image = data.get("image") if isinstance(data, dict) else None
        if isinstance(image, dict):
            repo = str(image.get("repository", "")).strip()
            tag = str(image.get("tag", "")).strip()
            if repo:
                img = f"{repo}:{tag}" if tag else repo
                spec.images.append(img)
                spec.services.append(ServiceInfo(name=path.parent.name, image=img))
        spec.runtime_hints.append("k3s")
        return spec


class AnsiblePlaybookParser:
    name = "ansible_playbook"
    format_label = "Ansible Playbook"
    extensions = [".yaml", ".yml"]
    path_patterns = ["playbook.yml", "playbook.yaml", "*.playbook.yml"]

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() not in {".yml", ".yaml"}:
            return False
        lname = path.name.lower()
        if "playbook" in lname:
            return True
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return isinstance(data, list) and any(isinstance(item, dict) and "hosts" in item for item in data)
        except Exception:
            return False

    def parse(self, path: Path) -> ParsedSpec:
        spec = ParsedSpec(source_file=path, source_format=self.name, confidence=0.75)
        plays = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if isinstance(plays, list):
            for play in plays:
                if not isinstance(play, dict):
                    continue
                host = play.get("hosts")
                if host:
                    host_s = str(host)
                    if host_s not in spec.target_hosts:
                        spec.target_hosts.append(host_s)
                for task in play.get("tasks", []) or []:
                    if not isinstance(task, dict):
                        continue
                    name = task.get("name")
                    if name:
                        spec.deploy_commands.append(f"ansible-task:{name}")
        spec.runtime_hints.append("systemd")
        return spec


# Plugin contract understood by redeploy.iac.registry._load_local_parsers
PARSERS = [HelmChartParser, AnsiblePlaybookParser]
