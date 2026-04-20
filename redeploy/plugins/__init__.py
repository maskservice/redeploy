"""Plugin system for redeploy.

Plugins extend the step pipeline with custom action types via the YAML field:

    action: plugin
    plugin_type: browser_reload   # registered plugin name
    plugin_params:
      port: 9222
      ignore_cache: true

Registering a plugin
--------------------
Use the @register_plugin decorator:

    from redeploy.plugins import register_plugin, PluginContext

    @register_plugin("browser_reload")
    def my_handler(ctx: PluginContext) -> None:
        ...
        ctx.step.result = "ok"
        ctx.step.status = StepStatus.DONE

Or register programmatically:

    from redeploy.plugins import registry
    registry.register("my_action", my_handler)

Auto-discovery
--------------
Built-in plugins are loaded automatically.
User plugins can be placed in:
  - ./redeploy_plugins/          (project-local)
  - ~/.redeploy/plugins/         (user-global)
Each *.py file in these directories is imported when load_user_plugins() is called.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from loguru import logger


@dataclass
class PluginContext:
    """Passed to every plugin handler.

    Attributes
    ----------
    step:       The MigrationStep being executed (set result + status here).
    host:       SSH host string (e.g. "pi@192.168.188.108").
    probe:      RemoteProbe instance — call probe.run(cmd) for SSH commands.
    emitter:    Optional ProgressEmitter — call emitter.progress(step.id, msg).
    params:     Shortcut for step.plugin_params dict.
    dry_run:    If True the plugin should skip side-effects.
    """
    step: object          # MigrationStep (avoid circular import)
    host: str
    probe: object         # RemoteProbe
    emitter: object       # Optional[ProgressEmitter]
    params: dict = field(default_factory=dict)
    dry_run: bool = False


PluginHandler = Callable[[PluginContext], None]


class PluginRegistry:
    """Central registry mapping plugin_type strings to handler callables."""

    def __init__(self) -> None:
        self._handlers: dict[str, PluginHandler] = {}
        self._loaded_builtins = False

    # ── registration ─────────────────────────────────────────────────────────

    def register(self, name: str, handler: PluginHandler) -> None:
        if name in self._handlers:
            logger.debug(f"plugin '{name}' overriding existing registration")
        self._handlers[name] = handler
        logger.debug(f"plugin registered: '{name}'")

    def __call__(self, name: str) -> Callable[[PluginHandler], PluginHandler]:
        """Use as decorator: @registry('my_plugin')."""
        def decorator(fn: PluginHandler) -> PluginHandler:
            self.register(name, fn)
            return fn
        return decorator

    # ── lookup ───────────────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[PluginHandler]:
        self._ensure_builtins()
        return self._handlers.get(name)

    def names(self) -> list[str]:
        self._ensure_builtins()
        return list(self._handlers)

    # ── loading ──────────────────────────────────────────────────────────────

    def _ensure_builtins(self) -> None:
        if not self._loaded_builtins:
            self._loaded_builtins = True
            _load_builtin_plugins()

    def load_directory(self, path: Path) -> int:
        """Import all *.py files in *path*. Returns number of files loaded."""
        if not path.is_dir():
            return 0
        count = 0
        for py_file in sorted(path.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    f"redeploy_plugin_{py_file.stem}", py_file
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)  # type: ignore[union-attr]
                    count += 1
                    logger.debug(f"loaded plugin file: {py_file}")
            except Exception as exc:
                logger.warning(f"failed to load plugin {py_file}: {exc}")
        return count


# ── module-level registry ────────────────────────────────────────────────────

registry = PluginRegistry()


def register_plugin(name: str) -> Callable[[PluginHandler], PluginHandler]:
    """Decorator shortcut: @register_plugin('browser_reload')."""
    return registry(name)


# ── built-in plugin loader ────────────────────────────────────────────────────

def _load_builtin_plugins() -> None:
    """Import all built-in plugin modules from redeploy/plugins/builtin/."""
    builtin_dir = Path(__file__).parent / "builtin"
    if not builtin_dir.is_dir():
        return
    for py_file in sorted(builtin_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        module_name = f"redeploy.plugins.builtin.{py_file.stem}"
        try:
            if module_name not in sys.modules:
                importlib.import_module(module_name)
        except Exception as exc:
            logger.warning(f"failed to load builtin plugin '{py_file.stem}': {exc}")


def load_user_plugins() -> int:
    """Load user plugins from project-local and user-global directories.

    Scans in order:
      1. ./redeploy_plugins/   (cwd — project-local)
      2. ~/.redeploy/plugins/  (user-global)

    Returns total number of plugin files loaded.
    """
    dirs = [
        Path.cwd() / "redeploy_plugins",
        Path.home() / ".redeploy" / "plugins",
    ]
    total = 0
    for d in dirs:
        n = registry.load_directory(d)
        if n:
            logger.debug(f"loaded {n} plugin(s) from {d}")
        total += n
    return total
