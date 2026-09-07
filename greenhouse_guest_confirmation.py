"""Read-only Greenhouse guest evidence validation; never submits or creates records.

Transition evidence is a trusted CALLER observation made around the canonical
one-shot invocation, not a DOM property or an assertion inferred from a URL.
Missing provenance means uncertain/inspection-only, including after a crash.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from html.parser import HTMLParser

from submission_authorization import BINDING_KEYS, _review_binding


class GuestConfirmationError(ValueError):
    """Guest submission cannot be attributed to one exact original intent."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_sha256(value: dict) -> str:
    return _sha256(json.dumps(value, sort_keys=True, separators=(",", ":")))


def is_permitted_confirmation_url(*, origin_url: str, page_url: str, tenant: str) -> bool:
    """Strict routing predicate, NOT submission evidence or navigation authority.

    Only canonical HTTPS job-board URLs are supported. Query strings, fragments,
    alternate hosts, general board pages and any other job are deliberately
    refused pending a separately verified route contract.
    """
    if not all(isinstance(value, str) and value for value in (origin_url, page_url, tenant)):
        return False
    origin = re.fullmatch(
        r"https://(job-boards\.greenhouse\.io|boards\.greenhouse\.io)/([a-z0-9][a-z0-9_-]*)/jobs/([0-9]+)",
        origin_url,
    )
    if origin is None or origin.group(2) != tenant:
        return False
    return page_url in {
        origin_url, origin_url + "/confirmation", origin_url + "/thank_you",
        f"https://{origin.group(1)}/{tenant}/thank_you",
    }


