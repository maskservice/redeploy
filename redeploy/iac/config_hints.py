"""Heuristic parser for common IaC/CI/CD config files.

This parser provides broad format coverage without extra runtime dependencies:
- Dockerfile / *.Dockerfile
- nginx.conf / *.conf (basic listen + proxy_pass hints)
- Kubernetes YAML manifests
- Terraform (*.tf, *.tfvars)
- TOML (including pyproject.toml)
- Vite config files (vite.config.*)
- CI/CD files (.github/workflows, .gitlab-ci.yml, Jenkinsfile)

It emits ``ParsedSpec`` hints suitable for `redeploy import` scaffolding.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from .base import ParsedSpec, PortInfo, ServiceInfo


class ConfigHintsParser:
    """Best-effort parser for common DevOps/IaC config files."""

    name = "config_hints"
    format_label = "IaC/CI Config Hints"
    extensions = [".yml", ".yaml", ".tf", ".tfvars", ".toml", ".conf", ".json"]
    path_patterns = [
        "Dockerfile",
        "*.Dockerfile",
        "nginx.conf",
        "*.tf",
        "*.tfvars",
        "*.toml",
        "vite.config.*",
        ".gitlab-ci.yml",
        "Jenkinsfile",
        ".github/workflows/*.yml",
        ".github/workflows/*.yaml",
    ]

    _IMAGE_RE = re.compile(r"^\s*(FROM|image:)\s+([^\s#]+)", re.IGNORECASE)
    _TERRAFORM_RES_RE = re.compile(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"')
    _LISTEN_RE = re.compile(r"^\s*listen\s+([0-9]+)")
    _PROXY_PASS_RE = re.compile(r"^\s*proxy_pass\s+([^;]+)")
    _SSH_HOST_RE = re.compile(r"(?:ssh\s+|scp\s+)([\w.-]+@[\w.-]+)")

    def can_parse(self, path: Path) -> bool:
        name = path.name
        lower = name.lower()
        posix = path.as_posix().lower()

        if name == "Dockerfile" or lower.endswith(".dockerfile"):
            return True
        if name == "Jenkinsfile":
            return True
        if lower in {"nginx.conf", ".gitlab-ci.yml", "pyproject.toml"}:
            return True
        if lower.endswith((".tf", ".tfvars", ".toml", "vite.config.ts", "vite.config.js", "vite.config.mjs", "vite.config.cjs")):
            return True
        if "/.github/workflows/" in posix and lower.endswith((".yml", ".yaml")):
            return True
        if lower.endswith((".yml", ".yaml")):
            return self._looks_like_k8s(path)
        return False

    def parse(self, path: Path) -> ParsedSpec:
        name = path.name
        lower = name.lower()

        if name == "Dockerfile" or lower.endswith(".dockerfile"):
            return self._parse_dockerfile(path)
        if name == "Jenkinsfile":
            return self._parse_jenkinsfile(path)
        if "/.github/workflows/" in path.as_posix().lower():
            return self._parse_github_actions(path)
        if lower == ".gitlab-ci.yml":
            return self._parse_gitlab_ci(path)
        if lower.endswith((".tf", ".tfvars")):
            return self._parse_terraform(path)
        if lower.endswith(".toml"):
            return self._parse_toml(path)
        if lower.startswith("vite.config."):
            return self._parse_vite(path)
        if lower.endswith(".conf") or lower == "nginx.conf":
            return self._parse_nginx(path)
        if lower.endswith((".yml", ".yaml")):
            return self._parse_k8s_yaml(path)

        raise ValueError(f"Unsupported config file: {path}")

    def _new_spec(self, path: Path, fmt: str, confidence: float = 0.85) -> ParsedSpec:
        return ParsedSpec(source_file=path, source_format=fmt, confidence=confidence)

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    def _parse_dockerfile(self, path: Path) -> ParsedSpec:
        spec = self._new_spec(path, "dockerfile", confidence=0.9)
        text = self._read_text(path)
        for line in text.splitlines():
            m = self._IMAGE_RE.match(line)
            if not m:
                continue
            image = m.group(2).strip()
            if image and image not in spec.images:
                spec.images.append(image)
        svc = ServiceInfo(name=path.parent.name or "app")
        if spec.images:
            svc.image = spec.images[-1]
        spec.services.append(svc)
        spec.runtime_hints.append("docker")
        return spec

    def _parse_nginx(self, path: Path) -> ParsedSpec:
        spec = self._new_spec(path, "nginx", confidence=0.8)
        text = self._read_text(path)
        ports: list[PortInfo] = []
        for line in text.splitlines():
            lm = self._LISTEN_RE.match(line)
            if lm:
                ports.append(PortInfo(container=int(lm.group(1)), host=int(lm.group(1))))
            pm = self._PROXY_PASS_RE.match(line)
            if pm:
                spec.deploy_commands.append(f"proxy_pass {pm.group(1).strip()}")
        if ports:
            spec.ports.extend(ports)
        spec.runtime_hints.append("systemd")
        return spec

    def _looks_like_k8s(self, path: Path) -> bool:
        try:
            text = self._read_text(path)
            return "apiVersion:" in text and "kind:" in text
        except OSError:
            return False

    def _parse_k8s_yaml(self, path: Path) -> ParsedSpec:
        spec = self._new_spec(path, "kubernetes", confidence=0.9)
        docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            kind = str(doc.get("kind", "")).lower()
            metadata = doc.get("metadata") or {}
            name = str(metadata.get("name", "") or kind or "workload")
            if kind in {"deployment", "statefulset", "daemonset", "job", "cronjob", "pod"}:
                svc = ServiceInfo(name=name)
                containers = (
                    (doc.get("spec") or {}).get("template", {}).get("spec", {}).get("containers", [])
                    if kind != "pod"
                    else (doc.get("spec") or {}).get("containers", [])
                )
                for c in containers:
                    if not isinstance(c, dict):
                        continue
                    img = c.get("image")
                    if img and img not in spec.images:
                        spec.images.append(str(img))
                    for p in c.get("ports", []) or []:
                        cp = p.get("containerPort") if isinstance(p, dict) else None
                        if cp:
                            svc.ports.append(PortInfo(container=int(cp)))
                if svc.image is None and spec.images:
                    svc.image = spec.images[-1]
                spec.services.append(svc)
            if kind == "service":
                for p in (doc.get("spec") or {}).get("ports", []) or []:
                    if isinstance(p, dict) and p.get("port"):
                        spec.ports.append(PortInfo(container=int(p["port"]), host=int(p["port"])))
        spec.runtime_hints.append("k3s")
        return spec

    def _parse_terraform(self, path: Path) -> ParsedSpec:
        spec = self._new_spec(path, "terraform", confidence=0.75)
        text = self._read_text(path)
        for line in text.splitlines():
            m = self._TERRAFORM_RES_RE.match(line)
            if m:
                provider = m.group(1).split("_")[0]
                hint = f"terraform:{provider}"
                if hint not in spec.runtime_hints:
                    spec.runtime_hints.append(hint)
        if not spec.runtime_hints:
            spec.runtime_hints.append("terraform")
        return spec

    def _parse_toml(self, path: Path) -> ParsedSpec:
        spec = self._new_spec(path, "toml", confidence=0.7)
        text = self._read_text(path)
        try:
            import tomllib

            data = tomllib.loads(text)
            if path.name == "pyproject.toml":
                scripts = ((data.get("project") or {}).get("scripts") or {})
                if isinstance(scripts, dict):
                    for k in scripts:
                        spec.deploy_commands.append(f"script:{k}")
        except Exception:
            spec.add_warning("TOML parsed heuristically (tomllib fallback)", severity="info")
            spec.confidence = 0.55
        return spec

    def _parse_vite(self, path: Path) -> ParsedSpec:
        spec = self._new_spec(path, "vite", confidence=0.8)
        text = self._read_text(path)
        if "server:" in text or "preview:" in text:
            spec.deploy_commands.append("vite preview")
        if "build:" in text:
            spec.deploy_commands.append("vite build")
        spec.runtime_hints.extend(["docker", "systemd"])
        return spec

    def _parse_github_actions(self, path: Path) -> ParsedSpec:
        spec = self._new_spec(path, "github_actions", confidence=0.85)
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        # Some YAML loaders (YAML 1.1) coerce unquoted key "on" -> True.
        on_block = raw.get("on") if isinstance(raw, dict) else None
        if on_block is None and isinstance(raw, dict):
            on_block = raw.get(True)
        if isinstance(on_block, dict):
            spec.triggers.extend(sorted(str(k) for k in on_block.keys()))
        elif isinstance(on_block, str):
            spec.triggers.append(on_block)
        jobs = raw.get("jobs") or {}
        for _job_name, job in jobs.items() if isinstance(jobs, dict) else []:
            steps = job.get("steps") or [] if isinstance(job, dict) else []
            for step in steps:
                if not isinstance(step, dict):
                    continue
                run_cmd = step.get("run")
                if run_cmd:
                    cmd = str(run_cmd).strip().splitlines()[0]
                    if cmd:
                        spec.deploy_commands.append(cmd)
                uses = str(step.get("uses", ""))
                if "docker" in uses.lower() and "docker" not in spec.runtime_hints:
                    spec.runtime_hints.append("docker")
                for m in self._SSH_HOST_RE.finditer(str(run_cmd or "")):
                    host = m.group(1)
                    if host not in spec.target_hosts:
                        spec.target_hosts.append(host)
        return spec

    def _parse_gitlab_ci(self, path: Path) -> ParsedSpec:
        spec = self._new_spec(path, "gitlab_ci", confidence=0.8)
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(raw, dict):
            stages = raw.get("stages") or []
            for st in stages:
                spec.triggers.append(f"stage:{st}")
            for key, job in raw.items():
                if key.startswith(".") or not isinstance(job, dict):
                    continue
                script = job.get("script") or []
                if isinstance(script, str):
                    spec.deploy_commands.append(script.splitlines()[0])
                elif isinstance(script, list):
                    for line in script:
                        if line:
                            spec.deploy_commands.append(str(line))
                img = job.get("image")
                if img and str(img) not in spec.images:
                    spec.images.append(str(img))
        return spec

    def _parse_jenkinsfile(self, path: Path) -> ParsedSpec:
        spec = self._new_spec(path, "jenkins", confidence=0.75)
        text = self._read_text(path)
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("stage("):
                spec.triggers.append(line)
            if "sh " in line:
                cmd = line.split("sh ", 1)[1].strip().strip("'\"")
                if cmd:
                    spec.deploy_commands.append(cmd)
        if "docker" in text.lower():
            spec.runtime_hints.append("docker")
        return spec


def parse_json_file(path: Path) -> dict:
    """Tiny helper for plugin authors; currently unused by built-ins."""
    return json.loads(path.read_text(encoding="utf-8"))
