"""Built-in plugin: notify

Sends deployment notifications to Slack (webhook) or any generic HTTP endpoint.
Runs locally (no SSH needed) — useful as a final pipeline step.

YAML example
------------
  steps:
    - id: notify_slack
      action: plugin
      plugin_type: notify
      description: Notify Slack on deploy
      plugin_params:
        backend: slack
        webhook_url: "${SLACK_WEBHOOK_URL}"
        message: "✅ {app} deployed to {env} by redeploy"
        env: prod
        app: c2004

    - id: notify_webhook
      action: plugin
      plugin_type: notify
      description: POST deployment event to monitoring endpoint
      plugin_params:
        backend: webhook
        url: "https://ops.example.com/hooks/deploy"
        method: POST           # GET or POST (default: POST)
        headers:
          Authorization: "Bearer ${OPS_TOKEN}"
        payload:
          event: deploy
          app: c2004

CSS DSL example
---------------
  step-4: plugin notify backend=slack message="deployed {app}";
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from string import Template

from loguru import logger

from redeploy.models import StepStatus
from redeploy.plugins import PluginContext, register_plugin


@register_plugin("notify")
def notify(ctx: PluginContext) -> None:
    backend: str = ctx.params.get("backend", "webhook")

    if ctx.dry_run:
        ctx.step.result = f"dry-run: would notify via {backend}"
        ctx.step.status = StepStatus.DONE
        return

    if backend == "slack":
        _notify_slack(ctx)
    elif backend in ("webhook", "http"):
        _notify_webhook(ctx)
    else:
        from redeploy.apply.executor import StepError
        raise StepError(ctx.step, f"unknown notify backend '{backend}'. Use: slack, webhook")


# ── Slack ─────────────────────────────────────────────────────────────────────

def _notify_slack(ctx: PluginContext) -> None:
    from redeploy.apply.executor import StepError

    webhook_url = _resolve_env(ctx.params.get("webhook_url", ""))
    if not webhook_url:
        raise StepError(ctx.step, "notify[slack] requires webhook_url (or $SLACK_WEBHOOK_URL)")

    raw_msg = ctx.params.get("message", "redeploy: deployment complete")
    message = _fmt(raw_msg, ctx)

    payload = {"text": message}
    # Optional: blocks-style rich message
    if ctx.params.get("blocks"):
        payload["blocks"] = ctx.params["blocks"]

    _http_post(ctx, webhook_url, payload)
    ctx.step.result = f"slack notified: {message[:80]}"
    ctx.step.status = StepStatus.DONE


# ── Generic webhook ───────────────────────────────────────────────────────────

def _notify_webhook(ctx: PluginContext) -> None:
    from redeploy.apply.executor import StepError

    url = _resolve_env(ctx.params.get("url", ""))
    if not url:
        raise StepError(ctx.step, "notify[webhook] requires url")

    method: str = ctx.params.get("method", "POST").upper()
    headers: dict[str, str] = {
        k: _resolve_env(str(v))
        for k, v in ctx.params.get("headers", {}).items()
    }
    raw_payload: dict = ctx.params.get("payload", {})
    payload = {k: _fmt(str(v), ctx) for k, v in raw_payload.items()}

    if method == "POST":
        _http_post(ctx, url, payload, headers=headers)
    elif method == "GET":
        _http_get(ctx, url, headers=headers)
    else:
        raise StepError(ctx.step, f"notify[webhook] unsupported method '{method}'")

    ctx.step.result = f"webhook {method} {url[:60]}: ok"
    ctx.step.status = StepStatus.DONE


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _http_post(ctx: PluginContext, url: str, payload: dict, headers: dict | None = None) -> None:
    from redeploy.apply.executor import StepError

    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            if status >= 400:
                raise StepError(ctx.step, f"HTTP POST {url} returned {status}")
            logger.debug(f"    notify POST {url} → {status}")
    except urllib.error.URLError as exc:
        raise StepError(ctx.step, f"notify HTTP error: {exc}") from exc


def _http_get(ctx: PluginContext, url: str, headers: dict | None = None) -> None:
    from redeploy.apply.executor import StepError

    req = urllib.request.Request(url, method="GET")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 400:
                raise StepError(ctx.step, f"HTTP GET {url} returned {resp.status}")
            logger.debug(f"    notify GET {url} → {resp.status}")
    except urllib.error.URLError as exc:
        raise StepError(ctx.step, f"notify HTTP error: {exc}") from exc


# ── utils ─────────────────────────────────────────────────────────────────────

def _resolve_env(value: str) -> str:
    """Expand $VAR and ${VAR} references from environment."""
    return os.path.expandvars(value)


def _fmt(template: str, ctx: PluginContext) -> str:
    """Substitute {app}, {env}, {host} placeholders."""
    return template.format(
        app=ctx.params.get("app", "app"),
        env=ctx.params.get("env", "unknown"),
        host=ctx.host,
    )
