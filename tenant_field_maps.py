"""Versioned exact-tenant field maps and conditional learned ATS steps."""
from __future__ import annotations

from copy import deepcopy
from urllib.parse import urlparse

import browser_actions


class FieldMapError(ValueError):
    """A tenant, semantic field, operation, or step is not learned."""


class ControlDriftError(ValueError):
    """A learned selector was not present on the exact current step."""


def _control(selector: str, operation: str) -> dict[str, str]:
    return {"selector": selector, "operation": operation}


REGISTRY: tuple[dict, ...] = (
    {
        "version": 1,
        "platform": "greenhouse",
        "tenant": "fixture",
        "hostname": "job-boards.greenhouse.io",
        "path_prefix": "/fixture/",
        "steps": {
            "application": {
                "controls": {
                    "first_name": _control("#first_name", "replace_text"),
                    "last_name": _control("#last_name", "replace_text"),
                    "email": _control("#email", "replace_text"),
                    "phone": _control("#phone", "replace_text"),
                    "resume": _control("#resume", "cdp_upload"),
                    "work_authorization": _control("#authorization", "native_select"),
                    "sponsorship": _control("#sponsorship", "native_select"),
                },
                "required_fields": ["first_name", "last_name", "email", "phone", "resume", "work_authorization", "sponsorship"],
                "required_conditions": [],
                "next_step": "review",
            },
            "review": {
                "controls": {"submit": _control("#submit", "submit")},
                "required_fields": [],
                "required_conditions": ["authoritative_review"],
                "next_step": None,
            },
        },
    },
    {
        "version": 1,
        "platform": "workday",
        "tenant": "fixture",
        "hostname": "fixture.wd1.myworkdayjobs.com",
        "path_prefix": "/",
        "steps": {
            "my_information": {
                "controls": {
                    "email": _control("#wd_email", "replace_text"),
                    "phone": _control("#wd_phone", "replace_text"),
                },
                "required_fields": ["email", "phone"],
                "required_conditions": [],
                "next_step": "experience",
            },
            "experience": {
                "controls": {
                    "resume": _control("#wd_resume", "cdp_upload"),
                    "school": _control("#wd_school", "replace_text"),
                },
                "required_fields": ["resume"],
                "required_conditions": ["parser_repairs_verified"],
                "next_step": "application_questions",
            },
            "application_questions": {
                "controls": {
                    "work_authorization": _control("#wd_auth", "native_select"),
                    "sponsorship": _control("#wd_sponsor", "native_select"),
                },
                "required_fields": ["work_authorization", "sponsorship"],
                "required_conditions": ["required_questions_verified"],
                "next_step": "review",
            },
            "review": {
                "controls": {"submit": _control("#wd_submit", "submit")},
                "required_fields": [],
                "required_conditions": ["authoritative_review"],
                "next_step": None,
            },
        },
    },
    {
        "version": 1,
        "platform": "lever",
        "tenant": "fixture",
        "hostname": "jobs.lever.co",
        "path_prefix": "/fixture/",
        "steps": {
            "application": {
                "controls": {
                    "full_name": _control("#name", "replace_text"),
                    "email": _control("#email", "replace_text"),
                    "resume": _control("#resume", "cdp_upload"),
                    "linkedin": _control("#linkedin", "replace_text"),
                },
                "required_fields": ["full_name", "email", "resume"],
                "required_conditions": [],
                "next_step": "review",
            },
            "review": {
                "controls": {"submit": _control("#application-form button[type='submit']", "submit")},
                "required_fields": [],
                "required_conditions": ["authoritative_review"],
                "next_step": None,
            },
        },
    },
    {
        "version": 1,
        "platform": "oracle",
        "tenant": "example",
        "hostname": "careers.example.test",
        "path_prefix": "/",
        "steps": {
            "application": {
                "controls": {
                    "first_name": _control("#first_name", "replace_text"),
                    "country": _control("#country", "human_required"),
                    "resume": _control("#resume", "cdp_upload"),
                    "salary": _control("#salary", "human_required"),
                },
                "required_fields": ["first_name", "country", "resume", "salary"],
                "required_conditions": ["oracle_comboboxes_verified"],
                "next_step": "review",
            },
            "review": {
                "controls": {"submit": _control("[data-automation-id='submit']", "submit")},
                "required_fields": [],
                "required_conditions": ["authoritative_review"],
                "next_step": None,
            },
        },
    },
    {
        "version": 1,
        "platform": "njoyn",
        "tenant": "cgi",
        "hostname": "cgi.njoyn.com",
        "path_prefix": "/",
        "steps": {
            "account": {
                "controls": {
                    "email": _control("[name='email']", "human_required"),
                    "password": _control("[name='password']", "human_required"),
                },
                "required_fields": [],
                "required_conditions": ["authenticated_session"],
                "next_step": "privacy",
            },
            "privacy": {
                "controls": {"privacy_acknowledged": _control("[name='privacy_acknowledged']", "set_checked")},
                "required_fields": ["privacy_acknowledged"],
                "required_conditions": [],
                "next_step": "disclosures",
            },
            "disclosures": {
                "controls": {
                    "work_authorization": _control("[name='authorized'][value='yes']", "set_checked"),
                    "sponsorship": _control("[name='sponsorship'][value='no']", "set_checked"),
                },
                "required_fields": ["work_authorization", "sponsorship"],
                "required_conditions": [],
                "next_step": "disability",
            },
            "disability": {
                "controls": {"disability": _control("[name='disability']", "native_select")},
                "required_fields": ["disability"],
                "required_conditions": [],
                "next_step": "resume_upload",
            },
            "resume_upload": {
                "controls": {"resume": _control("[name='resume']", "cdp_upload")},
                "required_fields": ["resume"],
                "required_conditions": [],
                "next_step": "parsed_profile",
            },
            "parsed_profile": {
                "controls": {
                    "first_name": _control("[name='first_name']", "replace_text"),
                    "school": _control("[name='school']", "replace_text"),
                },
                "required_fields": ["first_name", "school"],
                "required_conditions": ["parser_repairs_verified"],
                "next_step": "referral",
            },
            "referral": {
                "controls": {
                    "source": _control("[name='source']", "native_select"),
                    "source_detail": _control("[name='source_detail']", "native_select"),
                },
                "required_fields": ["source", "source_detail"],
                "required_conditions": ["referral_options_verified"],
                "next_step": "questionnaire",
            },
            "questionnaire": {
                "controls": {
                    "age": _control("[name='age']", "native_select"),
                    "compensation": _control("[name='compensation']", "replace_text"),
                },
                "required_fields": ["age", "compensation"],
                "required_conditions": ["required_questions_verified"],
                "next_step": "review",
            },
            "review": {
                "controls": {"submit": _control("button[type='submit']", "submit")},
                "required_fields": [],
                "required_conditions": ["authoritative_review"],
                "next_step": None,
            },
        },
    },
)


