"""Closed, versioned runtime contract for one exact live-operator run.

The manifest binds artifacts and identity but grants no browser or submission
authority.  Production use additionally requires caller-side enablement that
cannot be supplied by the manifest itself.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


SCHEMA_VERSION = 1
MODES = {"sanitized_local", "production_live"}
PLATFORMS = {"greenhouse", "workday", "lever", "oracle", "njoyn"}
TOP_LEVEL_FIELDS = {
    "schema_version",
    "mode",
    "job_id",
    "queue_id",
    "target",
    "identity",
    "profile",
    "resume",
    "manual_gate",
    "runtime_paths",
}
TARGET_FIELDS = {"id", "url"}
IDENTITY_FIELDS = {"company", "role", "requisition", "platform", "tenant"}
PROFILE_FIELDS = {"path", "sha256", "verified"}
RESUME_FIELDS = {"path", "basename", "content_type", "sha256", "verified"}
MANUAL_GATE_FIELDS = {"gates", "maango", "maango_approved", "verified"}
RUNTIME_PATH_FIELDS = {
    "preparation",
    "review",
    "authorization_db",
    "authorization_handoff",
    "submit_journal",
    "confirmation",
    "transaction_db",
    "status",
}
OBSERVED_BINDING_FIELDS = {
    "target_id",
    "page_url",
    "company",
    "role",
    "requisition",
    "platform",
    "tenant",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    """A live-run manifest is incomplete, surprising, or no longer exact."""


def _object(value: object, *, label: str) -> dict:
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be an object")
    return value


def _closed_fields(value: dict, expected: set[str], *, label: str) -> None:
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown:
        raise ManifestError(f"unknown manifest fields in {label}: {', '.join(unknown)}")
    if missing:
        raise ManifestError(f"missing manifest fields in {label}: {', '.join(missing)}")


def _nonempty_strings(value: dict, fields: set[str], *, label: str) -> None:
    if not all(isinstance(value.get(field), str) and value[field] for field in fields):
        raise ManifestError(f"{label} fields must be non-empty strings")


def _sha256(value: object, *, label: str) -> None:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise ManifestError(f"{label} must be a lowercase SHA-256 digest")


def _validate_binding(payload: dict, observed: dict) -> None:
    _closed_fields(observed, OBSERVED_BINDING_FIELDS, label="observed binding")
    expected = {
        "target_id": payload["target"]["id"],
        "page_url": payload["target"]["url"],
        **payload["identity"],
    }
    if observed != expected:
        raise ManifestError("exact target or job identity drift detected")


def validate_manifest(
    payload: object,
    *,
    production_enabled: bool = False,
    observed_binding: dict | None = None,
) -> dict:
    """Validate and return a v1 manifest without granting runtime authority."""
    manifest = _object(payload, label="manifest")
    _closed_fields(manifest, TOP_LEVEL_FIELDS, label="manifest")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError("unsupported live-run manifest schema version")
    mode = manifest.get("mode")
    if mode not in MODES:
        raise ManifestError("unsupported live-run mode")
    if mode == "production_live" and production_enabled is not True:
        raise ManifestError("production live mode was not explicitly enabled by the caller")
    if (
        not isinstance(manifest.get("job_id"), int)
        or isinstance(manifest.get("job_id"), bool)
        or manifest["job_id"] <= 0
        or not isinstance(manifest.get("queue_id"), str)
        or not manifest["queue_id"]
    ):
        raise ManifestError("positive job ID and non-empty queue ID are required")

    target = _object(manifest.get("target"), label="target")
    identity = _object(manifest.get("identity"), label="identity")
    profile = _object(manifest.get("profile"), label="profile evidence")
    resume = _object(manifest.get("resume"), label="resume evidence")
    manual_gate = _object(manifest.get("manual_gate"), label="manual-gate state")
    runtime_paths = _object(manifest.get("runtime_paths"), label="runtime paths")
    for value, expected, label in (
        (target, TARGET_FIELDS, "target"),
        (identity, IDENTITY_FIELDS, "identity"),
        (profile, PROFILE_FIELDS, "profile evidence"),
        (resume, RESUME_FIELDS, "resume evidence"),
        (manual_gate, MANUAL_GATE_FIELDS, "manual-gate state"),
        (runtime_paths, RUNTIME_PATH_FIELDS, "runtime paths"),
    ):
        _closed_fields(value, expected, label=label)

    _nonempty_strings(target, TARGET_FIELDS, label="target")
    _nonempty_strings(identity, IDENTITY_FIELDS, label="identity")
    if identity["platform"] not in PLATFORMS:
        raise ManifestError("manifest platform has no learned live contract")
    _nonempty_strings(profile, {"path"}, label="profile evidence")
    _nonempty_strings(
        resume, {"path", "basename", "content_type"}, label="resume evidence"
    )
    _sha256(profile.get("sha256"), label="profile evidence hash")
    _sha256(resume.get("sha256"), label="resume evidence hash")
    if profile.get("verified") is not True:
        raise ManifestError("profile evidence must be independently verified")
    if (
        resume.get("verified") is not True
        or resume.get("basename") != "Resume.pdf"
        or resume.get("content_type") != "application/pdf"
    ):
        raise ManifestError("resume evidence must bind an exact verified Resume.pdf")

    gates = manual_gate.get("gates")
    if (
        not isinstance(gates, list)
        or not all(isinstance(gate, str) and gate for gate in gates)
        or manual_gate.get("verified") is not True
        or not isinstance(manual_gate.get("maango"), bool)
        or not isinstance(manual_gate.get("maango_approved"), bool)
        or (manual_gate["maango_approved"] and not manual_gate["maango"])
    ):
        raise ManifestError("manual-gate state must be explicit and verified")

    _nonempty_strings(runtime_paths, RUNTIME_PATH_FIELDS, label="runtime paths")
    paths = [Path(runtime_paths[field]) for field in sorted(RUNTIME_PATH_FIELDS)]
    if not all(path.is_absolute() for path in paths) or len(set(paths)) != len(paths):
        raise ManifestError("runtime paths must be unique absolute paths")

    if observed_binding is not None:
        _validate_binding(manifest, _object(observed_binding, label="observed binding"))
    return manifest


def load_manifest(
    path: Path | str,
    *,
    production_enabled: bool = False,
    observed_binding: dict | None = None,
) -> dict:
    """Read and validate a manifest from an explicitly supplied runtime path."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"live-run manifest could not be read: {exc}") from exc
    return validate_manifest(
        payload,
        production_enabled=production_enabled,
        observed_binding=observed_binding,
    )
