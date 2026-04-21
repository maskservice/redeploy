from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_example_module() -> object:
    plugin_path = Path(__file__).parent.parent / "examples" / "redeploy_iac_parsers" / "helm_kustomize.py"
    spec = importlib.util.spec_from_file_location("example_helm_kustomize", plugin_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_example_module_exposes_parsers():
    module = _load_example_module()
    assert hasattr(module, "PARSERS")
    assert len(module.PARSERS) == 2


def test_helm_templates_parser_extracts_images(tmp_path: Path):
    module = _load_example_module()
    parser = module.HelmTemplatesParser()

    chart = tmp_path / "chart" / "templates"
    chart.mkdir(parents=True)
    manifest = chart / "deployment.yaml"
    manifest.write_text(
        """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  template:
    spec:
      containers:
        - name: api
          image: ghcr.io/example/api:1.2.3
""".strip()
    )

    assert parser.can_parse(manifest)
    spec = parser.parse(manifest)
    assert spec.source_format == "helm_templates"
    assert "ghcr.io/example/api:1.2.3" in spec.images
    assert any(s.name == "api" for s in spec.services)


def test_kustomize_parser_extracts_resources_and_images(tmp_path: Path):
    module = _load_example_module()
    parser = module.KustomizationParser()

    kfile = tmp_path / "kustomization.yaml"
    kfile.write_text(
        """
namespace: prod
resources:
  - deployment.yaml
images:
  - name: ghcr.io/example/api
    newTag: 2.0.0
""".strip()
    )

    assert parser.can_parse(kfile)
    spec = parser.parse(kfile)
    assert spec.source_format == "kustomize"
    assert "ghcr.io/example/api:2.0.0" in spec.images
    assert any(cmd.startswith("kubectl apply -k") for cmd in spec.deploy_commands)
