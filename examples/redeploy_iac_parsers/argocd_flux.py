"""Example external parser plugin: ArgoCD + Flux GitOps manifests.

How to use locally:
1. Copy this file to ./redeploy_iac_parsers/argocd_flux.py
2. Run: redeploy import path/to/argocd-application.yaml
3. Run: redeploy import path/to/flux-kustomization.yaml

The local parser loader will auto-import files from:
- ./redeploy_iac_parsers/*.py
- ~/.redeploy/iac_parsers/*.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

from redeploy.iac.base import ParsedSpec, ServiceInfo


class ArgoCDApplicationParser:
    name = "argocd_application"
    format_label = "ArgoCD Application"
    extensions = [".yaml", ".yml"]
    path_patterns = ["*application*.yaml", "*application*.yml"]

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() not in {".yaml", ".yml"}:
            return False
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return False
        return str(data.get("kind", "")).lower() == "application" and (
            str(data.get("apiVersion", "")).lower().startswith("argoproj.io/")
        )

    def parse(self, path: Path) -> ParsedSpec:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        spec = ParsedSpec(source_file=path, source_format=self.name, confidence=0.9)

        metadata = data.get("metadata") or {}
        app_name = str(metadata.get("name", "argocd-app"))
        src = (data.get("spec") or {}).get("source") or {}
        dst = (data.get("spec") or {}).get("destination") or {}

        repo_url = str(src.get("repoURL", "")).strip()
        chart = str(src.get("chart", "")).strip()
        target_rev = str(src.get("targetRevision", "")).strip()
        path_value = str(src.get("path", "")).strip()
        namespace = str(dst.get("namespace", "")).strip()
        server = str(dst.get("server", "")).strip()

        svc = ServiceInfo(name=app_name)
        spec.services.append(svc)

        if repo_url:
            spec.deploy_commands.append(f"argocd-repo:{repo_url}")
        if chart:
            spec.deploy_commands.append(f"argocd-chart:{chart}")
        if path_value:
            spec.deploy_commands.append(f"argocd-path:{path_value}")
        if target_rev:
            spec.deploy_commands.append(f"argocd-revision:{target_rev}")
        if namespace:
            spec.runtime_hints.append(f"namespace:{namespace}")
        if server:
            spec.target_hosts.append(server)

        spec.runtime_hints.append("k3s")
        spec.deploy_commands.append("argocd app sync")
        return spec


class FluxKustomizationParser:
    name = "flux_kustomization"
    format_label = "Flux Kustomization"
    extensions = [".yaml", ".yml"]
    path_patterns = ["*kustomization*.yaml", "*kustomization*.yml"]

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() not in {".yaml", ".yml"}:
            return False
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return False
        return str(data.get("kind", "")).lower() == "kustomization" and (
            str(data.get("apiVersion", "")).lower().startswith("kustomize.toolkit.fluxcd.io/")
        )

    def parse(self, path: Path) -> ParsedSpec:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        spec = ParsedSpec(source_file=path, source_format=self.name, confidence=0.9)

        metadata = data.get("metadata") or {}
        k_name = str(metadata.get("name", "flux-kustomization"))
        k_ns = str(metadata.get("namespace", "")).strip()
        k_spec = data.get("spec") or {}

        source_ref = k_spec.get("sourceRef") or {}
        source_kind = str(source_ref.get("kind", "")).strip()
        source_name = str(source_ref.get("name", "")).strip()
        source_ns = str(source_ref.get("namespace", "")).strip()
        path_value = str(k_spec.get("path", "")).strip()
        interval = str(k_spec.get("interval", "")).strip()
        prune = bool(k_spec.get("prune", False))

        spec.services.append(ServiceInfo(name=k_name))

        if k_ns:
            spec.runtime_hints.append(f"namespace:{k_ns}")
        if source_kind or source_name:
            spec.deploy_commands.append(f"flux-source:{source_kind}/{source_name}")
        if source_ns:
            spec.deploy_commands.append(f"flux-source-namespace:{source_ns}")
        if path_value:
            spec.deploy_commands.append(f"flux-path:{path_value}")
        if interval:
            spec.deploy_commands.append(f"flux-interval:{interval}")
        spec.deploy_commands.append(f"flux-prune:{str(prune).lower()}")

        spec.runtime_hints.append("k3s")
        spec.deploy_commands.append("flux reconcile kustomization")
        return spec


# Plugin contract understood by redeploy.iac.registry._load_local_parsers
PARSERS = [ArgoCDApplicationParser, FluxKustomizationParser]
