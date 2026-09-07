"""Learned, exact-target readers for provenance-aware ATS Review state.

Readers are observation-only. The exact Schonfeld guest surface requires
explicit live_client_bound_form provenance; it cannot fall back to server state.
A page-specific learned adapter may expose
``read_<platform>_server_review`` (or the shared ``read_server_review`` seam).
The conservative mapped fallback reads only known controls and leaves evidence
unverified when a tenant cannot expose a server resume hash or question state.
"""
from __future__ import annotations


SUPPORTED_PLATFORMS = frozenset({"greenhouse", "workday", "lever", "oracle", "njoyn"})


class LiveReviewReadError(ValueError):
    """The exact Review surface could not be observed through a learned seam."""


def _snapshot(page: object, *, target_id: str, page_url: str) -> dict:
    payload = page.read_only_snapshot()  # type: ignore[attr-defined]
    if (
        not isinstance(payload, dict)
        or payload.get("read_only") is not True
        or payload.get("target_id") != target_id
        or payload.get("url") != page_url
    ):
        raise LiveReviewReadError("exact Review target drift detected")
    return payload


def _mapped_review(
    *,
    page: object,
    mapping: dict,
    step: str,
    target_id: str,
    page_url: str,
    identity: dict[str, str],
    required_parser_repairs: list[str],
    required_question_ids: list[str],
) -> dict:
    step_map = mapping.get("steps", {}).get(step, {})
    controls = step_map.get("controls", {}) if isinstance(step_map, dict) else {}
    if not isinstance(controls, dict) or not controls:
        raise LiveReviewReadError("learned Review controls are unavailable for this step")
    fields: dict[str, object] = {}
    resume: dict[str, object] = {"basename": "", "sha256": ""}
    for control in controls.values():
        if not isinstance(control, dict):
            continue
        selector = control.get("selector")
        operation = control.get("operation")
        if not isinstance(selector, str):
            continue
        if operation == "replace_text":
            fields[selector] = page.read_value(selector)  # type: ignore[attr-defined]
        elif operation == "replace_tel_local_digits":
            value = page.read_value(selector)  # type: ignore[attr-defined]
            fields[selector] = "".join(character for character in value if character.isdigit())
        elif operation == "native_select":
            fields[selector] = page.read_selected_option(selector)  # type: ignore[attr-defined]
        elif operation == "react_select_exact":
            fields[selector] = page.read_react_selected_option(selector)  # type: ignore[attr-defined]
        elif operation == "set_checked":
            fields[selector] = page.read_checked(selector)  # type: ignore[attr-defined]
        elif operation == "cdp_upload":
            resume["basename"] = page.read_uploaded_filename(selector)  # type: ignore[attr-defined]
            hash_reader = getattr(page, "read_uploaded_sha256", None)
            if callable(hash_reader):
                resume["sha256"] = hash_reader(selector)
            # A filename is observation, not upload or server-save verification.
            resume["verified"] = False
    return {
        "source": "unverified_mapped_form",
        "server_saved": False,
        "target_id": target_id,
        "page_url": page_url,
        "identity": dict(identity),
        "fields": fields,
        "resume": resume,
        "parser_repairs": [
            {"field": field, "verified": False} for field in required_parser_repairs
        ],
        "questions": [
            {
                "id": question_id,
                "required": True,
                "answered": False,
                "verified": False,
            }
            for question_id in required_question_ids
        ],
    }


def read_server_review(
    *,
    page: object,
    platform: str,
    mapping: dict,
    step: str,
    target_id: str,
    page_url: str,
    identity: dict[str, str],
    required_parser_repairs: list[str],
    required_question_ids: list[str],
) -> dict:
    """Read one fresh learned Review surface without mutating or navigating."""
    if platform not in SUPPORTED_PLATFORMS or mapping.get("platform") != platform:
        raise LiveReviewReadError("learned Review reader platform mismatch")
    _snapshot(page, target_id=target_id, page_url=page_url)
    from schonfeld_form import URL as SCHONFELD_URL
    client_bound = platform == "greenhouse" and page_url == SCHONFELD_URL and mapping.get("tenant") == "schonfeld"
    reader = getattr(page, "read_greenhouse_client_bound_form", None) if client_bound else getattr(page, f"read_{platform}_server_review", None)
    if client_bound and not callable(reader):
        raise LiveReviewReadError("learned live client-bound form reader unavailable")
    if not callable(reader):
        reader = getattr(page, "read_server_review", None)
    if callable(reader):
        result = reader()
        if not isinstance(result, dict):
            raise LiveReviewReadError("learned Review reader returned invalid evidence")
        if not (
            (result.get("source") == "server_saved_review" and result.get("server_saved") is True)
            or (result.get("source") == "live_client_bound_form" and result.get("server_saved") is False)
        ):
            raise LiveReviewReadError("explicit consistent Review provenance required")
    else:
        result = _mapped_review(
            page=page,
            mapping=mapping,
            step=step,
            target_id=target_id,
            page_url=page_url,
            identity=identity,
            required_parser_repairs=required_parser_repairs,
            required_question_ids=required_question_ids,
        )
    _snapshot(page, target_id=target_id, page_url=page_url)
    if client_bound:
        if result.get("source") != "live_client_bound_form" or result.get("server_saved") is not False:
            raise LiveReviewReadError("client-bound form provenance required")
        result["identity"] = dict(identity)
        result["parser_repairs"] = [
            {"field": field, "verified": result.get("bindings", {}).get(field, {}).get("bound") is True}
            for field in required_parser_repairs
        ]
    return result
