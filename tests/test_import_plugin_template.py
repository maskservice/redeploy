from __future__ import annotations

from click.testing import CliRunner

from redeploy.cli.commands.import_ import import_cmd


def test_list_plugin_templates():
    runner = CliRunner()
    result = runner.invoke(import_cmd, ["--list-plugin-templates"])
    assert result.exit_code == 0
    assert "helm-ansible" in result.output
    assert "gitops-ci" in result.output


def test_copy_plugin_template(tmp_path):
    runner = CliRunner()
    plugin_dir = tmp_path / "redeploy_iac_parsers"

    result = runner.invoke(
        import_cmd,
        ["--plugin-template", "helm-kustomize", "--plugin-dir", str(plugin_dir)],
    )

    assert result.exit_code == 0
    copied = plugin_dir / "helm_kustomize.py"
    assert copied.exists()
    assert "Helm templates + Kustomize" in copied.read_text(encoding="utf-8")


def test_copy_plugin_template_dry_run(tmp_path):
    runner = CliRunner()
    plugin_dir = tmp_path / "redeploy_iac_parsers"

    result = runner.invoke(
        import_cmd,
        [
            "--plugin-template",
            "argocd-flux",
            "--plugin-dir",
            str(plugin_dir),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert not (plugin_dir / "argocd_flux.py").exists()
    assert "DRY RUN" in result.output


def test_source_required_without_plugin_template(tmp_path):
    runner = CliRunner()
    result = runner.invoke(import_cmd, [])
    assert result.exit_code != 0
    assert "SOURCE is required unless --plugin-template is used" in result.output
