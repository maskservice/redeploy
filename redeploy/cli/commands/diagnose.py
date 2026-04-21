"""diagnose command — Compare a migration spec against the live target host."""
from __future__ import annotations

import sys

import click
import yaml


@click.command()
@click.argument("spec", type=click.Path(exists=True, dir_okay=False))
@click.option("--host", default=None, help="Override target host (default: spec.target.host)")
@click.option("--ssh-key", default=None, type=click.Path(), help="Path to SSH private key")
@click.option("--format", "output_fmt", default="yaml", type=click.Choice(["yaml", "json"]), help="Output format (default: yaml)")
@click.option("--exit-on-fail", is_flag=True, help="Exit with non-zero status if any check fails")
@click.pass_context
def diagnose(ctx, spec, host, ssh_key, output_fmt, exit_on_fail):
    """Compare a migration spec against the live target host.

    Walks the spec (YAML or markpact .md), derives all expected facts
    (binaries, directories, ports, container images, systemd units,
    apt packages, env files, free disk) and probes the target read-only
    via SSH. Reports what is missing or out of spec — without applying
    any change.

    \b
    Examples:
        redeploy diagnose migration.podman-rpi5-resume.md
        redeploy diagnose migration.yaml --host pi@192.168.188.108
        redeploy diagnose migration.yaml --format json
    """
    from ...audit import audit_spec

    try:
        report = audit_spec(spec, host=host, ssh_key=ssh_key)
    except Exception as exc:
        click.echo(f"audit failed: {exc}", err=True)
        sys.exit(2)

    if output_fmt == "json":
        import json as _json
        click.echo(_json.dumps(report.to_dict(), indent=2))
    else:
        click.echo(yaml.safe_dump(report.to_dict(), sort_keys=False))

    if exit_on_fail and not report.ok:
        sys.exit(1)