def resolve_field_map(*, page_url: str, platform: str) -> dict:
    parsed = urlparse(page_url)
    normalized_platform = platform.strip().casefold()
    matches = [
        item
        for item in REGISTRY
        if item["platform"] == normalized_platform
        and parsed.hostname == item["hostname"]
        and parsed.path.startswith(item["path_prefix"])
    ]
    if parsed.scheme != "https" or len(matches) != 1:
        raise FieldMapError("unknown exact learned tenant for platform and URL")
    return deepcopy(matches[0])


def build_step_actions(
    *,
    mapping: dict,
    step: str,
    approved_answers: dict[str, object],
    observed_selectors: set[str] | None = None,
) -> list[dict[str, object]]:
    if mapping.get("version") != 1:
        raise FieldMapError("unsupported learned field-map version")
    step_map = mapping.get("steps", {}).get(step)
    if not isinstance(step_map, dict):
        raise FieldMapError("unknown learned tenant step")
    controls = step_map.get("controls", {})
    if not isinstance(approved_answers, dict) or not approved_answers:
        raise FieldMapError("approved semantic answers are required")
    actions = []
    for field, value in approved_answers.items():
        control = controls.get(field)
        if not isinstance(control, dict):
            raise FieldMapError(f"unknown semantic field for learned step: {field}")
        selector = control["selector"]
        operation = control["operation"]
        if observed_selectors is not None and selector not in observed_selectors:
            raise ControlDriftError(f"learned control drift for semantic field: {field}")
        if operation == "human_required":
            raise FieldMapError(f"semantic field requires human handling: {field}")
        if operation == "submit":
            raise FieldMapError("submit controls cannot be used as approved answer fields")
        if operation == "set_checked":
            if not isinstance(value, bool):
                raise FieldMapError(f"checked semantic field requires a boolean: {field}")
        elif not isinstance(value, str) or not value:
            raise FieldMapError(f"semantic field requires a non-empty string: {field}")
        actions.append({
            "field": field,
            "operation": operation,
            "selector": selector,
            "value": value,
        })
    return actions


def plan_next_step(
    *,
    mapping: dict,
    current_step: str,
    completed_fields: set[str],
    conditions: dict[str, bool],
) -> dict[str, object]:
    step = mapping.get("steps", {}).get(current_step)
    if not isinstance(step, dict):
        raise FieldMapError("unknown learned tenant step")
    blockers = [
        field for field in step.get("required_fields", []) if field not in completed_fields
    ]
    blockers.extend(
        condition
        for condition in step.get("required_conditions", [])
        if conditions.get(condition) is not True
    )
    if blockers:
        return {
            "status": "human_required",
            "current_step": current_step,
            "next_step": current_step,
            "human_required": blockers,
        }
    next_step = step.get("next_step")
    return {
        "status": "advance" if isinstance(next_step, str) else "stop_before_submit",
        "current_step": current_step,
        "next_step": next_step,
        "human_required": [],
    }


def execute_step_actions(
    *, page: object, target_id: str, expected_url: str, actions: list[dict[str, object]]
) -> dict[str, object]:
    evidence = []
    for action in actions:
        snapshot = page.read_only_snapshot()  # type: ignore[attr-defined]
        if (
            snapshot.get("read_only") is not True
            or snapshot.get("target_id") != target_id
            or snapshot.get("url") != expected_url
        ):
            raise ControlDriftError("exact target drift before learned field action")
        operation = action["operation"]
        selector = action["selector"]
        value = action["value"]
        if operation == "replace_text":
            item = browser_actions.replace_text(page, selector, value)  # type: ignore[arg-type]
        elif operation == "native_select":
            item = browser_actions.native_select(page, selector, value)  # type: ignore[arg-type]
        elif operation == "set_checked":
            item = browser_actions.set_checked(page, selector, value)  # type: ignore[arg-type]
        elif operation == "cdp_upload":
            item = browser_actions.cdp_upload(page, selector, value)  # type: ignore[arg-type]
        else:
            raise FieldMapError(f"unsupported learned field operation: {operation}")
        evidence.append({
            **item,
            "field": action["field"],
            "target_id": target_id,
            "target_url": expected_url,
        })
    return {
        "action": "apply_learned_step",
        "field_evidence": evidence,
        "verified": bool(evidence) and all(item.get("verified") is True for item in evidence),
    }
