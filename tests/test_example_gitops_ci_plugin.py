from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_example_module() -> object:
    plugin_path = Path(__file__).parent.parent / "examples" / "redeploy_iac_parsers" / "gitops_ci.py"
    spec = importlib.util.spec_from_file_location("example_gitops_ci", plugin_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_example_module_exposes_parsers():
    module = _load_example_module()
    assert hasattr(module, "PARSERS")
    assert len(module.PARSERS) == 2


def test_github_actions_gitops_parser(tmp_path: Path):
    module = _load_example_module()
    parser = module.GitHubActionsGitOpsParser()

    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    p = workflow_dir / "deploy-gitops.yml"
    p.write_text(
        """
on:
  push:
    branches: [ main ]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - run: argocd app sync demo-app
      - run: argocd app wait demo-app --health
""".strip()
    )

    assert parser.can_parse(p)
    spec = parser.parse(p)
    assert spec.source_format == "github_actions_gitops"
    assert "push" in spec.triggers
    assert any("argocd app sync" in cmd for cmd in spec.deploy_commands)
    assert "gitops" in spec.runtime_hints


def test_gitlab_ci_gitops_parser(tmp_path: Path):
    module = _load_example_module()
    parser = module.GitLabCIGitOpsParser()

    p = tmp_path / ".gitlab-ci.yml"
    p.write_text(
        """
stages: [deploy]

deploy_gitops:
  stage: deploy
  script:
    - flux reconcile kustomization app-prod -n flux-system
    - kubectl apply -k clusters/prod
""".strip()
    )

    assert parser.can_parse(p)
    spec = parser.parse(p)
    assert spec.source_format == "gitlab_ci_gitops"
    assert "stage:deploy" in spec.triggers
    assert any("flux reconcile" in cmd for cmd in spec.deploy_commands)
    assert "gitops" in spec.runtime_hints