class _BodyTextParser(HTMLParser):
    """Exclude hidden/non-rendered HTML; actual innerText is also mandatory."""

    _NON_RENDERED = {"head", "script", "style", "template", "noscript"}
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    _BLOCK = {"body", "main", "section", "div", "p", "h1", "h2", "h3", "li", "br"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []
        self.chunks: list[str] = []
        self.active_application_control = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        style = re.sub(r"\s+", "", attributes.get("style") or "").casefold()
        hidden = bool(self.stack and self.stack[-1][1]) or (
            tag in self._NON_RENDERED or "hidden" in attributes
            or (tag == "input" and attributes.get("type") == "hidden")
            or (attributes.get("aria-hidden") or "").casefold() == "true"
            or "display:none" in style or "visibility:hidden" in style
        )
        if not hidden and "disabled" not in attributes and (
            (tag in {"input", "select", "textarea"} and "required" in attributes)
            or (tag == "button" and attributes.get("type") == "submit")
        ):
            self.active_application_control = True
        if tag not in self._VOID:
            self.stack.append((tag, hidden))
        if tag in self._BLOCK and not hidden:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if tag in self._BLOCK:
            self.chunks.append("\n")

    def handle_data(self, data):
        if self.stack and not self.stack[-1][1] and any(tag == "body" for tag, _ in self.stack):
            self.chunks.append(data)


def _success_sentences(text: str) -> set[str]:
    # Full statements, not substrings in instructions, questions or negations.
    statements = {" ".join(part.split()).casefold() for part in re.split(r"[.!\n]+", text)}
    return {statement for statement in statements if re.fullmatch(
        r"thank you for applying(?: to [a-z0-9 &,'’()-]+)?"
        r"|(?:your )?application (?:has been )?received"
        r"|(?:your )?application (?:has been )?(?:successfully )?submitted(?: successfully)?"
        r"|we(?: have|['’]ve) received your application",
        statement,
    )}


def extract_observed_success(snapshot: dict) -> dict:
    """Hash explicit success present in both actual innerText and visible HTML.

    No success is derived from URL spelling, data attributes, scripts, title,
    a sent request, or the one-shot click. Unknown wording stays unconfirmed.
    """
    parser = _BodyTextParser()
    parser.feed(snapshot["html"])
    parser.close()
    if parser.active_application_control or re.search(
        r"\b(?:could not (?:be submitted|submit)|has not been received|not submitted|"
        r"verify you are human|verify your (?:email|identity))\b",
        snapshot["body_text"], re.IGNORECASE,
    ):
        raise GuestConfirmationError("guest_confirmation_conflicting_form_or_gate")
    if not (_success_sentences(snapshot["body_text"]) & _success_sentences("".join(parser.chunks))):
        raise GuestConfirmationError("guest_explicit_rendered_success_missing")
    return {
        "confirmation_url": snapshot["url"], "reference_id": None,
        "submitted": True, "text_sha256": _sha256(snapshot["body_text"]),
    }


def validate_provenance(
    *, snapshot: dict, expected_identity: dict[str, str], target_id: str,
    origin_url: str, guest_submission: dict,
) -> dict:
    """Read the canonical intent and verify exact Review/transition binding."""
    job_id = guest_submission.get("job_id")
    review = guest_submission.get("review_evidence")
    if type(job_id) is not int or job_id <= 0 or not isinstance(review, dict):
        raise GuestConfirmationError("guest_original_review_missing")
    try:
        binding = _review_binding(review, job_id=job_id)
    except (ValueError, TypeError):
        raise GuestConfirmationError("guest_original_review_unverified") from None
    review_identity = review["binding"]
    if (
        binding["target_id"] != target_id or binding["page_url"] != origin_url
        or any(review_identity.get(key) != expected_identity[key] for key in ("company", "role", "requisition"))
    ):
        raise GuestConfirmationError("guest_original_identity_mismatch")

    try:
        entries = [json.loads(line) for line in Path(guest_submission["journal_path"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError, TypeError, KeyError):
        raise GuestConfirmationError("guest_submit_journal_unavailable") from None
    if not all(isinstance(entry, dict) and isinstance(entry.get("evidence"), dict) for entry in entries):
        raise GuestConfirmationError("guest_submit_journal_invalid")
    intents = [(index, entry["evidence"]) for index, entry in enumerate(entries)
               if entry.get("action") == "submit" and entry["evidence"].get("status") == "intent_recorded"]
    if len(intents) != 1:
        raise GuestConfirmationError("guest_requires_one_journaled_intent")
    intent_index, intent = intents[0]
    if (
        intent.get("verified") is not False
        or any(intent.get(key) != binding[key] for key in BINDING_KEYS)
        or not isinstance(intent.get("selector"), str) or not intent["selector"]
    ):
        raise GuestConfirmationError("guest_submit_intent_binding_mismatch")
    for entry in entries[intent_index + 1:]:
        evidence = entry["evidence"]
        if (
            entry.get("action") != "submit"
            or evidence.get("status") not in {"confirmation_observed", "confirmation_observed_after_interruption"}
            or evidence.get("verified") is not True
            or any(evidence.get(key) != intent.get(key) for key in (*BINDING_KEYS, "selector"))
        ):
            raise GuestConfirmationError("guest_submit_journal_changed_after_intent")

    transition = guest_submission.get("transition")
    if not isinstance(transition, dict) or (
        transition.get("source") != "one_shot_same_tab_observation"
        or transition.get("trusted") is not True
        or transition.get("target_id") != target_id
        or transition.get("from_url") != origin_url
        or transition.get("to_url") != snapshot.get("url")
        or transition.get("intent_sha256") != _canonical_sha256(intent)
    ):
        raise GuestConfirmationError("guest_trusted_transition_unverified")
    before_hash = transition.get("before_html_sha256")
    if (
        snapshot.get("read_only") is not True or snapshot.get("target_id") != target_id
        or not isinstance(snapshot.get("html"), str) or not snapshot["html"]
        or not isinstance(snapshot.get("body_text"), str) or not snapshot["body_text"]
        or not isinstance(before_hash, str) or re.fullmatch(r"[0-9a-f]{64}", before_hash) is None
        or transition.get("after_html_sha256") != _sha256(snapshot["html"])
        or transition.get("after_body_text_sha256") != _sha256(snapshot["body_text"])
        or before_hash == transition.get("after_html_sha256")
    ):
        raise GuestConfirmationError("guest_observation_missing_stale_or_changed")
    return {
        "source": "one_shot_same_tab_observation", "binding": binding,
        "intent_sha256": transition["intent_sha256"],
        "before_html_sha256": before_hash,
        "after_html_sha256": transition["after_html_sha256"],
        "after_body_text_sha256": transition["after_body_text_sha256"],
    }
