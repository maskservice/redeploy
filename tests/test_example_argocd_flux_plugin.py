from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_example_module() -> object:
    plugin_path = Path(__file__).parent.parent / "examples" / "redeploy_iac_parsers" / "argocd_flux.py"
    spec = importlib.util.spec_from_file_location("example_argocd_flux", plugin_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_example_module_exposes_parsers():
    module = _load_example_module()
    assert hasattr(module, "PARSERS")
    assert len(module.PARSERS) == 2


def test_argocd_application_parser(tmp_path: Path):
    module = _load_example_module()
    parser = module.ArgoCDApplicationParser()

    p = tmp_path / "argocd-application.yaml"
    p.write_text(
        """
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: demo-app
spec:
  source:
    repoURL: https://github.com/example/demo.git
    path: k8s/overlays/prod
    targetRevision: main
  destination:
    server: https://kubernetes.default.svc
    namespace: demo
""".strip()
    )

    assert parser.can_parse(p)
    spec = parser.parse(p)
    assert spec.source_format == "argocd_application"
    assert any(cmd.startswith("argocd-repo:") for cmd in spec.deploy_commands)
    assert "k3s" in spec.runtime_hints
    assert any(s.name == "demo-app" for s in spec.services)


def test_flux_kustomization_parser(tmp_path: Path):
    module = _load_example_module()
    parser = module.FluxKustomizationParser()

    p = tmp_path / "flux-kustomization.yaml"
    p.write_text(
        """
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: app-prod
  namespace: flux-system
spec:
  interval: 10m
  path: ./clusters/prod
  prune: true
  sourceRef:
    kind: GitRepository
    name: app-config
    namespace: flux-system
""".strip()
    )

    assert parser.can_parse(p)
    spec = parser.parse(p)
    assert spec.source_format == "flux_kustomization"
    assert any(cmd.startswith("flux-source:") for cmd in spec.deploy_commands)
    assert any(cmd.startswith("flux-interval:") for cmd in spec.deploy_commands)
    assert "k3s" in spec.runtime_hints
    assert any(s.name == "app-prod" for s in spec.services)
