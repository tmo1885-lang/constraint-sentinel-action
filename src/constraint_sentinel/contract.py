"""Load and validate a task contract from a trusted Git base revision."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .patterns import PatternError, validate_pattern


class ContractError(ValueError):
    """An invalid or missing contract cannot authorize changes."""


@dataclass(frozen=True)
class RequiredCheck:
    name: str
    argv: tuple[str, ...]
    timeout_seconds: int
    report_format: str = "exit_code"


@dataclass(frozen=True)
class Contract:
    task_id: str
    allow: tuple[str, ...]
    protect: tuple[str, ...]
    test_paths: tuple[str, ...]
    deny_test_deletions: bool
    required_checks: tuple[RequiredCheck, ...]
    digest: str


def _glob_list(data: dict[str, Any], key: str, *, required: bool = False) -> tuple[str, ...]:
    value = data.get(key)
    if value is None and not required:
        return ()
    if not isinstance(value, list) or (required and not value):
        raise ContractError(f"{key} must be a nonempty array of glob patterns" if required
                            else f"{key} must be an array of glob patterns")
    try:
        patterns = tuple(validate_pattern(item) for item in value)
    except PatternError as exc:
        raise ContractError(str(exc)) from exc
    if len(set(patterns)) != len(patterns):
        raise ContractError(f"{key} contains duplicate patterns")
    return patterns


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ContractError(f"Duplicate contract key: {key!r}")
        obj[key] = value
    return obj


def _nonstandard_constant(value: str) -> None:
    raise ContractError(f"Non-JSON numeric constant: {value}")


def load_contract(raw: bytes) -> Contract:
    try:
        data = json.loads(
            raw, object_pairs_hook=_unique_object, parse_constant=_nonstandard_constant,
        )
    except ContractError:
        raise
    except (ValueError, UnicodeDecodeError) as exc:
        raise ContractError("Contract is not valid UTF-8 JSON") from exc
    if not isinstance(data, dict):
        raise ContractError("Contract must be a JSON object")
    allowed_keys = {
        "schema_version", "task_id", "allow", "protect", "test_paths",
        "deny_test_deletions", "required_checks",
    }
    unknown = set(data) - allowed_keys
    if unknown:
        raise ContractError(f"Unknown contract keys: {', '.join(sorted(unknown))}")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ContractError("Only schema_version 1 is supported")
    task_id = data.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 160:
        raise ContractError("task_id must be a nonempty string of at most 160 characters")
    allow = _glob_list(data, "allow", required=True)
    protect = _glob_list(data, "protect")
    test_paths = _glob_list(data, "test_paths")
    deny_test_deletions = data.get("deny_test_deletions", True)
    if type(deny_test_deletions) is not bool:
        raise ContractError("deny_test_deletions must be a boolean")
    if deny_test_deletions and not test_paths:
        raise ContractError("test_paths must be specified when deny_test_deletions is true")
    raw_checks = data.get("required_checks", [])
    if not isinstance(raw_checks, list):
        raise ContractError("required_checks must be an array")
    checks: list[RequiredCheck] = []
    seen: set[str] = set()
    if len(raw_checks) > 20:
        raise ContractError("At most 20 checks are supported")
    for item in raw_checks:
        required_fields = {"name", "argv", "timeout_seconds"}
        permitted_fields = required_fields | {"report_format"}
        if (not isinstance(item, dict) or
                not required_fields.issubset(item) or
                not set(item).issubset(permitted_fields)):
            raise ContractError("Each check needs name, argv, timeout_seconds; optional report_format")
        name, argv, timeout = item["name"], item["argv"], item["timeout_seconds"]
        report_format = item.get("report_format", "exit_code")
        if report_format not in ("exit_code", "proof_of_done_v0"):
            raise ContractError(
                f"Check {name!r} unsupported report_format: {report_format!r}"
            )
        if not isinstance(name, str) or not name.strip() or name in seen:
            raise ContractError("Check names must be unique nonempty strings")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(arg, str) and arg and "\x00" not in arg for arg in argv
        ):
            raise ContractError(f"Check {name!r} argv must be a nonempty string array")
        if type(timeout) is not int or not 1 <= timeout <= 600:
            raise ContractError(f"Check {name!r} timeout_seconds must be 1..600")
        seen.add(name)
        checks.append(RequiredCheck(name, tuple(argv), timeout, report_format))
    return Contract(
        task_id=task_id, allow=allow, protect=protect,
        test_paths=test_paths, deny_test_deletions=deny_test_deletions,
        required_checks=tuple(checks), digest=hashlib.sha256(raw).hexdigest(),
    )
