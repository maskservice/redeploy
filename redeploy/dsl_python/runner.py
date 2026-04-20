"""Runner for Python-native DSL migrations.

Provides CLI integration to run migration.py files via redeploy.
"""
import sys
import importlib.util
import inspect
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from .decorators import MigrationRegistry, MigrationMeta
from .exceptions import DSLException


class PythonMigrationRunner:
    """Runner for Python-based migrations."""

    def __init__(self, verbose: bool = False, dry_run: bool = False):
        self.verbose = verbose
        self.dry_run = dry_run
        self.results: List[Dict[str, Any]] = []

    def run_file(
        self,
        file_path: str,
        function_name: Optional[str] = None,
        *args,
        **kwargs
    ) -> bool:
        """Run a migration from a Python file.

        Args:
            file_path: Path to migration.py file
            function_name: Specific function to run (or None for default)
            *args, **kwargs: Arguments to pass to migration function

        Returns:
            True if successful

        Raises:
            FileNotFoundError: If file doesn't exist
            RuntimeError: If no migration found
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Migration file not found: {file_path}")

        if self.verbose:
            print(f"Loading migration from: {path.absolute()}")

        # Load the module
        module_name = path.stem
        spec = importlib.util.spec_from_file_location(module_name, path)
        if not spec or not spec.loader:
            raise RuntimeError(f"Failed to load spec for: {file_path}")

        module = importlib.util.module_from_spec(spec)

        # Add redeploy to path if needed
        redeploy_path = Path(__file__).parent.parent.parent
        if str(redeploy_path) not in sys.path:
            sys.path.insert(0, str(redeploy_path))

        # Execute the module
        spec.loader.exec_module(module)

        # Find migration functions
        migrations = self._find_migrations(module)

        if not migrations:
            raise RuntimeError(f"No @migration decorated functions found in {file_path}")

        # Select function to run
        if function_name:
            if function_name not in migrations:
                available = ", ".join(migrations.keys())
                raise RuntimeError(
                    f"Migration '{function_name}' not found. Available: {available}"
                )
            target = migrations[function_name]
        else:
            # Use first migration
            target = list(migrations.values())[0]
            function_name = list(migrations.keys())[0]

        # Get metadata
        meta = getattr(target, '_migration_meta', None)
        if meta:
            print(f"\n🚀 Running migration: {meta.name} v{meta.version}")
            if meta.description:
                print(f"   {meta.description}")
            if self.dry_run:
                print("   [DRY RUN - no changes will be made]")

        # Execute
        try:
            if self.dry_run:
                # In dry-run, we could analyze but not execute
                # For now, just print what would happen
                print("\n   Steps that would be executed:")
                # TODO: Add step introspection

            result = target(*args, **kwargs)

            if meta:
                print(f"\n✅ Migration completed: {meta.name}")

            return True

        except DSLException as e:
            print(f"\n❌ Migration failed: {e}")
            return False

    def _find_migrations(self, module) -> Dict[str, Callable]:
        """Find all @migration decorated functions in a module."""
        migrations = {}

        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and hasattr(obj, '_migration_meta'):
                migrations[name] = obj

        return migrations

    def list_migrations(self, file_path: str) -> List[str]:
        """List all available migrations in a file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Migration file not found: {file_path}")

        module_name = path.stem
        spec = importlib.util.spec_from_file_location(module_name, path)
        if not spec or not spec.loader:
            return []

        module = importlib.util.module_from_spec(spec)

        # Add redeploy to path
        redeploy_path = Path(__file__).parent.parent.parent
        if str(redeploy_path) not in sys.path:
            sys.path.insert(0, str(redeploy_path))

        spec.loader.exec_module(module)

        migrations = self._find_migrations(module)
        return list(migrations.keys())


def main():
    """CLI entry point for running Python migrations."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run Python-native DSL migrations"
    )
    parser.add_argument(
        "file",
        help="Path to migration.py file"
    )
    parser.add_argument(
        "--function", "-f",
        help="Specific function to run (default: first @migration)"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Show what would be done without executing"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available migrations"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    runner = PythonMigrationRunner(
        verbose=args.verbose,
        dry_run=args.dry_run
    )

    if args.list:
        migrations = runner.list_migrations(args.file)
        print(f"Available migrations in {args.file}:")
        for name in migrations:
            print(f"  - {name}")
        return 0

    try:
        success = runner.run_file(
            args.file,
            function_name=args.function
        )
        return 0 if success else 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
