"""Apify Pay-Per-Event Actor: Greenhouse, Lever & Ashby ATS Jobs Board Extractor."""

from __future__ import annotations

import asyncio
import email.utils
import html
import ipaddress
import json
import re
import socket
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import httpx

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK installed.
    Actor = None  # type: ignore[assignment]

USER_AGENT = "HorizonATSJobsExtractor/1.0 (+https://github.com/pecopeko/apify-ppe-actors)"
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_RETRY_STATUSES = frozenset({429, 503})
_FORBIDDEN_HOSTS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata.google.internal",
        "metadata.goog",
        "metadata",
    }
)
_FORBIDDEN_HOST_SUFFIXES = (".local", ".internal", ".localhost")
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_ESCAPED_HTML_TAG_RE = re.compile(r"&lt;/?[A-Za-z][A-Za-z0-9]*[\s&]")

SUPPORTED_PROVIDERS = frozenset({"greenhouse", "lever", "ashby"})

ALLOWED_ATS_API_HOSTS = frozenset(
    {
        "boards-api.greenhouse.io",
        "boards-api.eu.greenhouse.io",
        "api.lever.co",
        "api.eu.lever.co",
        "api.ashbyhq.com",
    }
)

# 45+ unambiguous technology & skill signatures: (canonical_tag, compiled_regex)
TECH_TAG_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS", re.compile(r"(?:\bAWS\b|Amazon Web Services)")),
    ("Airflow", re.compile(r"\b(?:Apache\s+)?Airflow\b", re.IGNORECASE)),
    ("Angular", re.compile(r"\bAngular(?:JS)?\b", re.IGNORECASE)),
    ("Azure", re.compile(r"\b(?:Microsoft\s+)?Azure\b", re.IGNORECASE)),
    ("C#", re.compile(r"(?<![A-Za-z0-9_])C#(?![A-Za-z0-9_])")),
    ("C++", re.compile(r"(?<![A-Za-z0-9_])C\+\+(?![A-Za-z0-9_])")),
    ("CUDA", re.compile(r"\bCUDA\b")),
    ("ClickHouse", re.compile(r"\bClickHouse\b", re.IGNORECASE)),
    ("Django", re.compile(r"\bDjango\b", re.IGNORECASE)),
    ("Docker", re.compile(r"\bDocker\b", re.IGNORECASE)),
    ("Elasticsearch", re.compile(r"\bElastic(?:search|Search)\b")),
    ("FastAPI", re.compile(r"\bFastAPI\b", re.IGNORECASE)),
    ("GCP", re.compile(r"(?:\bGCP\b|Google Cloud(?:\s+Platform)?)")),
    (
        "Go",
        re.compile(
            r"(?:\bGolang\b|(?<![A-Za-z0-9_])Go(?=\s*(?:[,;/)\]]|\band\b|\bor\b|\bdeveloper|\bengineer|\bbackend|\bservices|\bmicroservices|\bprogramming|\blanguage)))"
        ),
    ),
    ("GraphQL", re.compile(r"\bGraphQL\b", re.IGNORECASE)),
    ("Java", re.compile(r"\bJava\b(?!\s*Script)", re.IGNORECASE)),
    ("JavaScript", re.compile(r"\bJavaScript\b|\bECMAScript\b", re.IGNORECASE)),
    ("Kafka", re.compile(r"\b(?:Apache\s+)?Kafka\b", re.IGNORECASE)),
    ("Kotlin", re.compile(r"\bKotlin\b", re.IGNORECASE)),
    ("Kubernetes", re.compile(r"\bKubernetes\b|\bK8s\b", re.IGNORECASE)),
    (
        "LLM/GenAI",
        re.compile(
            r"(?:\bLLMs?\b|\bLangChain\b|\bLangGraph\b|\bHugging\s*Face\b|\bvLLM\b|\bOpenAI\s+API\b|\bAnthropic\b|\bRAG\s+pipeline)",
            re.IGNORECASE,
        ),
    ),
    ("MongoDB", re.compile(r"\bMongoDB\b", re.IGNORECASE)),
    ("MySQL", re.compile(r"\bMySQL\b", re.IGNORECASE)),
    ("Next.js", re.compile(r"\bNext\.js\b|\bNextJS\b", re.IGNORECASE)),
    ("Node.js", re.compile(r"\bNode\.js\b|\bNodeJS\b", re.IGNORECASE)),
    ("PHP", re.compile(r"\bPHP\b")),
    ("PostgreSQL", re.compile(r"\bPostgreSQL\b|\bPostgres\b", re.IGNORECASE)),
    ("PyTorch", re.compile(r"\bPyTorch\b", re.IGNORECASE)),
    ("Python", re.compile(r"\bPython\b", re.IGNORECASE)),
    ("Rails", re.compile(r"\bRuby on Rails\b|\bRails\b")),
    ("React", re.compile(r"\bReact(?:\.js|JS| Native)?\b")),
    ("Redis", re.compile(r"\bRedis\b", re.IGNORECASE)),
    ("Ruby", re.compile(r"\bRuby\b")),
    ("Rust", re.compile(r"\bRust(?:lang)?\b")),
    ("SQL", re.compile(r"\bSQL\b")),
    ("Scala", re.compile(r"\bScala\b")),
    ("Snowflake", re.compile(r"\bSnowflake\b", re.IGNORECASE)),
    ("Solidity", re.compile(r"\bSolidity\b", re.IGNORECASE)),
    ("Spark", re.compile(r"\b(?:Apache\s+Spark|PySpark|Spark)\b")),
    ("Svelte", re.compile(r"\bSvelte(?:Kit)?\b", re.IGNORECASE)),
    ("Swift", re.compile(r"\bSwift(?:UI)?\b")),
    ("Tailwind CSS", re.compile(r"\bTailwind(?:\s*CSS)?\b", re.IGNORECASE)),
    ("TensorFlow", re.compile(r"\bTensorFlow\b", re.IGNORECASE)),
    ("Terraform", re.compile(r"\bTerraform\b", re.IGNORECASE)),
    ("TypeScript", re.compile(r"\bTypeScript\b", re.IGNORECASE)),
    ("Vue", re.compile(r"\bVue(?:\.js|JS)?\b")),
    ("WebAssembly", re.compile(r"\bWebAssembly\b|\bWASM\b")),
    ("dbt", re.compile(r"\bdbt\b")),
    ("gRPC", re.compile(r"\bgRPC\b", re.IGNORECASE)),
)

