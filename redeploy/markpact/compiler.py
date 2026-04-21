from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..models import InfraSpec, MigrationSpec, MigrationStep, _migrate_legacy_post_deploy
from ..steps import StepLibrary
from .models import MarkpactBlock, MarkpactDocument


class MarkpactCompileError(ValueError):
    """Raised when a markpact document cannot be compiled to MigrationSpec."""


_SUPPORTED_BLOCK_KINDS = {"config", "steps", "ref"}
_SUPPORTED_FORMATS = {"yaml", "toml", "json", "bash", "sh"}
_ALLOWED_SPEC_KEYS = set(MigrationSpec.model_fields)
_ALLOWED_INFRA_KEYS = set(InfraSpec.model_fields)
_ALLOWED_STEP_KEYS = set(MigrationStep.model_fields) | {"insert_before"}
_COMMON_CONFIG_WRAPPERS = {"deployment", "migration", "spec"}


def compile_markpact_document(document: MarkpactDocument) -> MigrationSpec:
    data = compile_markpact_document_to_data(document)
    # Backward-compat: translate legacy post_deploy/pre_deploy blocks → generic hooks.
    data = _migrate_legacy_post_deploy(data)
    try:
        return MigrationSpec(**data)
    except ValidationError as exc:
        raise MarkpactCompileError(
            f"{document.path}: compiled markpact document does not match MigrationSpec: {exc}"
        ) from exc


def compile_markpact_document_to_data(document: MarkpactDocument) -> dict[str, Any]:
    compiled: dict[str, Any] = {}
    saw_config = False

    for block in document.blocks:
        if block.kind not in _SUPPORTED_BLOCK_KINDS:
            raise MarkpactCompileError(
                f"{document.path}:{block.start_line}: unsupported block kind 'markpact:{block.kind}'. "
                "Phase 1 supports only markpact:config and markpact:steps."
            )

        # Skip payload loading for ref blocks - they are used by inline_script via command_ref
        if block.kind == "ref":
            continue

        payload = _load_block_payload(document.path, block)

        if block.kind == "config":
            saw_config = True
            config_payload = _normalize_config_payload(payload, document.path, block)
            _deep_merge(compiled, config_payload)
            continue

        steps = _extract_steps(payload, document.path, block)
        compiled.setdefault("extra_steps", [])
        compiled["extra_steps"].extend(steps)

    if not saw_config:
        raise MarkpactCompileError(
            f"{document.path}: at least one markpact:config block is required."
        )

    return compiled


def _load_block_payload(path: Path, block: MarkpactBlock) -> Any:
    format_name = (block.format or "yaml").lower()
    if format_name not in _SUPPORTED_FORMATS:
        raise MarkpactCompileError(
            f"{path}:{block.start_line}: unsupported payload format '{format_name}' for {block.label}."
        )

    content = block.content.strip()
    if not content:
        return {}

    try:
        if format_name == "yaml":
            return yaml.safe_load(content) or {}
        if format_name == "toml":
            return tomllib.loads(content)
        return json.loads(content)
    except Exception as exc:
        raise MarkpactCompileError(
            f"{path}:{block.start_line}: failed to parse {block.label}: {exc}"
        ) from exc


def _normalize_config_payload(payload: Any, path: Path, block: MarkpactBlock) -> dict[str, Any]:
    if isinstance(payload, dict) and len(payload) == 1:
        key = next(iter(payload))
        if key in _COMMON_CONFIG_WRAPPERS and isinstance(payload[key], dict):
            payload = payload[key]

    if not isinstance(payload, dict):
        raise MarkpactCompileError(
            f"{path}:{block.start_line}: {block.label} must compile to a mapping."
        )

    # Backward-compat: translate legacy post_deploy/pre_deploy → hooks before key validation.
    payload = _migrate_legacy_post_deploy(payload)

    unknown_top = sorted(set(payload) - _ALLOWED_SPEC_KEYS)
    if unknown_top:
        raise MarkpactCompileError(
            f"{path}:{block.start_line}: unsupported config keys: {', '.join(unknown_top)}"
        )

    for section in ("source", "target"):
        if section not in payload:
            continue
        if not isinstance(payload[section], dict):
            raise MarkpactCompileError(
                f"{path}:{block.start_line}: '{section}' must be a mapping."
            )
        unknown_nested = sorted(set(payload[section]) - _ALLOWED_INFRA_KEYS)
        if unknown_nested:
            raise MarkpactCompileError(
                f"{path}:{block.start_line}: unsupported {section} keys: {', '.join(unknown_nested)}"
            )

    return payload


def _extract_steps(payload: Any, path: Path, block: MarkpactBlock) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        steps = payload
    elif isinstance(payload, dict) and "extra_steps" in payload:
        steps = payload["extra_steps"]
    else:
        raise MarkpactCompileError(
            f"{path}:{block.start_line}: {block.label} must define a list of steps or an extra_steps list."
        )

    if not isinstance(steps, list):
        raise MarkpactCompileError(
            f"{path}:{block.start_line}: extra_steps must be a list."
        )

    validated: list[dict[str, Any]] = []
    for index, raw in enumerate(steps, start=1):
        if not isinstance(raw, dict):
            raise MarkpactCompileError(
                f"{path}:{block.start_line}: step #{index} in {block.label} must be a mapping."
            )

        unknown_keys = sorted(set(raw) - _ALLOWED_STEP_KEYS)
        if unknown_keys:
            raise MarkpactCompileError(
                f"{path}:{block.start_line}: unsupported step keys in '{raw.get('id', f'#{index}')}'"
                f": {', '.join(unknown_keys)}"
            )

        raw_for_validation = dict(raw)
        raw_for_validation.pop("insert_before", None)
        try:
            StepLibrary.resolve_from_spec(raw_for_validation)
        except Exception as exc:
            raise MarkpactCompileError(
                f"{path}:{block.start_line}: step '{raw.get('id', f'#{index}')}' is not supported by the current runtime: {exc}"
            ) from exc

        validated.append(dict(raw))

    return validated


def _deep_merge(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
            continue
        target[key] = value
