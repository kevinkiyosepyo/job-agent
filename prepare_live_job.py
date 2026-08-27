"""Non-submitting exact-target live preparation orchestration.

The command seam deliberately accepts an already bound page adapter. It never
navigates, submits, reaches credentials, tracker, or notification services. Its
only durable result is sanitized Review-ready evidence.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import urlsplit

from answer_coverage import build_coverage_matrix
from cdp_page_executor import CDPPageExecutor
from prepare_job import prepare_saved_html
from scoped_cdp import ScopedCDPTransport
from tenant_field_maps import build_step_actions, execute_step_actions, resolve_field_map


class ReadOnlyLivePage(Protocol):
    target_id: str

    def read_only_snapshot(self) -> dict[str, object]: ...


class LivePreparationError(ValueError):
    """Live preparation cannot safely proceed without exact identity evidence."""


Prepare = Callable[..., dict]
Coverage = Callable[..., dict]
TransportFactory = Callable[[str], object]


def _identity(payload: dict) -> dict[str, str]:
    return {key: str(payload.get(key, "")) for key in ("company", "role", "requisition")}


def prepare_live_job(
    *,
    page: ReadOnlyLivePage,
    target_id: str,
    expected_url: str,
    expected_identity: dict[str, str],
    profile: dict,
    prepare: Prepare,
    coverage: Coverage,
    approved_answers: dict[str, object] | None = None,
    apply_known: Callable[[dict[str, object]], dict[str, object]] | None = None,
) -> dict:
    """Inspect one fresh exact target and emit non-submitting Review evidence."""
    snapshot = page.read_only_snapshot()
    if snapshot.get("read_only") is not True or snapshot.get("target_id") != target_id:
        raise LivePreparationError("exact trusted target binding is required")
    if snapshot.get("url") != expected_url:
        raise LivePreparationError("target URL changed before live preparation")
    html = snapshot.get("html")
    if not isinstance(html, str):
        raise LivePreparationError("exact target did not return sanitized HTML evidence")

    prepared = prepare(html_text=html, page_url=expected_url)
    identity = _identity(prepared)
    expected = {key: str(expected_identity.get(key, "")) for key in identity}
    if identity != expected:
        raise LivePreparationError("company, role, or requisition changed before live preparation")
    if prepared.get("submission_enabled") is not False:
        raise LivePreparationError("live preparation must remain non-submitting")

    questions = prepared.get("questions", [])
    if not isinstance(questions, list):
        raise LivePreparationError("handler returned invalid question inventory")
    answer_coverage = coverage(profile=profile, questions=questions, company=identity["company"])
    answers = dict(approved_answers or {})
    if answers and apply_known is None:
        raise LivePreparationError("approved answers require an exact-target apply operation")
    applied_answers = apply_known(answers) if answers else {
        "action": "fill_known_page", "field_evidence": [], "verified": True,
    }
    if applied_answers.get("verified") is not True:
        raise LivePreparationError("approved answer read-back was not verified")
    review_ready = not answer_coverage.get("human_required")
    return {
        "target_id": target_id,
        "page_url": expected_url,
        "identity": identity,
        "platform": prepared.get("platform", ""),
        "submission_enabled": False,
        "review_ready": review_ready,
        "answer_coverage": answer_coverage,
        "applied_answers": applied_answers,
        "evidence": {"sanitized": True, "target_bound": True},
    }


def _load_json_object(path: str, *, label: str) -> dict:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise LivePreparationError(f"{label} must be a JSON object")
    return payload


def _validate_local_cdp_base_url(base_url: str) -> None:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise LivePreparationError("CDP base URL must be an uncredentialed loopback HTTP origin")


def _questions_from_fields(payload: dict) -> list[dict[str, object]]:
    fields = payload.get("fields", [])
    if not isinstance(fields, list):
        raise LivePreparationError("handler returned an invalid field inventory")
    questions: list[dict[str, object]] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        label = field.get("label") or field.get("name")
        if isinstance(label, str) and label:
            questions.append({"label": label, "required": field.get("required") is True})
    return questions


def _has_exact_identity(text: str, value: str) -> bool:
    if not value:
        return False
    return re.search(r"(?<![\w-])" + re.escape(value) + r"(?![\w-])", text) is not None


def _dispatch_live_html(
    *,
    html_text: str,
    page_url: str,
    expected_identity: dict[str, str],
    expected_platform: str | None = None,
) -> dict:
    payload = prepare_saved_html(html_text=html_text, page_url=page_url)
    if expected_platform is not None and payload.get("platform") != expected_platform:
        raise LivePreparationError("learned field-map platform did not match ATS handler")
    manual_gates = payload.get("manual_gates") or (
        [payload["manual_gate"]] if payload.get("manual_gate") else []
    )
    if manual_gates:
        raise LivePreparationError("handler reported a human-required gate before preparation")
    if payload.get("page_type") not in {None, "application"}:
        raise LivePreparationError("handler did not report an application form surface")

    identity_sources = {
        "company": html_text,
        "role": html_text,
        "requisition": f"{html_text}\n{page_url}",
    }
    for key, expected in expected_identity.items():
        observed = payload.get(key)
        if not observed and _has_exact_identity(identity_sources[key], expected):
            payload[key] = expected
    payload["questions"] = _questions_from_fields(payload)
    return payload


def _apply_text_answers(
    *, page: object, target_id: str, expected_url: str, answers: dict[str, str]
) -> dict[str, object]:
    executor = CDPPageExecutor(page)  # type: ignore[arg-type]
    field_evidence = [
        executor.replace_text(
            target_id=target_id,
            expected_url=expected_url,
            selector=selector,
            value=value,
        )
        for selector, value in answers.items()
    ]
    return {
        "action": "fill_known_page",
        "field_evidence": field_evidence,
        "verified": bool(field_evidence) and all(item.get("verified") is True for item in field_evidence),
    }


def _sanitize_review_evidence(payload: dict) -> dict:
    applied = payload.get("applied_answers", {})
    sanitized_fields = []
    for field in applied.get("field_evidence", []):
        sanitized_fields.append({
            key: field[key]
            for key in ("action", "field", "selector", "verified", "target_id", "target_url")
            if key in field
        })
    return {
        **payload,
        "applied_answers": {
            "action": applied.get("action", "fill_known_page"),
            "field_evidence": sanitized_fields,
            "verified": applied.get("verified") is True,
        },
        "evidence": {
            **payload.get("evidence", {}),
            "answer_values_persisted": False,
        },
    }


def main(
    argv: list[str] | None = None,
    *,
    transport_factory: TransportFactory = ScopedCDPTransport,
    prepare: Prepare | None = None,
    coverage: Coverage = build_coverage_matrix,
) -> int:
    parser = argparse.ArgumentParser(description="Prepare one exact-bound live ATS page without submitting")
    parser.add_argument("--cdp-base-url", default="http://127.0.0.1:9222")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--expected-url", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--requisition", required=True)
    parser.add_argument("--platform")
    parser.add_argument("--step")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--approved-answers", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    try:
        _validate_local_cdp_base_url(args.cdp_base_url)
        expected_identity = {
            "company": args.company,
            "role": args.role,
            "requisition": args.requisition,
        }
        if not args.target_id or not all(expected_identity.values()):
            raise LivePreparationError("target and expected identity values must be non-empty")
        profile = _load_json_object(args.profile, label="profile")
        approved_answers = _load_json_object(args.approved_answers, label="approved answers")
        if not approved_answers or not all(
            isinstance(field, str) and bool(field) for field in approved_answers
        ):
            raise LivePreparationError("approved answers must be a non-empty object")

        learned_actions = None
        if prepare is None:
            if not isinstance(args.platform, str) or not args.platform or not isinstance(args.step, str) or not args.step:
                raise LivePreparationError("default live preparation requires exact platform and learned step")
            mapping = resolve_field_map(page_url=args.expected_url, platform=args.platform)
            learned_actions = build_step_actions(
                mapping=mapping,
                step=args.step,
                approved_answers=approved_answers,
            )
            selected_prepare = lambda **kwargs: _dispatch_live_html(
                **kwargs,
                expected_identity=expected_identity,
                expected_platform=args.platform,
            )
        else:
            if not all(isinstance(value, str) for value in approved_answers.values()):
                raise LivePreparationError("injected preparation answers must be selector-to-string values")
            selected_prepare = prepare
        transport = transport_factory(args.cdp_base_url)
        with transport.bind_mutable_page_target(args.target_id) as page:  # type: ignore[attr-defined]
            if learned_actions is not None:
                apply_operation = lambda answers: execute_step_actions(
                    page=page,
                    target_id=args.target_id,
                    expected_url=args.expected_url,
                    actions=learned_actions,
                )
            else:
                apply_operation = lambda answers: _apply_text_answers(
                    page=page,
                    target_id=args.target_id,
                    expected_url=args.expected_url,
                    answers=answers,  # type: ignore[arg-type]
                )
            result = prepare_live_job(
                page=page,
                target_id=args.target_id,
                expected_url=args.expected_url,
                expected_identity=expected_identity,
                profile=profile,
                prepare=selected_prepare,
                coverage=coverage,
                approved_answers=approved_answers,
                apply_known=apply_operation,
            )
        sanitized = _sanitize_review_evidence(result)
        Path(args.output).write_text(json.dumps(sanitized, indent=2, sort_keys=True) + "\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "error": str(exc),
            "submission_enabled": False,
            "review_evidence_persisted": False,
        }))
        return 2

    print(json.dumps(sanitized, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