_INTERN_RE = re.compile(
    r"\b(?:intern|internship|co-?op|apprentice|student\s+worker|summer\s+analyst)\b",
    re.IGNORECASE,
)
_EXEC_MANAGER_RE = re.compile(
    r"\b(?:chief\s+[a-z]+\s+officer|ceo|cto|cfo|coo|ciso|cpo|cmo|cio|president|svp|evp|vp|"
    r"vice\s+president|head\s+of|director|engineering\s+manager|software\s+manager|"
    r"group\s+product\s+manager|senior\s+manager|general\s+manager|regional\s+manager|"
    r"operations\s+manager|sales\s+manager|people\s+manager|design\s+manager|"
    r"data\s+science\s+manager|security\s+manager|managing\s+director|founder|partner)\b",
    re.IGNORECASE,
)
_IC_MANAGER_ROLE_RE = re.compile(
    r"\b(?:product|project|program|account|customer\s+success|community|content|campaign|"
    r"technical\s+program|release|engagement|event|office|brand)\s+manager\b",
    re.IGNORECASE,
)
_GENERIC_MANAGER_RE = re.compile(r"\bmanager\b", re.IGNORECASE)
_STAFF_PRINCIPAL_RE = re.compile(
    r"\b(?:staff|principal|distinguished|fellow|architect|tech\s+lead|technical\s+lead|"
    r"team\s+lead|founding\s+engineer|founding\s+[a-z]+|l6|l7|l8|e6|e7|ic5|ic6)\b",
    re.IGNORECASE,
)
_SENIOR_RE = re.compile(
    r"\b(?:senior|sr\.?|lead|iii|level\s*3|l5|e5|ic4)\b",
    re.IGNORECASE,
)
_JUNIOR_RE = re.compile(
    r"\b(?:junior|jr\.?|entry[- ]level|associate|new\s+grad|graduate|early\s+career|"
    r"assistant|level\s*1|l3|e3|ic1)\b",
    re.IGNORECASE,
)

_CURRENCY_SYMBOL_MAP = {
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "CA$": "CAD",
    "C$": "CAD",
    "CAD": "CAD",
    "AU$": "AUD",
    "A$": "AUD",
    "AUD": "AUD",
    "€": "EUR",
    "EUR": "EUR",
    "£": "GBP",
    "GBP": "GBP",
    "¥": "JPY",
    "JPY": "JPY",
    "CHF": "CHF",
    "SGD": "SGD",
    "S$": "SGD",
    "INR": "INR",
    "₹": "INR",
}

_SALARY_RANGE_RE = re.compile(
    r"(?P<curr1>US\$|CA\$|AU\$|C\$|A\$|S\$|USD|EUR|GBP|CAD|AUD|CHF|SGD|JPY|INR|[\$€£¥₹])\s*"
    r"(?P<min>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?P<min_k>[kK])?\s*"
    r"(?:-|–|—|\bto\b)\s*"
    r"(?P<curr2>US\$|CA\$|AU\$|C\$|A\$|S\$|USD|EUR|GBP|CAD|AUD|CHF|SGD|JPY|INR|[\$€£¥₹])?\s*"
    r"(?P<max>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?P<max_k>[kK])?"
    r"(?:\s*(?P<curr_post>USD|EUR|GBP|CAD|AUD|CHF|SGD|JPY|INR))?"
    r"(?:\s*(?:/|per\s+)?(?P<unit>year|yr|annually|annual|annum|month|mo|monthly|hour|hr|hourly|week|wk|weekly|day|daily))?",
    re.IGNORECASE,
)


def _is_public_ip(addr: str) -> bool:
    """Return True strictly for globally routable public IPv4/IPv6 addresses."""
    ip_obj = ipaddress.ip_address(addr.split("%")[0])
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped is not None:
        ip_obj = ip_obj.ipv4_mapped
    return bool(
        ip_obj.is_global
        and not ip_obj.is_private
        and not ip_obj.is_loopback
        and not ip_obj.is_link_local
        and not ip_obj.is_multicast
        and not ip_obj.is_reserved
        and not ip_obj.is_unspecified
    )


def assert_safe_public_url(
    raw_url: str,
    *,
    preserve_path: bool = True,
    allowed_hosts: frozenset[str] | None = None,
) -> str:
    """Validate public http/https URL and block localhost, private, loopback, or metadata IPs."""
    cleaned = str(raw_url or "").strip()
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Unsupported or invalid URL: {raw_url!r}")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"Credentials in URL are disallowed: {raw_url!r}")

    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if (
        not host
        or host in _FORBIDDEN_HOSTS
        or any(host.endswith(suffix) for suffix in _FORBIDDEN_HOST_SUFFIXES)
    ):
        raise ValueError(f"Forbidden local or internal host: {host!r}")

    is_literal_ip = False
    try:
        ip_obj = ipaddress.ip_address(host)
        is_literal_ip = True
        if not _is_public_ip(str(ip_obj)):
            raise ValueError(f"Forbidden non-public IP: {host}")
    except ValueError as ip_err:
        if "Forbidden" in str(ip_err):
            raise

    if allowed_hosts is not None and host not in allowed_hosts:
        raise ValueError(f"Host {host!r} is not an allowed ATS API host.")

    if not is_literal_ip:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror:
            infos = []
        for info in infos:
            addr = info[4][0]
            if not _is_public_ip(addr):
                raise ValueError(f"Host {host} resolved to non-public IP {addr}")

    if preserve_path:
        path = parsed.path or ""
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{parsed.scheme.lower()}://{parsed.netloc}{path}{query}"
    return f"{parsed.scheme.lower()}://{parsed.netloc}"


