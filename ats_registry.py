from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import greenhouse_handler
import lever_handler
import njoyn_handler
import oracle_handler
import workday_handler


InspectHandler = Callable[..., dict]
MatchHandler = Callable[[str, str], bool]


@dataclass(frozen=True)
class ATSHandler:
    platform: str
    matches: MatchHandler
    inspect_html: InspectHandler


def _url_contains(*tokens: str) -> MatchHandler:
    lowered_tokens = tuple(token.casefold() for token in tokens)

    def matcher(page_url: str, html_text: str) -> bool:
        lowered_url = page_url.casefold()
        return any(token in lowered_url for token in lowered_tokens)

    return matcher


def _oracle_matcher(page_url: str, html_text: str) -> bool:
    lowered_url = page_url.casefold()
    lowered_html = html_text.casefold()
    if any(token in lowered_url for token in ("fa.oraclecloud.com", "oraclecloud", "oracle")):
        return True
    return any(
        token in lowered_html
        for token in (
            'data-field-type="combobox"',
            "apply-now-button",
            "postinglocationscontent",
        )
    )


HANDLERS: tuple[ATSHandler, ...] = (
    ATSHandler("greenhouse", _url_contains("greenhouse.io"), greenhouse_handler.inspect_html),
    ATSHandler(
        "workday",
        _url_contains("myworkdayjobs.com", "myworkdaysite.com", ".wd1.", ".wd5."),
        workday_handler.inspect_html,
    ),
    ATSHandler("lever", _url_contains("lever.co"), lever_handler.inspect_html),
    ATSHandler("njoyn", _url_contains("njoyn.com"), njoyn_handler.inspect_html),
    ATSHandler("oracle", _oracle_matcher, oracle_handler.inspect_html),
)


def resolve_handler(*, page_url: str, html_text: str) -> ATSHandler:
    for handler in HANDLERS:
        if handler.matches(page_url, html_text):
            return handler
    raise ValueError(f"Unsupported ATS for URL: {page_url}")
