"""Decorators for Python-native DSL."""
import functools
import inspect
from typing import Callable, Optional, Any, Dict, List
from dataclasses import dataclass, field
from .context import StepContext
from .exceptions import StepError


@dataclass
class MigrationMeta:
    """Metadata for a migration."""
    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)


class MigrationRegistry:
    """Global registry of migration functions."""
    _migrations: Dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str, func: Callable) -> None:
        cls._migrations[name] = func

    @classmethod
    def get(cls, name: str) -> Optional[Callable]:
        return cls._migrations.get(name)

    @classmethod
    def list(cls) -> List[str]:
        return list(cls._migrations.keys())


def migration(
    name: Optional[str] = None,
    version: str = "0.0.0",
    description: Optional[str] = None,
    author: Optional[str] = None,
) -> Callable:
    """Decorator to mark a function as a migration.

    Args:
        name: Migration name (defaults to function name)
        version: Version being deployed
        description: Human-readable description
        author: Who created the migration

    Example:
        @migration(name="c2004 rpi5 deploy", version="1.0.22")
        def deploy():
            with step("restart"):
                ssh("pi@192.168.188.108", "sudo reboot")
    """
    def decorator(func: Callable) -> Callable:
        meta = MigrationMeta(
            name=name or func.__name__,
            version=version,
            description=description or func.__doc__,
            author=author,
        )
        func._migration_meta = meta

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            print(f"🚀 Migration: {meta.name} v{meta.version}")
            if meta.description:
                print(f"   {meta.description}")

            # Run the migration function
            try:
                result = func(*args, **kwargs)
                print(f"✅ Migration completed: {meta.name}")
                return result
            except StepError as e:
                print(f"❌ Migration failed: {e}")
                raise

        MigrationRegistry.register(meta.name, wrapper)
        return wrapper
    return decorator


class StepManager:
    """Manages step execution and tracking."""
    _current: Optional[StepContext] = None
    _history: List[StepContext] = []

    @classmethod
    def begin(cls, name: str, risk: str = "low", timeout: Optional[int] = None) -> StepContext:
        ctx = StepContext(name=name, risk=risk, timeout=timeout)
        cls._current = ctx
        cls._history.append(ctx)
        print(f"\n  → [{name}] (risk={risk}, timeout={timeout}s)")
        return ctx

    @classmethod
    def end(cls, success: bool = True, error: Optional[str] = None) -> None:
        if cls._current:
            cls._current.success = success
            cls._current.error = error
            status = "✓" if success else "✗"
            print(f"    {status} {cls._current.name}")
            cls._current = None


@dataclass
class step:
    """Context manager for a deployment step.

    Args:
        name: Step identifier
        risk: low | medium | high
        timeout: Maximum seconds to wait
        retries: Number of retries on failure

    Example:
        with step("rsync_code", risk="low", timeout=300):
            rsync(src="/local", dst="remote:/path")
    """
    name: str
    risk: str = "low"
    timeout: Optional[int] = None
    retries: int = 0

    def __enter__(self) -> StepContext:
        return StepManager.begin(self.name, self.risk, self.timeout)

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_val:
            StepManager.end(success=False, error=str(exc_val))
            # Re-raise the exception
            return False
        StepManager.end(success=True)
        return True
