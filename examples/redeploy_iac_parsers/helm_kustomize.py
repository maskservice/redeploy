"""Example external parser plugin: Helm templates + Kustomize.

How to use locally:
1. Copy this file to ./redeploy_iac_parsers/helm_kustomize.py
2. Run: redeploy import path/to/chart/templates/deployment.yaml
3. Run: redeploy import path/to/kustomization.yaml

The local parser loader will auto-import files from:
- ./redeploy_iac_parsers/*.py
- ~/.redeploy/iac_parsers/*.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

from redeploy.iac.base import ParsedSpec, PortInfo, ServiceInfo


def _extract_images_from_container_spec(container_spec: dict) -> list[str]:
    images: list[str] = []
    for c in container_spec.get("containers", []) or []:
        if isinstance(c, dict) and c.get("image"):
            images.append(str(c["image"]))
    return images


class HelmTemplatesParser:
    name = "helm_templates"
    format_label = "Helm Templates"
    extensions = [".yaml", ".yml"]
    path_patterns = ["templates/*.yaml", "templates/*.yml"]

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() not in {".yml", ".yaml"}:
            return False
        return "templates" in path.parts

    def parse(self, path: Path) -> ParsedSpec:
        spec = ParsedSpec(source_file=path, source_format=self.name, confidence=0.8)
        docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            kind = str(doc.get("kind", "")).lower()
            metadata = doc.get("metadata") or {}
            name = str(metadata.get("name", "workload"))
            if kind in {"deployment", "statefulset", "daemonset", "pod", "job", "cronjob"}:
                svc = ServiceInfo(name=name)
                pod_spec = (
                    (doc.get("spec") or {}).get("template", {}).get("spec", {})
                    if kind != "pod"
                    else (doc.get("spec") or {})
                )
                for img in _extract_images_from_container_spec(pod_spec):
                    if img not in spec.images:
                        spec.images.append(img)
                    if svc.image is None:
                        svc.image = img
                spec.services.append(svc)
            elif kind == "service":
                for p in (doc.get("spec") or {}).get("ports", []) or []:
                    if isinstance(p, dict) and p.get("port"):
                        port = int(p["port"])
                        spec.ports.append(PortInfo(container=port, host=port))
        spec.runtime_hints.append("k3s")
        return spec


class KustomizationParser:
    name = "kustomize"
    format_label = "Kustomize"
    extensions = [".yaml", ".yml"]
    path_patterns = ["kustomization.yaml", "kustomization.yml"]

    def can_parse(self, path: Path) -> bool:
        return path.name in {"kustomization.yaml", "kustomization.yml"}

    def parse(self, path: Path) -> ParsedSpec:
        spec = ParsedSpec(source_file=path, source_format=self.name, confidence=0.85)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        resources = data.get("resources") or []
        images = data.get("images") or []
        namespace = data.get("namespace")

        for res in resources:
            if isinstance(res, str):
                spec.deploy_commands.append(f"resource:{res}")

        for image in images:
            if isinstance(image, str):
                if image not in spec.images:
                    spec.images.append(image)
                continue
            if isinstance(image, dict):
                name = str(image.get("newName") or image.get("name") or "").strip()
                tag = str(image.get("newTag") or "").strip()
                if name:
                    img = f"{name}:{tag}" if tag else name
                    if img not in spec.images:
                        spec.images.append(img)

        if namespace:
            spec.runtime_hints.append(f"namespace:{namespace}")

        spec.runtime_hints.append("k3s")
        spec.deploy_commands.append(f"kubectl apply -k {path.parent}")
        return spec


# Plugin contract understood by redeploy.iac.registry._load_local_parsers
PARSERS = [HelmTemplatesParser, KustomizationParser]
