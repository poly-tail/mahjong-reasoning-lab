from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import os
import re
from typing import Iterable, Optional
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from capture.fragment_parser import load_from_xml_text
from capture.state import GameState

# DEFAULT_XML_URL_TIMEOUT_S の定義。
DEFAULT_XML_URL_TIMEOUT_S = 20.0
# XML_URL_USER_AGENT の定義。
XML_URL_USER_AGENT = "tenhou-hojo/1.0"
# _LOG_XML_REF_PATTERN の定義。
_LOG_XML_REF_PATTERN = re.compile(r"log/\?[^\"'\s<>]+", re.IGNORECASE)


class _ReferenceCollector(HTMLParser):
    """Collect href/src-like references from an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        for attr_name, attr_value in attrs:
            if attr_name.lower() not in {"href", "src", "data-href"}:
                continue
            if attr_value:
                self.references.append(attr_value)


# ResolvedXmlUrl クラスを定義する。
@dataclass(frozen=True)
class ResolvedXmlUrl:
    # input_url を保持する。
    input_url: str
    # xml_url を保持する。
    xml_url: str
    # viewer_tw を保持する。
    viewer_tw: Optional[int] = None


# FetchedXmlLog クラスを定義する。
@dataclass(frozen=True)
class FetchedXmlLog:
    # resolved を保持する。
    resolved: ResolvedXmlUrl
    # xml_text を保持する。
    xml_text: str


def _fetch_text(url: str, *, timeout_s: float) -> str:
    """Fetch text content from the provided URL using a small custom user-agent."""

    request = Request(url, headers={"User-Agent": XML_URL_USER_AGENT})
    previous_ssl_keylogfile = os.environ.pop("SSLKEYLOGFILE", None)
    try:
        with urlopen(request, timeout=timeout_s) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    finally:
        if previous_ssl_keylogfile is not None:
            os.environ["SSLKEYLOGFILE"] = previous_ssl_keylogfile


def _looks_like_log_xml_reference(reference: str) -> bool:
    """Return whether a reference points at a `log/?...` XML payload."""

    parsed = urlparse(reference)
    path = parsed.path.lstrip("/")
    if path == "log/" and bool(parsed.query):
        return True
    return reference.startswith("log/?") or "/log/?" in reference


def _iter_log_xml_candidates(page_text: str, base_url: str) -> Iterable[str]:
    """Yield absolute candidate XML URLs discovered in a page."""

    parser = _ReferenceCollector()
    parser.feed(page_text)
    for reference in parser.references:
        normalized_reference = unescape(reference.strip())
        if not _looks_like_log_xml_reference(normalized_reference):
            continue
        yield urljoin(base_url, normalized_reference)

    for match in _LOG_XML_REF_PATTERN.finditer(page_text):
        yield urljoin(base_url, match.group(0))


def extract_viewer_tw(url: str) -> Optional[int]:
    """Extract `tw` from a viewer URL when it is a valid absolute seat."""

    values = parse_qs(urlparse(url).query).get("tw")
    if not values:
        return None
    try:
        tw = int(values[0])
    except ValueError:
        return None
    if 0 <= tw <= 3:
        return tw
    return None


def extract_log_id(url: str) -> Optional[str]:
    """Extract the Tenhou `log=` payload id from a viewer-style URL."""

    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("log")
    if values:
        log_id = (values[0] or "").strip()
        if log_id:
            return log_id
    if parsed.path.lstrip("/") == "log/" and parsed.query:
        log_id = parsed.query.strip()
        return log_id or None
    return None


def _build_canonical_xml_url(log_id: str) -> str:
    """Build the canonical Tenhou XML endpoint from a bare log id."""

    return f"https://tenhou.net/0/log/?{log_id}"


def resolve_xml_log_url(input_url: str, *, timeout_s: float = DEFAULT_XML_URL_TIMEOUT_S) -> ResolvedXmlUrl:
    """Resolve a user-provided URL into the actual Tenhou `log/?...` XML URL."""

    viewer_tw = extract_viewer_tw(input_url)
    log_id = extract_log_id(input_url)
    if log_id:
        return ResolvedXmlUrl(
            input_url=input_url,
            xml_url=_build_canonical_xml_url(log_id),
            viewer_tw=viewer_tw,
        )
    if _looks_like_log_xml_reference(input_url):
        return ResolvedXmlUrl(input_url=input_url, xml_url=input_url, viewer_tw=viewer_tw)

    page_text = _fetch_text(input_url, timeout_s=timeout_s)
    for candidate_url in _iter_log_xml_candidates(page_text, input_url):
        return ResolvedXmlUrl(input_url=input_url, xml_url=candidate_url, viewer_tw=viewer_tw)

    raise ValueError(f"Could not find a log/? XML link from URL: {input_url}")


def fetch_xml_text_from_url(
    input_url: str,
    *,
    timeout_s: float = DEFAULT_XML_URL_TIMEOUT_S,
) -> FetchedXmlLog:
    """Resolve and fetch a Tenhou XML log from a user-provided URL."""

    resolved = resolve_xml_log_url(input_url, timeout_s=timeout_s)
    xml_text = _fetch_text(resolved.xml_url, timeout_s=timeout_s)
    return FetchedXmlLog(resolved=resolved, xml_text=xml_text)


def load_from_xml_url(
    input_url: str,
    *,
    self_abs_seat: Optional[int] = None,
    self_player_name: Optional[str] = None,
    timeout_s: float = DEFAULT_XML_URL_TIMEOUT_S,
) -> GameState:
    """Fetch a Tenhou XML log from a URL, then parse it into GameState."""

    fetched = fetch_xml_text_from_url(input_url, timeout_s=timeout_s)
    resolved = fetched.resolved
    effective_self_abs_seat = self_abs_seat if self_abs_seat is not None else resolved.viewer_tw
    state = load_from_xml_text(
        fetched.xml_text,
        self_abs_seat=effective_self_abs_seat,
        self_player_name=self_player_name,
    )
    state.diagnostics.append(
        {
            "level": "info",
            "code": "xml_url_loaded",
            "input_url": resolved.input_url,
            "xml_url": resolved.xml_url,
            "viewer_tw": resolved.viewer_tw,
            "self_abs_seat": state.self_abs_seat,
        }
    )
    return state
