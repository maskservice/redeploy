"""Built-in plugin: browser_reload

Reloads a Chromium/Chrome tab via the Chrome DevTools Protocol (CDP)
on the remote host, using only Python stdlib (no websocket-client needed).

YAML example
------------
  steps:
    - id: reload_kiosk
      action: plugin
      plugin_type: browser_reload
      description: Reload kiosk browser after deploy
      plugin_params:
        port: 9222          # remote debugging port (default: 9222)
        ignore_cache: true  # hard reload (default: true)
        url_contains: ""    # optional: only reload tabs whose URL contains this
"""
from __future__ import annotations

import base64
import json
import os
import socket
import urllib.request

from loguru import logger

from redeploy.models import StepStatus
from redeploy.plugins import PluginContext, register_plugin


@register_plugin("browser_reload")
def browser_reload(ctx: PluginContext) -> None:
    port: int = int(ctx.params.get("port", 9222))
    ignore_cache: bool = bool(ctx.params.get("ignore_cache", True))
    url_filter: str = ctx.params.get("url_contains", "")

    if ctx.dry_run:
        ctx.step.result = "dry-run"
        ctx.step.status = StepStatus.DONE
        return

    # Fetch tab list from remote via SSH proxy (curl on remote host)
    tabs_json_cmd = f"curl -sf http://localhost:{port}/json"
    r = ctx.probe.run(tabs_json_cmd, timeout=10)
    if not r.ok or not r.out.strip():
        from redeploy.apply.executor import StepError
        raise StepError(ctx.step, f"CDP /json not reachable on port {port}: {r.stderr[:100]}")

    try:
        tabs = json.loads(r.out)
    except json.JSONDecodeError as exc:
        from redeploy.apply.executor import StepError
        raise StepError(ctx.step, f"CDP /json invalid JSON: {exc}")

    # Filter tabs
    target_tabs = [
        t for t in tabs
        if t.get("type") == "page" and url_filter in t.get("url", "")
    ]
    if not target_tabs:
        target_tabs = [t for t in tabs if t.get("type") == "page"]

    if not target_tabs:
        from redeploy.apply.executor import StepError
        raise StepError(ctx.step, "No page tabs found via CDP")

    reloaded = []
    for tab in target_tabs:
        tab_id = tab["id"]
        ws_path = f"/devtools/page/{tab_id}"
        tab_url = tab.get("url", "")[:60]

        # Build WebSocket script to run on remote via SSH
        script = _cdp_reload_script(port, ws_path, ignore_cache)
        reload_cmd = f"python3 -c {_sh_quote(script)}"
        r2 = ctx.probe.run(reload_cmd, timeout=15)
        if r2.ok:
            logger.debug(f"    reloaded tab: {tab_url}")
            if ctx.emitter:
                ctx.emitter.progress(ctx.step.id, f"reloaded: {tab_url}")
            reloaded.append(tab_url)
        else:
            logger.warning(f"    CDP reload failed for {tab_url}: {r2.stderr[:80]}")

    if not reloaded:
        from redeploy.apply.executor import StepError
        raise StepError(ctx.step, "CDP reload failed for all tabs")

    ctx.step.result = f"reloaded {len(reloaded)} tab(s): {', '.join(reloaded)}"
    ctx.step.status = StepStatus.DONE


def _cdp_reload_script(port: int, ws_path: str, ignore_cache: bool) -> str:
    """Return a self-contained Python script (stdlib only) that sends Page.reload via CDP."""
    payload = json.dumps({"id": 1, "method": "Page.reload",
                          "params": {"ignoreCache": ignore_cache}})
    return (
        "import json,socket,base64,os\n"
        f"port={port}\npath={ws_path!r}\npayload={payload!r}\n"
        "s=socket.socket()\n"
        "s.connect(('localhost',port))\n"
        "key=base64.b64encode(os.urandom(16)).decode()\n"
        "s.send(('GET '+path+' HTTP/1.1\\r\\nHost: localhost:'+str(port)+'\\r\\n"
        "Upgrade: websocket\\r\\nConnection: Upgrade\\r\\n"
        "Sec-WebSocket-Key: '+key+'\\r\\nSec-WebSocket-Version: 13\\r\\n\\r\\n').encode())\n"
        "s.recv(4096)\n"
        "pl=payload.encode()\n"
        "mask=os.urandom(4)\n"
        "frame=bytes([0x81,0x80|len(pl)])+mask+bytes(b^mask[i%4] for i,b in enumerate(pl))\n"
        "s.send(frame)\n"
        "s.recv(4096)\n"
        "s.close()\n"
        "print('ok')\n"
    )


def _sh_quote(s: str) -> str:
    """Wrap string in single quotes for shell, escaping internal single quotes."""
    return "'" + s.replace("'", "'\"'\"'") + "'"
