"""Example external parser plugin: GitOps CI automation for ArgoCD/Flux.

How to use locally:
1. Copy this file to ./redeploy_iac_parsers/gitops_ci.py
2. Run: redeploy import .github/workflows/deploy-gitops.yml
3. Run: redeploy import .gitlab-ci.yml

This plugin specializes CI/CD parsing for GitOps-oriented pipelines using:
- argocd app sync / argocd app wait
- flux reconcile kustomization / source git
- kubectl apply -k / kubectl rollout status
"""
from __future__ import annotations

from pathlib import Path

import yaml

from redeploy.iac.base import ParsedSpec, ServiceInfo


_GITOPS_MARKERS = (
    "argocd app sync",
    "argocd app wait",
    "flux reconcile",
    "flux bootstrap",
    "kubectl apply -k",
)


def _is_gitops_command(text: str) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in _GITOPS_MARKERS)


class GitHubActionsGitOpsParser:
    name = "github_actions_gitops"
    format_label = "GitHub Actions GitOps"
    extensions = [".yaml", ".yml"]
    path_patterns = [".github/workflows/*.yaml", ".github/workflows/*.yml"]

    def can_parse(self, path: Path) -> bool:
        if "/.github/workflows/" not in path.as_posix():
            return False
        if path.suffix.lower() not in {".yaml", ".yml"}:
            return False
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return False
        jobs = raw.get("jobs") if isinstance(raw, dict) else None
        if not isinstance(jobs, dict):
            return False
        for job in jobs.values():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps", []) or []:
                if isinstance(step, dict) and _is_gitops_command(str(step.get("run", ""))):
                    return True
        return False

    def parse(self, path: Path) -> ParsedSpec:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        spec = ParsedSpec(source_file=path, source_format=self.name, confidence=0.9)

        on_block = raw.get("on") if isinstance(raw, dict) else None
        if on_block is None and isinstance(raw, dict):
            on_block = raw.get(True)
        if isinstance(on_block, dict):
            spec.triggers.extend(sorted(str(k) for k in on_block.keys()))
        elif isinstance(on_block, str):
            spec.triggers.append(on_block)

        for job_name, job in (raw.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            svc = ServiceInfo(name=str(job_name))
            spec.services.append(svc)
            for step in job.get("steps", []) or []:
                if not isinstance(step, dict):
                    continue
                run = str(step.get("run", "")).strip()
                if run and _is_gitops_command(run):
                    spec.deploy_commands.append(run.splitlines()[0])

        spec.runtime_hints.extend(["k3s", "gitops"])
        return spec


class GitLabCIGitOpsParser:
    name = "gitlab_ci_gitops"
    format_label = "GitLab CI GitOps"
    extensions = [".yaml", ".yml"]
    path_patterns = [".gitlab-ci.yml"]

    def can_parse(self, path: Path) -> bool:
        if path.name != ".gitlab-ci.yml":
            return False
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return False
        if not isinstance(raw, dict):
            return False
        for job in raw.values():
            if not isinstance(job, dict):
                continue
            script = job.get("script") or []
            items = [script] if isinstance(script, str) else script
            for line in items:
                if _is_gitops_command(str(line)):
                    return True
        return False

    def parse(self, path: Path) -> ParsedSpec:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        spec = ParsedSpec(source_file=path, source_format=self.name, confidence=0.88)

        for stage in raw.get("stages", []) or []:
            spec.triggers.append(f"stage:{stage}")

        for job_name, job in raw.items():
            if job_name.startswith(".") or not isinstance(job, dict):
                continue
            spec.services.append(ServiceInfo(name=str(job_name)))
            script = job.get("script") or []
            items = [script] if isinstance(script, str) else script
            for line in items:
                line_s = str(line).strip()
                if line_s and _is_gitops_command(line_s):
                    spec.deploy_commands.append(line_s)

        spec.runtime_hints.extend(["k3s", "gitops"])
        return spec


PARSERS = [GitHubActionsGitOpsParser, GitLabCIGitOpsParser]