def _validate_slug(slug: str) -> str:
    cleaned = str(slug or "").strip().strip("/")
    if not cleaned or ".." in cleaned or not _SLUG_RE.match(cleaned):
        raise ValueError(f"Invalid ATS board slug: {slug!r}")
    return cleaned


def build_ats_api_url(provider: str, slug: str, *, eu_region: bool = False) -> str:
    """Build the official public JSON API URL for Greenhouse, Lever, or Ashby."""
    norm_provider = str(provider or "").strip().lower()
    if norm_provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported ATS provider {provider!r}; expected one of: greenhouse, lever, ashby."
        )
    clean_slug = _validate_slug(slug)

    if norm_provider == "greenhouse":
        host = "boards-api.eu.greenhouse.io" if eu_region else "boards-api.greenhouse.io"
        url = f"https://{host}/v1/boards/{clean_slug}/jobs?content=true"
    elif norm_provider == "lever":
        host = "api.eu.lever.co" if eu_region else "api.lever.co"
        url = f"https://{host}/v0/postings/{clean_slug}?mode=json"
    else:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{clean_slug}?includeCompensation=true"

    return assert_safe_public_url(url, preserve_path=True, allowed_hosts=ALLOWED_ATS_API_HOSTS)


def parse_board_target(entry: Any) -> dict[str, Any]:
    """Resolve dict, full board URL, or provider:slug shorthand into canonical ATS target info."""
    if isinstance(entry, dict):
        raw_url = str(entry.get("url") or "").strip()
        if raw_url and not entry.get("provider"):
            return parse_board_target(raw_url)
        provider = str(entry.get("provider") or entry.get("ats") or "").strip().lower()
        slug = str(
            entry.get("slug") or entry.get("company") or entry.get("board") or ""
        ).strip()
        region = str(entry.get("region") or "").strip().lower()
        eu_region = bool(entry.get("eu_region")) or region == "eu"
        api_url = build_ats_api_url(provider, slug, eu_region=eu_region)
        return {
            "provider": provider,
            "slug": _validate_slug(slug),
            "eu_region": eu_region,
            "api_url": api_url,
            "raw_input": entry,
        }

    if not isinstance(entry, str):
        raise ValueError(f"Unsupported board entry type: {type(entry).__name__}")

    token = entry.strip()
    if not token:
        raise ValueError("Board entry must not be empty.")

    # Shorthand form: "greenhouse:stripe", "lever:spotify", "ashby:linear"
    if "://" not in token and ":" in token:
        prefix, rest = token.split(":", 1)
        provider = prefix.strip().lower()
        if provider in SUPPORTED_PROVIDERS:
            slug = _validate_slug(rest)
            api_url = build_ats_api_url(provider, slug)
            return {
                "provider": provider,
                "slug": slug,
                "eu_region": False,
                "api_url": api_url,
                "raw_input": token,
            }

    # Treat as URL (prepending https:// if user omitted scheme on a known ATS domain)
    candidate_url = token if "://" in token else f"https://{token}"
    safe_url = assert_safe_public_url(candidate_url, preserve_path=True)
    parsed = urlparse(safe_url)
    host = (parsed.hostname or "").lower().rstrip(".")
    segments = [seg for seg in parsed.path.split("/") if seg]

    # Greenhouse public board or API URLs
    if host in (
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
        "boards.eu.greenhouse.io",
        "job-boards.eu.greenhouse.io",
    ):
        if not segments:
            raise ValueError(f"Missing Greenhouse board slug in URL: {token!r}")
        slug = _validate_slug(segments[0])
        eu_region = ".eu." in host
        api_url = build_ats_api_url("greenhouse", slug, eu_region=eu_region)
        return {
            "provider": "greenhouse",
            "slug": slug,
            "eu_region": eu_region,
            "api_url": api_url,
            "raw_input": token,
        }

    if host in ("boards-api.greenhouse.io", "boards-api.eu.greenhouse.io"):
        if len(segments) >= 3 and segments[0] == "v1" and segments[1] == "boards":
            slug = _validate_slug(segments[2])
            eu_region = ".eu." in host
            api_url = build_ats_api_url("greenhouse", slug, eu_region=eu_region)
            return {
                "provider": "greenhouse",
                "slug": slug,
                "eu_region": eu_region,
                "api_url": api_url,
                "raw_input": token,
            }
        raise ValueError(f"Unrecognized Greenhouse API path in URL: {token!r}")

    # Lever public board or API URLs
    if host in ("jobs.lever.co", "jobs.eu.lever.co"):
        if not segments:
            raise ValueError(f"Missing Lever company slug in URL: {token!r}")
        slug = _validate_slug(segments[0])
        eu_region = ".eu." in host
        api_url = build_ats_api_url("lever", slug, eu_region=eu_region)
        return {
            "provider": "lever",
            "slug": slug,
            "eu_region": eu_region,
            "api_url": api_url,
            "raw_input": token,
        }

    if host in ("api.lever.co", "api.eu.lever.co"):
        if len(segments) >= 3 and segments[0] == "v0" and segments[1] == "postings":
            slug = _validate_slug(segments[2])
            eu_region = ".eu." in host
            api_url = build_ats_api_url("lever", slug, eu_region=eu_region)
            return {
                "provider": "lever",
                "slug": slug,
                "eu_region": eu_region,
                "api_url": api_url,
                "raw_input": token,
            }
        raise ValueError(f"Unrecognized Lever API path in URL: {token!r}")

    # Ashby public board or API URLs
    if host == "jobs.ashbyhq.com":
        if not segments:
            raise ValueError(f"Missing Ashby board slug in URL: {token!r}")
        slug = _validate_slug(segments[0])
        api_url = build_ats_api_url("ashby", slug)
        return {
            "provider": "ashby",
            "slug": slug,
            "eu_region": False,
            "api_url": api_url,
            "raw_input": token,
        }

    if host == "api.ashbyhq.com":
        if len(segments) >= 3 and segments[0] == "posting-api" and segments[1] == "job-board":
            slug = _validate_slug(segments[2])
            api_url = build_ats_api_url("ashby", slug)
            return {
                "provider": "ashby",
                "slug": slug,
                "eu_region": False,
                "api_url": api_url,
                "raw_input": token,
            }
        raise ValueError(f"Unrecognized Ashby API path in URL: {token!r}")

    raise ValueError(
        f"Unsupported ATS board URL {token!r}. Expected Greenhouse, Lever, or Ashby board URL."
    )


