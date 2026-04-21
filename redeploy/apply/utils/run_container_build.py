"""Container build handler with progress polling (docker/podman)."""
from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Literal

from loguru import logger

from ...models import StepStatus

if TYPE_CHECKING:
    from ..models import MigrationStep
    from ..progress import ProgressEmitter
    from ...detect.remote import RemoteProbe


def run_container_build(
    step: "MigrationStep",
    probe: "RemoteProbe",
    emitter: "ProgressEmitter | None",
    engine: Literal["docker", "podman"],
) -> None:
    """Run container build on remote with periodic progress polling."""
    cmd = step.command
    if not cmd:
        from ..exceptions import StepError
        raise StepError(step, "No command specified")

    timeout = step.timeout or 1800  # 30 min default for ARM64 builds
    poll_interval = 15
    done_event = threading.Event()
    result_holder: list = []

    def _ssh_build() -> None:
        r = probe.run(cmd, timeout=timeout)
        result_holder.append(r)
        done_event.set()

    thread = threading.Thread(target=_ssh_build, daemon=True)
    thread.start()

    elapsed = 0
    while not done_event.wait(timeout=poll_interval):
        elapsed += poll_interval
        cache_cmd = f"{engine} system df 2>/dev/null | grep -E 'Image|Cache' | awk '{{print $1, $3, $4}}'"
        snap = probe.run(cache_cmd, timeout=10)
        if snap.ok and snap.out.strip():
            lines = " | ".join(snap.out.strip().splitlines())
            msg = f"[{elapsed}s] {engine} cache: {lines}"
            logger.debug(f"    {msg}")
            if emitter:
                emitter.progress(step.id, msg)
        else:
            msg = f"[{elapsed}s] {engine} build in progress..."
            logger.debug(f"    {msg}")
            if emitter:
                emitter.progress(step.id, msg)

    if not result_holder:
        from ..exceptions import StepError
        raise StepError(step, f"{engine.capitalize()} build thread did not return a result")
    r = result_holder[0]
    step.result = r.out[:500]
    if not r.ok:
        from ..exceptions import StepError
        raise StepError(step, f"exit={r.exit_code}: {r.stderr[:300]}")
    logger.debug(f"    {engine} build completed in {elapsed + poll_interval}s")
    step.status = StepStatus.DONE