def _parse_retry_after(header_value: str | None, max_backoff: float) -> float | None:
    if not header_value:
        return None
    text = header_value.strip()
    if not text:
        return None
    try:
        return max(0.0, min(float(text), max_backoff))
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, min(delta, max_backoff))
    except (TypeError, ValueError):
        return None


def safe_http_get(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    allowed_hosts: frozenset[str] | None = ALLOWED_ATS_API_HOSTS,
    max_redirects: int = 3,
    max_retries: int = 3,
    base_backoff: float = 1.0,
    max_backoff: float = 15.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """Fetch an ATS API URL with strict SSRF re-validation on redirects and 429/503 Retry-After backoff."""
    current_url = assert_safe_public_url(url, preserve_path=True, allowed_hosts=allowed_hosts)

    for hop in range(max_redirects + 1):
        resp: httpx.Response | None = None
        for attempt in range(max_retries + 1):
            resp = client.get(current_url, headers=headers, follow_redirects=False)
            if resp.status_code in _RETRY_STATUSES and attempt < max_retries:
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"), max_backoff)
                delay = (
                    retry_after
                    if retry_after is not None
                    else min(max_backoff, base_backoff * (2**attempt))
                )
                if delay > 0:
                    sleep_fn(delay)
                continue
            break

        assert resp is not None
        if resp.status_code in _REDIRECT_STATUSES:
            location = (resp.headers.get("location") or "").strip()
            if not location:
                return resp
            if hop >= max_redirects:
                raise ValueError(f"Exceeded maximum redirects ({max_redirects}) for {url}")
            next_url = urljoin(current_url, location)
            current_url = assert_safe_public_url(
                next_url, preserve_path=True, allowed_hosts=allowed_hosts
            )
            continue

        return resp

    raise ValueError(f"Exceeded maximum redirects ({max_redirects}) for {url}")


class _HTMLTextExtractor(HTMLParser):
    """Lightweight stdlib HTML-to-plain-text stripper preserving readable line breaks."""

    _BREAK_TAGS = frozenset({"br", "hr", "li", "tr"})
    _BLOCK_TAGS = frozenset(
        {"p", "div", "section", "article", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "pre"}
    )
    _SKIP_TAGS = frozenset({"script", "style", "svg", "noscript"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if lower in self._BREAK_TAGS or lower in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if not self._skip_depth and lower in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data:
            self._parts.append(data)

    def get_text(self) -> str:
        joined = "".join(self._parts).replace("\xa0", " ")
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in joined.splitlines()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()


def html_to_clean_text(raw_html: str | None) -> str:
    """Convert raw or HTML-entity-escaped job HTML into clean stripped plain text."""
    text = str(raw_html or "").strip()
    if not text:
        return ""
    if _ESCAPED_HTML_TAG_RE.search(text):
        text = html.unescape(text)
    parser = _HTMLTextExtractor()
    parser.feed(text)
    parser.close()
    return parser.get_text()


def normalize_plain_text(raw_text: str | None) -> str:
    """Clean plain-text job description whitespace without losing paragraph structure."""
    text = str(raw_text or "").replace("\xa0", " ").strip()
    if not text:
        return ""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def classify_workplace_type(
    *,
    explicit_value: str | None = None,
    is_remote_flag: bool | None = None,
    location: str = "",
    title: str = "",
    description_text: str = "",
) -> str:
    """Classify workplace arrangement into remote | hybrid | onsite | unspecified."""
    explicit = str(explicit_value or "").strip().lower().replace("_", "").replace("-", "").replace(" ", "")
    if explicit in ("remote", "fullyremote", "remotefirst"):
        return "remote"
    if explicit == "hybrid":
        return "hybrid"
    if explicit in ("onsite", "inoffice", "office"):
        return "onsite"
    if is_remote_flag is True:
        return "remote"

    loc_title = f"{location} {title}".strip()
    if loc_title:
        if re.search(r"\bhybrid\b", loc_title, re.IGNORECASE):
            return "hybrid"
        if re.search(
            r"\b(?:remote|work\s+from\s+home|wfh|distributed|anywhere)\b",
            loc_title,
            re.IGNORECASE,
        ) and not re.search(r"\b(?:no|not)\s+remote\b", loc_title, re.IGNORECASE):
            return "remote"
        if re.search(r"\b(?:on-?site|in-?office|in\s+person)\b", loc_title, re.IGNORECASE):
            return "onsite"

    if description_text:
        if re.search(
            r"\b(?:hybrid\s+(?:work|role|schedule|model|environment|position)|days?\s+(?:a|per)\s+week\s+in\s+(?:the\s+)?office)\b",
            description_text,
            re.IGNORECASE,
        ):
            return "hybrid"
        if re.search(
            r"\b(?:100%\s+remote|fully\s+remote|remote[- ]first|remote\s+(?:role|position|opportunity|friendly))\b",
            description_text,
            re.IGNORECASE,
        ):
            return "remote"
        if re.search(
            r"\b(?:strictly\s+on-?site|full-?time\s+in-?office|on-?site\s+(?:role|position))\b",
            description_text,
            re.IGNORECASE,
        ):
            return "onsite"

    return "unspecified"


def classify_seniority(title: str) -> str:
    """Classify job title seniority into intern | junior | mid | senior | staff_principal | manager_exec."""
    text = str(title or "").strip()
    if not text:
        return "mid"

    if _INTERN_RE.search(text):
        return "intern"

    if _EXEC_MANAGER_RE.search(text):
        return "manager_exec"

    if _GENERIC_MANAGER_RE.search(text) and not _IC_MANAGER_ROLE_RE.search(text):
        if not _JUNIOR_RE.search(text):
            return "manager_exec"

    if _STAFF_PRINCIPAL_RE.search(text):
        return "staff_principal"

    if _SENIOR_RE.search(text):
        return "senior"

    if _JUNIOR_RE.search(text):
        return "junior"

    return "mid"


def extract_tech_tags(title: str, description_text: str) -> list[str]:
    """Detect normalized technology & engineering stack tags from title and description."""
    combined = f"{title}\n{description_text}"
    if not combined.strip():
        return []
    found: list[str] = []
    for tag, pattern in TECH_TAG_PATTERNS:
        if pattern.search(combined):
            found.append(tag)
    return sorted(found)


def _normalize_salary_interval(raw_interval: str | None) -> str | None:
    token = str(raw_interval or "").strip().lower()
    if not token:
        return None
    if any(k in token for k in ("year", "yr", "annual", "annum")):
        return "yearly"
    if any(k in token for k in ("month", "mo")):
        return "monthly"
    if any(k in token for k in ("hour", "hr")):
        return "hourly"
    if any(k in token for k in ("week", "wk")):
        return "weekly"
    if "day" in token or "daily" in token:
        return "daily"
    return token


def _clean_numeric_amount(val: Any) -> int | float | None:
    if val is None or isinstance(val, bool):
        return None
    try:
        num = float(val)
    except (TypeError, ValueError):
        return None
    if num <= 0:
        return None
    if abs(num - round(num)) < 1e-6:
        return int(round(num))
    return round(num, 2)


def extract_salary_from_text(
    text: str,
) -> tuple[int | float | None, int | float | None, str | None, str | None]:
    """Fallback salary range parser for compensation bands stated in job text or summaries."""
    if not text:
        return (None, None, None, None)

    for match in _SALARY_RANGE_RE.finditer(text):
        curr_raw = (
            match.group("curr_post") or match.group("curr1") or match.group("curr2") or ""
        ).strip()
        currency = _CURRENCY_SYMBOL_MAP.get(curr_raw) or _CURRENCY_SYMBOL_MAP.get(curr_raw.upper())
        if not currency:
            continue

        min_raw = match.group("min").replace(",", "")
        max_raw = match.group("max").replace(",", "")
        try:
            min_val = float(min_raw)
            max_val = float(max_raw)
        except ValueError:
            continue

        min_has_k = bool(match.group("min_k"))
        max_has_k = bool(match.group("max_k"))
        if min_has_k:
            min_val *= 1000.0
        if max_has_k:
            max_val *= 1000.0
        # Handle shorthand like "$150 - $200k" where only the upper bound carries "k"
        if max_has_k and not min_has_k and min_val < 1000 and max_val >= 10000:
            min_val *= 1000.0

        if min_val <= 0 or max_val <= 0 or min_val > max_val:
            continue

        unit = _normalize_salary_interval(match.group("unit"))
        if unit is None:
            if max_val >= 15000:
                unit = "yearly"
            elif 10 <= min_val <= 500 and max_val <= 1000:
                # Require nearby hourly hint to avoid picking up non-salary ranges like "$20 - $50 credit"
                ctx_start = max(0, match.start() - 40)
                ctx_end = min(len(text), match.end() + 40)
                context = text[ctx_start:ctx_end].lower()
                if any(k in context for k in ("hour", "/hr", "hourly", "wage")):
                    unit = "hourly"
                else:
                    continue
            else:
                continue

        if unit == "yearly" and min_val < 10000:
            continue
        if unit == "hourly" and max_val > 2000:
            continue

        return (
            _clean_numeric_amount(min_val),
            _clean_numeric_amount(max_val),
            currency,
            unit,
        )

    return (None, None, None, None)


def _iso_from_epoch_ms(epoch_ms: Any) -> str | None:
    if epoch_ms is None or isinstance(epoch_ms, bool):
        return None
    try:
        val = float(epoch_ms)
    except (TypeError, ValueError):
        return None
    if val <= 0:
        return None
    # Guard against seconds vs milliseconds
    if val > 1e11:
        val = val / 1000.0
    dt = datetime.fromtimestamp(val, tz=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _extract_greenhouse_metadata(metadata: Any) -> tuple[str, str]:
    """Pull optional team and workplace hints from Greenhouse job metadata arrays."""
    team = ""
    workplace_hint = ""
    if not isinstance(metadata, list):
        return team, workplace_hint
    for item in metadata:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower()
        val = item.get("value")
        val_str = ""
        if isinstance(val, str):
            val_str = val.strip()
        elif isinstance(val, list):
            val_str = ", ".join(str(x).strip() for x in val if str(x).strip())
        if not val_str:
            continue
        if not team and any(k in name for k in ("team", "sub-department", "subdepartment", "org")):
            team = val_str
        if not workplace_hint and any(
            k in name for k in ("workplace", "remote", "work type", "location type", "employment location")
        ):
            workplace_hint = val_str
    return team, workplace_hint


def parse_greenhouse_jobs(payload: Any, slug: str) -> list[dict[str, Any]]:
    """Normalize Greenhouse boards-api JSON payload into enriched job records."""
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError(f"Unexpected Greenhouse JSON payload structure for {slug!r}")

    records: list[dict[str, Any]] = []
    for raw in payload["jobs"]:
        if not isinstance(raw, dict):
            continue

        job_id = str(raw.get("id") or raw.get("internal_job_id") or "").strip()
        title = str(raw.get("title") or "").strip()
        company_name = str(raw.get("company_name") or slug).strip()

        departments = raw.get("departments") if isinstance(raw.get("departments"), list) else []
        dept_names = [
            str(d.get("name") or "").strip()
            for d in departments
            if isinstance(d, dict) and str(d.get("name") or "").strip()
        ]
        department = dept_names[0] if dept_names else ""
        meta_team, workplace_hint = _extract_greenhouse_metadata(raw.get("metadata"))
        team = meta_team or (dept_names[1] if len(dept_names) > 1 else "")

        loc_obj = raw.get("location")
        location = ""
        if isinstance(loc_obj, dict):
            location = str(loc_obj.get("name") or "").strip()
        elif isinstance(loc_obj, str):
            location = loc_obj.strip()
        if not location and isinstance(raw.get("offices"), list):
            office_names = [
                str(o.get("name") or o.get("location") or "").strip()
                for o in raw["offices"]
                if isinstance(o, dict) and str(o.get("name") or o.get("location") or "").strip()
            ]
            location = ", ".join(office_names)

        description_text = html_to_clean_text(raw.get("content"))
        workplace_type = classify_workplace_type(
            explicit_value=workplace_hint,
            location=location,
            title=title,
            description_text=description_text,
        )
        seniority = classify_seniority(title)
        salary_min, salary_max, salary_currency, salary_interval = extract_salary_from_text(
            description_text
        )
        tech_tags = extract_tech_tags(title, description_text)

        published_at = (
            str(raw.get("first_published") or raw.get("updated_at") or "").strip() or None
        )
        apply_url = str(raw.get("absolute_url") or "").strip()
        if not apply_url and job_id:
            apply_url = f"https://boards.greenhouse.io/{slug}/jobs/{job_id}"

        records.append(
            {
                "record_type": "job",
                "status": "ok",
                "provider": "greenhouse",
                "company_slug": slug,
                "company_name": company_name,
                "job_id": job_id,
                "title": title,
                "department": department,
                "team": team,
                "location": location,
                "workplace_type": workplace_type,
                "seniority": seniority,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_currency": salary_currency,
                "salary_interval": salary_interval,
                "tech_tags": tech_tags,
                "published_at": published_at,
                "apply_url": apply_url,
                "description_text": description_text,
                "source_api": "greenhouse_boards_api",
            }
        )
    return records


def _build_lever_description(raw: dict[str, Any]) -> str:
    sections: list[str] = []
    opening = normalize_plain_text(raw.get("openingPlain")) or html_to_clean_text(raw.get("opening"))
    main_desc = normalize_plain_text(raw.get("descriptionPlain")) or html_to_clean_text(
        raw.get("description")
    )
    if opening and opening not in main_desc:
        sections.append(opening)
    if main_desc:
        sections.append(main_desc)

    raw_lists = raw.get("lists")
    if isinstance(raw_lists, list):
        for blk in raw_lists:
            if not isinstance(blk, dict):
                continue
            heading = str(blk.get("text") or "").strip()
            body = html_to_clean_text(blk.get("content"))
            if heading and body:
                sections.append(f"{heading}\n{body}")
            elif heading:
                sections.append(heading)
            elif body:
                sections.append(body)

    additional = normalize_plain_text(raw.get("additionalPlain")) or html_to_clean_text(
        raw.get("additional")
    )
    if additional:
        sections.append(additional)
    return "\n\n".join(s for s in sections if s).strip()


def parse_lever_jobs(payload: Any, slug: str) -> list[dict[str, Any]]:
    """Normalize Lever postings JSON array into enriched job records."""
    if not isinstance(payload, list):
        raise ValueError(f"Unexpected Lever JSON payload structure for {slug!r}")

    records: list[dict[str, Any]] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue

        job_id = str(raw.get("id") or "").strip()
        title = str(raw.get("text") or raw.get("title") or "").strip()
        categories = raw.get("categories") if isinstance(raw.get("categories"), dict) else {}
        department = str(categories.get("department") or "").strip()
        team = str(categories.get("team") or "").strip()

        location = str(categories.get("location") or "").strip()
        if not location and isinstance(categories.get("allLocations"), list):
            location = ", ".join(
                str(loc).strip() for loc in categories["allLocations"] if str(loc).strip()
            )

        description_text = _build_lever_description(raw)
        workplace_type = classify_workplace_type(
            explicit_value=raw.get("workplaceType"),
            location=location,
            title=title,
            description_text=description_text,
        )
        seniority = classify_seniority(title)

        salary_min: int | float | None = None
        salary_max: int | float | None = None
        salary_currency: str | None = None
        salary_interval: str | None = None

        sal_obj = raw.get("salaryRange")
        if isinstance(sal_obj, dict):
            salary_min = _clean_numeric_amount(sal_obj.get("min"))
            salary_max = _clean_numeric_amount(sal_obj.get("max"))
            curr = str(sal_obj.get("currency") or "").strip().upper()
            salary_currency = curr or None
            salary_interval = _normalize_salary_interval(sal_obj.get("interval"))

        if salary_min is None and salary_max is None:
            salary_min, salary_max, salary_currency, salary_interval = extract_salary_from_text(
                description_text
            )

        tech_tags = extract_tech_tags(title, description_text)
        published_at = _iso_from_epoch_ms(raw.get("createdAt"))
        apply_url = str(raw.get("applyUrl") or raw.get("hostedUrl") or "").strip()
        if not apply_url and job_id:
            apply_url = f"https://jobs.lever.co/{slug}/{job_id}/apply"

        records.append(
            {
                "record_type": "job",
                "status": "ok",
                "provider": "lever",
                "company_slug": slug,
                "company_name": slug,
                "job_id": job_id,
                "title": title,
                "department": department,
                "team": team,
                "location": location,
                "workplace_type": workplace_type,
                "seniority": seniority,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_currency": salary_currency,
                "salary_interval": salary_interval,
                "tech_tags": tech_tags,
                "published_at": published_at,
                "apply_url": apply_url,
                "description_text": description_text,
                "source_api": "lever_postings_api",
            }
        )
    return records


def _extract_ashby_compensation(
    comp: Any, description_text: str
) -> tuple[int | float | None, int | float | None, str | None, str | None]:
    if isinstance(comp, dict):
        components: list[dict[str, Any]] = []
        raw_summary = comp.get("summaryComponents")
        if isinstance(raw_summary, list):
            components.extend(c for c in raw_summary if isinstance(c, dict))
        raw_tiers = comp.get("compensationTiers")
        if isinstance(raw_tiers, list):
            for tier in raw_tiers:
                if isinstance(tier, dict) and isinstance(tier.get("components"), list):
                    components.extend(c for c in tier["components"] if isinstance(c, dict))

        # Prioritize explicit Salary components first
        prioritized = sorted(
            components,
            key=lambda c: 0 if "salary" in str(c.get("compensationType") or "").lower() else 1,
        )
        for comp_item in prioritized:
            c_min = _clean_numeric_amount(comp_item.get("minValue"))
            c_max = _clean_numeric_amount(comp_item.get("maxValue"))
            if c_min is not None or c_max is not None:
                curr = str(comp_item.get("currencyCode") or "").strip().upper() or None
                interval = _normalize_salary_interval(comp_item.get("interval")) or "yearly"
                return (c_min, c_max, curr, interval)

        for summary_key in ("scrapeableCompensationSalarySummary", "compensationTierSummary"):
            summary_val = str(comp.get(summary_key) or "").strip()
            if summary_val:
                parsed = extract_salary_from_text(summary_val)
                if parsed[0] is not None or parsed[1] is not None:
                    return parsed

    return extract_salary_from_text(description_text)


def parse_ashby_jobs(payload: Any, slug: str) -> list[dict[str, Any]]:
    """Normalize Ashby public job-board JSON payload into enriched job records."""
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError(f"Unexpected Ashby JSON payload structure for {slug!r}")

    records: list[dict[str, Any]] = []
    for raw in payload["jobs"]:
        if not isinstance(raw, dict):
            continue
        if raw.get("isListed") is False:
            continue

        job_id = str(raw.get("id") or "").strip()
        title = str(raw.get("title") or "").strip()
        department = str(raw.get("department") or "").strip()
        team = str(raw.get("team") or "").strip()

        loc_parts: list[str] = []
        primary_loc = str(raw.get("location") or "").strip()
        if primary_loc:
            loc_parts.append(primary_loc)
        secondary = raw.get("secondaryLocations")
        if isinstance(secondary, list):
            for item in secondary:
                if isinstance(item, dict):
                    sec_loc = str(item.get("location") or "").strip()
                else:
                    sec_loc = str(item or "").strip()
                if sec_loc and sec_loc not in loc_parts:
                    loc_parts.append(sec_loc)
        location = ", ".join(loc_parts)

        description_text = normalize_plain_text(raw.get("descriptionPlain")) or html_to_clean_text(
            raw.get("descriptionHtml")
        )
        is_remote_flag = raw.get("isRemote") if isinstance(raw.get("isRemote"), bool) else None
        workplace_type = classify_workplace_type(
            explicit_value=raw.get("workplaceType"),
            is_remote_flag=is_remote_flag,
            location=location,
            title=title,
            description_text=description_text,
        )
        seniority = classify_seniority(title)
        salary_min, salary_max, salary_currency, salary_interval = _extract_ashby_compensation(
            raw.get("compensation"), description_text
        )
        tech_tags = extract_tech_tags(title, description_text)
        published_at = str(raw.get("publishedAt") or "").strip() or None
        apply_url = str(raw.get("applyUrl") or raw.get("jobUrl") or "").strip()
        if not apply_url and job_id:
            apply_url = f"https://jobs.ashbyhq.com/{slug}/{job_id}/application"

        records.append(
            {
                "record_type": "job",
                "status": "ok",
                "provider": "ashby",
                "company_slug": slug,
                "company_name": slug,
                "job_id": job_id,
                "title": title,
                "department": department,
                "team": team,
                "location": location,
                "workplace_type": workplace_type,
                "seniority": seniority,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_currency": salary_currency,
                "salary_interval": salary_interval,
                "tech_tags": tech_tags,
                "published_at": published_at,
                "apply_url": apply_url,
                "description_text": description_text,
                "source_api": "ashby_job_board_api",
            }
        )
    return records


def _matches_filters(
    record: dict[str, Any],
    *,
    remote_only: bool,
    keyword_needle: str,
    department_needle: str,
) -> bool:
    if remote_only and record.get("workplace_type") != "remote":
        return False

    if department_needle:
        dept_haystack = " ".join(
            [str(record.get("department") or ""), str(record.get("team") or "")]
        ).lower()
        if department_needle not in dept_haystack:
            return False

    if keyword_needle:
        tags_str = " ".join(record.get("tech_tags") or [])
        haystack = " ".join(
            [
                str(record.get("title") or ""),
                str(record.get("department") or ""),
                str(record.get("team") or ""),
                str(record.get("location") or ""),
                tags_str,
                str(record.get("description_text") or ""),
            ]
        ).lower()
        if keyword_needle not in haystack:
            return False

    return True


def extract_board_jobs(
    board_entry: Any,
    *,
    remote_only: bool = False,
    keyword_filter: str | None = None,
    department_filter: str | None = None,
    max_jobs: int = 100,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Fetch, enrich, and filter public job postings from a single Greenhouse, Lever, or Ashby board."""
    target = parse_board_target(board_entry)
    provider = target["provider"]
    slug = target["slug"]
    api_url = target["api_url"]

    target_limit = max(1, min(int(max_jobs), 5000))
    keyword_needle = str(keyword_filter or "").strip().lower()
    department_needle = str(department_filter or "").strip().lower()

    own_client = client is None
    active = (
        client
        if client is not None
        else httpx.Client(
            timeout=25.0,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=False,
        )
    )
    try:
        resp = safe_http_get(
            active,
            api_url,
            headers={"Accept": "application/json"},
            allowed_hosts=ALLOWED_ATS_API_HOSTS,
            sleep_fn=sleep_fn,
        )
        resp.raise_for_status()
        payload = resp.json()
    finally:
        if own_client:
            active.close()

    if provider == "greenhouse":
        raw_records = parse_greenhouse_jobs(payload, slug)
    elif provider == "lever":
        raw_records = parse_lever_jobs(payload, slug)
    else:
        raw_records = parse_ashby_jobs(payload, slug)

    filtered: list[dict[str, Any]] = []
    for rec in raw_records:
        if len(filtered) >= target_limit:
            break
        if _matches_filters(
            rec,
            remote_only=remote_only,
            keyword_needle=keyword_needle,
            department_needle=department_needle,
        ):
            filtered.append(rec)

    return filtered


def extract_ats_boards(
    boards: list[Any],
    *,
    remote_only: bool = False,
    keyword_filter: str | None = None,
    department_filter: str | None = None,
    max_jobs_per_board: int = 100,
    request_delay_sec: float = 0.25,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Batch-extract jobs across multiple ATS boards with strict per-board fault isolation."""
    if not boards:
        return []

    own_client = client is None
    active = (
        client
        if client is not None
        else httpx.Client(
            timeout=25.0,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=False,
        )
    )
    results: list[dict[str, Any]] = []
    seen_targets: set[tuple[str, str, bool]] = set()

    try:
        for idx, entry in enumerate(boards):
            if idx > 0 and request_delay_sec > 0:
                sleep_fn(request_delay_sec)

            provider_hint: str | None = None
            slug_hint: str | None = None
            try:
                target = parse_board_target(entry)
                provider_hint = target["provider"]
                slug_hint = target["slug"]
                dedup_key = (target["provider"], target["slug"], bool(target["eu_region"]))
                if dedup_key in seen_targets:
                    continue
                seen_targets.add(dedup_key)

                jobs = extract_board_jobs(
                    target,
                    remote_only=remote_only,
                    keyword_filter=keyword_filter,
                    department_filter=department_filter,
                    max_jobs=max_jobs_per_board,
                    client=active,
                    sleep_fn=sleep_fn,
                )
                results.extend(jobs)
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                results.append(
                    {
                        "record_type": "error",
                        "status": "error",
                        "provider": provider_hint,
                        "company_slug": slug_hint,
                        "board_input": entry,
                        "http_status": status_code,
                        "error_message": f"HTTP {status_code}: {exc}",
                    }
                )
            except (ValueError, httpx.RequestError, json.JSONDecodeError) as exc:
                results.append(
                    {
                        "record_type": "error",
                        "status": "error",
                        "provider": provider_hint,
                        "company_slug": slug_hint,
                        "board_input": entry,
                        "http_status": None,
                        "error_message": str(exc),
                    }
                )
    finally:
        if own_client:
            active.close()

    return results


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run this Actor.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        raw_boards = actor_input.get("boards") or []
        if not isinstance(raw_boards, list) or not raw_boards:
            raise ValueError("Provide at least one ATS board entry in 'boards'.")

        remote_only = bool(actor_input.get("remoteOnly", False))
        keyword_filter = str(actor_input.get("keywordFilter") or "").strip() or None
        department_filter = str(actor_input.get("departmentFilter") or "").strip() or None
        max_jobs = max(1, min(int(actor_input.get("maxJobsPerBoard") or 100), 5000))
        request_delay_ms = max(0, min(int(actor_input.get("requestDelayMs") or 250), 5000))

        records = await asyncio.to_thread(
            extract_ats_boards,
            raw_boards,
            remote_only=remote_only,
            keyword_filter=keyword_filter,
            department_filter=department_filter,
            max_jobs_per_board=max_jobs,
            request_delay_sec=request_delay_ms / 1000.0,
        )

        for rec in records:
            await Actor.push_data(rec)
            if rec.get("status") == "ok" and rec.get("record_type") == "job":
                await Actor.charge(event_name="job_extracted", count=1)


if __name__ == "__main__":
    asyncio.run(main())
