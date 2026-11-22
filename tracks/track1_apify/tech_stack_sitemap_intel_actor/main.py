"""Apify Pay-Per-Event Actor: Website Tech Stack, Recursive Sitemap & SEO Intelligence Extractor."""

from __future__ import annotations

import asyncio
import email.utils
import gzip
import io
import ipaddress
import json
import re
import socket
import time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable, Mapping
from urllib.parse import unquote, urljoin, urlparse

import httpx

try:
    from apify import Actor
except ImportError:  # Allow offline unit testing without Apify SDK installed.
    Actor = None  # type: ignore[assignment]

USER_AGENT = "HorizonTechStackSitemapIntel/1.0 (+https://github.com/pecopeko/apify-ppe-actors)"
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
_CDATA_RE = re.compile(r"<!\[CDATA\[.*?\]\]>", re.DOTALL)
_UNSAFE_DTD_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}$")
_IGNORED_EMAIL_DOMAINS = frozenset(
    {"example.com", "example.org", "example.net", "yourdomain.com", "domain.com", "sentry.io"}
)

MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_SITEMAP_DECOMPRESSED_BYTES = 15 * 1024 * 1024
DEFAULT_MAX_CHILD_SITEMAPS = 5

TECH_CATEGORIES: tuple[str, ...] = (
    "framework",
    "cms_ecommerce",
    "analytics",
    "payments",
    "cdn_hosting",
    "support_crm",
    "auth_infra",
)


@dataclass(frozen=True)
class TechSignature:
    """Declarative fingerprint rule for a web technology across HTTP headers and HTML."""

    name: str
    category: str
    header_rules: tuple[tuple[str, re.Pattern[str] | None], ...] = ()
    html_patterns: tuple[re.Pattern[str], ...] = ()


def _rx(pattern: str, flags: int = re.IGNORECASE) -> re.Pattern[str]:
    return re.compile(pattern, flags)


# 75+ curated technology signatures grouped across 7 commercial categories.
TECH_SIGNATURES: tuple[TechSignature, ...] = (
    # --- framework (14) ---
    TechSignature(
        "Next.js",
        "framework",
        header_rules=(
            ("x-powered-by", _rx(r"\bnext\.js\b")),
            ("x-nextjs-cache", None),
            ("x-nextjs-matched-path", None),
            ("x-nextjs-prerender", None),
        ),
        html_patterns=(
            _rx(r"/_next/static/"),
            _rx(r"id=[\"']__NEXT_DATA__[\"']"),
            _rx(r"__next_f\.push\("),
        ),
    ),
    TechSignature(
        "Nuxt",
        "framework",
        header_rules=(("x-nuxt-cache", None),),
        html_patterns=(
            _rx(r"/_nuxt/"),
            _rx(r"window\.__NUXT__"),
            _rx(r"id=[\"']__nuxt[\"']"),
        ),
    ),
    TechSignature(
        "Astro",
        "framework",
        html_patterns=(
            _rx(r"<astro-island\b"),
            _rx(r"\bdata-astro-cid-"),
            _rx(r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']Astro\b"),
        ),
    ),
    TechSignature(
        "Remix",
        "framework",
        html_patterns=(
            _rx(r"window\.__remixContext\b"),
            _rx(r"window\.__remixManifest\b"),
            _rx(r"__remixRouteModules"),
        ),
    ),
    TechSignature(
        "Gatsby",
        "framework",
        html_patterns=(
            _rx(r"id=[\"']___gatsby[\"']"),
            _rx(r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']Gatsby\b"),
        ),
    ),
    TechSignature(
        "React",
        "framework",
        html_patterns=(
            _rx(r"\bdata-reactroot\b"),
            _rx(r"\bdata-reactid\b"),
            _rx(r"react-dom(?:\.production)?(?:\.min)?\.js"),
            _rx(r"react\.production\.min\.js"),
            _rx(r"/_next/static/"),
            _rx(r"id=[\"']__NEXT_DATA__[\"']"),
        ),
    ),
    TechSignature(
        "Vue",
        "framework",
        html_patterns=(
            _rx(r"\bdata-v-[0-9a-f]{6,}\b"),
            _rx(r"vue(?:\.runtime|\.global)?(?:\.prod)?(?:\.min)?\.js"),
            _rx(r"window\.__VUE__"),
            _rx(r"/_nuxt/"),
        ),
    ),
    TechSignature(
        "Svelte",
        "framework",
        html_patterns=(
            _rx(r"__sveltekit"),
            _rx(r"\bdata-sveltekit-"),
            _rx(r"class=[\"'][^\"']*\bsvelte-[a-z0-9]{5,}\b"),
        ),
    ),
    TechSignature(
        "Angular",
        "framework",
        html_patterns=(
            _rx(r"\bng-version=[\"'][0-9]"),
            _rx(r"\b_ngcontent-"),
            _rx(r"angular(?:\.min)?\.js"),
        ),
    ),
    TechSignature(
        "SolidJS",
        "framework",
        html_patterns=(
            _rx(r"_\$HY\b"),
            _rx(r"solid-js"),
        ),
    ),
    TechSignature(
        "Qwik",
        "framework",
        html_patterns=(
            _rx(r"\bq:container="),
            _rx(r"\bq:version="),
            _rx(r"qwikloader"),
        ),
    ),
    TechSignature(
        "Tailwind CSS",
        "framework",
        html_patterns=(
            _rx(r"cdn\.tailwindcss\.com"),
            _rx(r"tailwindcss(?:\.min)?\.css"),
            _rx(r"--tw-(?:bg-opacity|ring-offset|translate-x|gradient-from)"),
        ),
    ),
    TechSignature(
        "Bootstrap",
        "framework",
        html_patterns=(
            _rx(r"bootstrap(?:\.bundle)?(?:\.min)?\.(?:css|js)"),
            _rx(r"cdn\.jsdelivr\.net/npm/bootstrap"),
        ),
    ),
    TechSignature(
        "jQuery",
        "framework",
        html_patterns=(
            _rx(r"jquery(?:-[0-9.]+)?(?:\.slim)?(?:\.min)?\.js"),
            _rx(r"code\.jquery\.com/jquery"),
        ),
    ),
    # --- cms_ecommerce (12) ---
    TechSignature(
        "Shopify",
        "cms_ecommerce",
        header_rules=(
            ("x-shopify-stage", None),
            ("x-shopid", None),
            ("x-sorting-hat-shopid", None),
            ("powered-by", _rx(r"\bshopify\b")),
        ),
        html_patterns=(
            _rx(r"cdn\.shopify\.com"),
            _rx(r"Shopify\.theme\b"),
            _rx(r"shopify-section"),
        ),
    ),
    TechSignature(
        "WordPress",
        "cms_ecommerce",
        header_rules=(
            ("x-pingback", _rx(r"xmlrpc\.php")),
            ("link", _rx(r"api\.w\.org|wp-json")),
        ),
        html_patterns=(
            _rx(r"/wp-content/(?:themes|plugins)/"),
            _rx(r"/wp-includes/js/"),
            _rx(r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']WordPress"),
        ),
    ),
    TechSignature(
        "WooCommerce",
        "cms_ecommerce",
        html_patterns=(
            _rx(r"/plugins/woocommerce/"),
            _rx(r"\bwc-ajax\b"),
            _rx(r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']WooCommerce"),
        ),
    ),
    TechSignature(
        "Webflow",
        "cms_ecommerce",
        html_patterns=(
            _rx(r"\bdata-wf-site="),
            _rx(r"\bdata-wf-page="),
            _rx(r"(?:assets|cdn\.prod)\.website-files\.com"),
            _rx(r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']Webflow"),
        ),
    ),
    TechSignature(
        "Wix",
        "cms_ecommerce",
        header_rules=(
            ("x-wix-request-id", None),
            ("x-wix-renderer-server", None),
        ),
        html_patterns=(
            _rx(r"static\.wixstatic\.com"),
            _rx(r"wix-thunderbolt"),
            _rx(r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']Wix"),
        ),
    ),
    TechSignature(
        "Squarespace",
        "cms_ecommerce",
        header_rules=(
            ("server", _rx(r"\bsquarespace\b")),
            ("x-servedby", _rx(r"\bsquarespace\b")),
        ),
        html_patterns=(
            _rx(r"static1?\.squarespace\.com"),
            _rx(r"This is Squarespace"),
        ),
    ),
    TechSignature(
        "Ghost",
        "cms_ecommerce",
        header_rules=(
            ("x-ghost-cache-status", None),
            ("x-powered-by", _rx(r"\bghost\b")),
        ),
        html_patterns=(
            _rx(r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']Ghost"),
            _rx(r"ghost-portal|@tryghost/portal"),
        ),
    ),
    TechSignature(
        "Contentful",
        "cms_ecommerce",
        html_patterns=(
            _rx(r"(?:images|downloads)\.ctfassets\.net"),
            _rx(r"cdn\.contentful\.com"),
        ),
    ),
    TechSignature(
        "Sanity",
        "cms_ecommerce",
        html_patterns=(_rx(r"cdn\.sanity\.io"),),
    ),
    TechSignature(
        "Framer",
        "cms_ecommerce",
        html_patterns=(
            _rx(r"framerusercontent\.com"),
            _rx(r"events\.framer\.com"),
            _rx(r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']Framer"),
        ),
    ),
    TechSignature(
        "BigCommerce",
        "cms_ecommerce",
        header_rules=(("x-bc-storefront-type", None),),
        html_patterns=(_rx(r"cdn11\.bigcommerce\.com"),),
    ),
    TechSignature(
        "Magento",
        "cms_ecommerce",
        header_rules=(
            ("x-magento-cache-debug", None),
            ("x-magento-tags", None),
        ),
        html_patterns=(
            _rx(r"text/x-magento-init"),
            _rx(r"Mage\.Cookies"),
        ),
    ),
    # --- analytics (14) ---
    TechSignature(
        "Google Analytics 4",
        "analytics",
        html_patterns=(
            _rx(r"googletagmanager\.com/gtag/js\?id=G-"),
            _rx(r"google-analytics\.com/g/collect"),
            _rx(r"gtag\(\s*[\"']config[\"']\s*,\s*[\"']G-[A-Z0-9]{6,}[\"']"),
        ),
    ),
    TechSignature(
        "Google Tag Manager",
        "analytics",
        html_patterns=(
            _rx(r"googletagmanager\.com/gtm\.js"),
            _rx(r"\bGTM-[A-Z0-9]{4,}\b", flags=0),
        ),
    ),
    TechSignature(
        "Meta Pixel",
        "analytics",
        html_patterns=(
            _rx(r"connect\.facebook\.net/[^\"']*/fbevents\.js"),
            _rx(r"\bfbq\(\s*[\"']init[\"']"),
        ),
    ),
    TechSignature(
        "Segment",
        "analytics",
        html_patterns=(
            _rx(r"cdn\.segment\.com/analytics\.js"),
            _rx(r"api\.segment\.io"),
            _rx(r"analytics\.load\(\s*[\"'][A-Za-z0-9]{16,}[\"']"),
        ),
    ),
    TechSignature(
        "PostHog",
        "analytics",
        html_patterns=(
            _rx(r"(?:us|eu|app)\.i?\.?posthog\.com"),
            _rx(r"posthog\.init\("),
            _rx(r"us-assets\.i\.posthog\.com"),
        ),
    ),
    TechSignature(
        "Mixpanel",
        "analytics",
        html_patterns=(
            _rx(r"cdn\.mxpnl\.com"),
            _rx(r"api-js\.mixpanel\.com"),
            _rx(r"mixpanel\.init\("),
        ),
    ),
    TechSignature(
        "Amplitude",
        "analytics",
        html_patterns=(
            _rx(r"cdn\.amplitude\.com"),
            _rx(r"api2?\.amplitude\.com"),
            _rx(r"amplitude\.getInstance\("),
        ),
    ),
    TechSignature(
        "Sentry",
        "analytics",
        header_rules=(("sentry-trace", None),),
        html_patterns=(
            _rx(r"browser\.sentry-cdn\.com"),
            _rx(r"ingest(?:\.[a-z0-9-]+)?\.sentry\.io"),
            _rx(r"\bSentry\.init\("),
        ),
    ),
    TechSignature(
        "Datadog",
        "analytics",
        html_patterns=(
            _rx(r"datadoghq-browser-agent\.com"),
            _rx(r"browser-intake-datadoghq\.com"),
            _rx(r"\bDD_RUM\b"),
        ),
    ),
    TechSignature(
        "Hotjar",
        "analytics",
        html_patterns=(
            _rx(r"static\.hotjar\.com"),
            _rx(r"_hjSettings\s*="),
        ),
    ),
    TechSignature(
        "Microsoft Clarity",
        "analytics",
        html_patterns=(
            _rx(r"(?:www\.)?clarity\.ms/tag/"),
            _rx(r"c\.clarity\.ms"),
        ),
    ),
    TechSignature(
        "Plausible",
        "analytics",
        html_patterns=(_rx(r"plausible\.io/js/(?:script|plausible)"),),
    ),
    TechSignature(
        "Fathom Analytics",
        "analytics",
        html_patterns=(_rx(r"cdn\.usefathom\.com"),),
    ),
    TechSignature(
        "FullStory",
        "analytics",
        html_patterns=(
            _rx(r"edge\.fullstory\.com"),
            _rx(r"fullstory\.com/s/fs\.js"),
        ),
    ),
    # --- payments (8) ---
    TechSignature(
        "Stripe",
        "payments",
        html_patterns=(
            _rx(r"js\.stripe\.com"),
            _rx(r"checkout\.stripe\.com"),
            _rx(r"m\.stripe\.network"),
            _rx(r"b\.stripecdn\.com"),
        ),
    ),
    TechSignature(
        "PayPal",
        "payments",
        html_patterns=(
            _rx(r"paypal\.com/sdk/js"),
            _rx(r"paypalobjects\.com"),
            _rx(r"js\.braintreegateway\.com"),
        ),
    ),
    TechSignature(
        "Paddle",
        "payments",
        html_patterns=(
            _rx(r"cdn\.paddle\.com/paddle"),
            _rx(r"\bPaddle\.Setup\("),
        ),
    ),
    TechSignature(
        "Adyen",
        "payments",
        html_patterns=(
            _rx(r"checkoutshopper-(?:live|test)\.adyen\.com"),
            _rx(r"adyen\.com/checkoutshopper"),
        ),
    ),
    TechSignature(
        "Klarna",
        "payments",
        html_patterns=(
            _rx(r"x\.klarnacdn\.net"),
            _rx(r"js\.klarna\.com"),
        ),
    ),
    TechSignature(
        "Shop Pay",
        "payments",
        html_patterns=(
            _rx(r"shopify\.com/shopifycloud/payment-sheet"),
            _rx(r"\bshop-pay-wallet\b"),
        ),
    ),
    TechSignature(
        "Chargebee",
        "payments",
        html_patterns=(_rx(r"js\.chargebee\.com"),),
    ),
    TechSignature(
        "Lemon Squeezy",
        "payments",
        html_patterns=(
            _rx(r"assets\.lemonsqueezy\.com"),
            _rx(r"app\.lemonsqueezy\.com/js/lemon\.js"),
        ),
    ),
    # --- cdn_hosting (12) ---
    TechSignature(
        "Cloudflare",
        "cdn_hosting",
        header_rules=(
            ("cf-ray", None),
            ("cf-cache-status", None),
            ("server", _rx(r"\bcloudflare\b")),
        ),
        html_patterns=(
            _rx(r"static\.cloudflareinsights\.com"),
            _rx(r"cdn-cgi/(?:scripts|challenge-platform|image)"),
        ),
    ),
    TechSignature(
        "Vercel",
        "cdn_hosting",
        header_rules=(
            ("x-vercel-id", None),
            ("x-vercel-cache", None),
            ("server", _rx(r"\bvercel\b")),
        ),
        html_patterns=(
            _rx(r"/_vercel/insights/"),
            _rx(r"va\.vercel-scripts\.com"),
        ),
    ),
    TechSignature(
        "Netlify",
        "cdn_hosting",
        header_rules=(
            ("x-nf-request-id", None),
            ("server", _rx(r"\bnetlify\b")),
        ),
    ),
    TechSignature(
        "AWS CloudFront",
        "cdn_hosting",
        header_rules=(
            ("x-amz-cf-id", None),
            ("x-amz-cf-pop", None),
            ("via", _rx(r"\bcloudfront\b")),
        ),
    ),
    TechSignature(
        "Fastly",
        "cdn_hosting",
        header_rules=(
            ("x-fastly-request-id", None),
            ("fastly-restarts", None),
            ("x-served-by", _rx(r"\bcache-[a-z0-9-]+\b")),
        ),
    ),
    TechSignature(
        "Akamai",
        "cdn_hosting",
        header_rules=(
            ("akamai-grn", None),
            ("x-akamai-transformed", None),
            ("server", _rx(r"\bakamaighost\b")),
        ),
    ),
    TechSignature(
        "Render",
        "cdn_hosting",
        header_rules=(("x-render-origin-server", None),),
    ),
    TechSignature(
        "Fly.io",
        "cdn_hosting",
        header_rules=(
            ("fly-request-id", None),
            ("server", _rx(r"^fly/")),
        ),
    ),
    TechSignature(
        "GitHub Pages",
        "cdn_hosting",
        header_rules=(
            ("server", _rx(r"\bgithub\.com\b")),
            ("x-github-request-id", None),
        ),
    ),
    TechSignature(
        "Google Cloud CDN",
        "cdn_hosting",
        header_rules=(
            ("server", _rx(r"^(?:gws|gfe|sffe|google frontend)\b")),
            ("via", _rx(r"\b1\.1 google\b")),
        ),
    ),
    TechSignature(
        "Nginx",
        "cdn_hosting",
        header_rules=(("server", _rx(r"\bnginx\b")),),
    ),
    TechSignature(
        "Apache",
        "cdn_hosting",
        header_rules=(("server", _rx(r"\bapache\b")),),
    ),
    # --- support_crm (9) ---
    TechSignature(
        "Intercom",
        "support_crm",
        html_patterns=(
            _rx(r"widget\.intercom\.io"),
            _rx(r"js\.intercomcdn\.com"),
            _rx(r"window\.intercomSettings"),
        ),
    ),
    TechSignature(
        "Zendesk",
        "support_crm",
        html_patterns=(
            _rx(r"static\.zdassets\.com"),
            _rx(r"ekr\.zdassets\.com"),
            _rx(r"zE\(\s*[\"']webWidget[\"']"),
        ),
    ),
    TechSignature(
        "HubSpot",
        "support_crm",
        header_rules=(("set-cookie", _rx(r"\bhubspotutk=")),),
        html_patterns=(
            _rx(r"js\.hs-scripts\.com"),
            _rx(r"js\.hsforms\.net"),
            _rx(r"js\.hs-analytics\.net"),
            _rx(r"id=[\"']hs-script-loader[\"']"),
        ),
    ),
    TechSignature(
        "Crisp",
        "support_crm",
        html_patterns=(
            _rx(r"client\.crisp\.chat"),
            _rx(r"window\.\$crisp\b"),
        ),
    ),
    TechSignature(
        "Drift",
        "support_crm",
        html_patterns=(
            _rx(r"js\.driftt\.com"),
            _rx(r"drift\.load\("),
        ),
    ),
    TechSignature(
        "Freshworks",
        "support_crm",
        html_patterns=(
            _rx(r"wchat\.freshchat\.com"),
            _rx(r"widget\.freshworks\.com"),
        ),
    ),
    TechSignature(
        "Help Scout",
        "support_crm",
        html_patterns=(_rx(r"beacon-v2\.helpscout\.net"),),
    ),
    TechSignature(
        "Marketo",
        "support_crm",
        html_patterns=(
            _rx(r"munchkin\.marketo\.net"),
            _rx(r"\bMktoForms2\b"),
        ),
    ),
    TechSignature(
        "Klaviyo",
        "support_crm",
        html_patterns=(
            _rx(r"static\.klaviyo\.com"),
            _rx(r"a\.klaviyo\.com"),
        ),
    ),
    # --- auth_infra (10) ---
    TechSignature(
        "reCAPTCHA",
        "auth_infra",
        html_patterns=(
            _rx(r"(?:www\.)?(?:google|recaptcha)\.com/recaptcha"),
            _rx(r"class=[\"'][^\"']*\bg-recaptcha\b"),
        ),
    ),
    TechSignature(
        "hCaptcha",
        "auth_infra",
        html_patterns=(
            _rx(r"js\.hcaptcha\.com"),
            _rx(r"hcaptcha\.com/1/api\.js"),
            _rx(r"class=[\"'][^\"']*\bh-captcha\b"),
        ),
    ),
    TechSignature(
        "Cloudflare Turnstile",
        "auth_infra",
        html_patterns=(
            _rx(r"challenges\.cloudflare\.com/turnstile"),
            _rx(r"class=[\"'][^\"']*\bcf-turnstile\b"),
        ),
    ),
    TechSignature(
        "Clerk",
        "auth_infra",
        html_patterns=(
            _rx(r"clerk\.accounts\.dev"),
            _rx(r"clerk\.browser\.js"),
            _rx(r"data-clerk-publishable-key"),
        ),
    ),
    TechSignature(
        "Auth0",
        "auth_infra",
        html_patterns=(
            _rx(r"cdn\.auth0\.com"),
            _rx(r"auth0\.com/js/"),
            _rx(r"auth0-spa-js"),
        ),
    ),
    TechSignature(
        "Supabase",
        "auth_infra",
        html_patterns=(
            _rx(r"\.supabase\.co\b"),
            _rx(r"@supabase/supabase-js"),
        ),
    ),
    TechSignature(
        "Firebase",
        "auth_infra",
        html_patterns=(
            _rx(r"www\.gstatic\.com/firebasejs/"),
            _rx(r"\.firebaseapp\.com"),
            _rx(r"firebase\.initializeApp\("),
        ),
    ),
    TechSignature(
        "Algolia",
        "auth_infra",
        html_patterns=(
            _rx(r"algoliasearch"),
            _rx(r"\.algolia\.net\b"),
            _rx(r"cdn\.jsdelivr\.net/npm/@?docsearch"),
        ),
    ),
    TechSignature(
        "LaunchDarkly",
        "auth_infra",
        html_patterns=(
            _rx(r"(?:app|clientstream)\.launchdarkly\.com"),
            _rx(r"ldclient\.min\.js"),
        ),
    ),
    TechSignature(
        "OneTrust",
        "auth_infra",
        html_patterns=(
            _rx(r"cdn\.cookielaw\.org"),
            _rx(r"optanon\.blob\.core\.windows\.net"),
            _rx(r"function\s+OptanonWrapper"),
        ),
    ),
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


def assert_safe_public_url(raw_url: str, *, preserve_path: bool = True) -> str:
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


def normalize_target_url(raw_input: str) -> str:
    """Normalize a bare domain or URL into a validated public http(s) URL."""
    token = str(raw_input or "").strip()
    if not token:
        raise ValueError("Website URL or domain must not be empty.")
    candidate = token if "://" in token else f"https://{token}"
    return assert_safe_public_url(candidate, preserve_path=True)


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
    max_redirects: int = 3,
    max_retries: int = 3,
    base_backoff: float = 1.0,
    max_backoff: float = 15.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[httpx.Response, str]:
    """Fetch URL with SSRF re-validation on every redirect hop (up to 3) and 429/503 Retry-After backoff."""
    current_url = assert_safe_public_url(url, preserve_path=True)

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
                return resp, current_url
            if hop >= max_redirects:
                raise ValueError(f"Exceeded maximum redirects ({max_redirects}) for {url}")
            next_url = urljoin(current_url, location)
            current_url = assert_safe_public_url(next_url, preserve_path=True)
            continue

        return resp, current_url

    raise ValueError(f"Exceeded maximum redirects ({max_redirects}) for {url}")


def _normalize_headers_map(headers: httpx.Headers | Mapping[str, str] | None) -> dict[str, str]:
    """Collapse HTTP headers (including multi-valued Set-Cookie/Link) into lowercase keys."""
    if headers is None:
        return {}
    grouped: dict[str, list[str]] = {}
    if isinstance(headers, httpx.Headers):
        for key, val in headers.multi_items():
            grouped.setdefault(key.lower(), []).append(val)
    else:
        for key, val in headers.items():
            grouped.setdefault(str(key).lower(), []).append(str(val))
    return {k: "\n".join(v) for k, v in grouped.items()}


def detect_tech_stack(
    headers: httpx.Headers | Mapping[str, str] | None,
    html_text: str,
) -> dict[str, Any]:
    """Detect 75+ web technologies from HTTP response headers and HTML markup."""
    header_map = _normalize_headers_map(headers)
    sample_html = (html_text or "")[:MAX_HTML_BYTES]

    by_category: dict[str, list[str]] = {cat: [] for cat in TECH_CATEGORIES}
    details: list[dict[str, str]] = []
    detected_names: list[str] = []

    for sig in TECH_SIGNATURES:
        evidence: str | None = None

        for hdr_name, hdr_rx in sig.header_rules:
            hdr_val = header_map.get(hdr_name)
            if hdr_val is not None:
                if hdr_rx is None or hdr_rx.search(hdr_val):
                    evidence = f"header:{hdr_name}"
                    break

        if evidence is None and sample_html:
            for html_rx in sig.html_patterns:
                if html_rx.search(sample_html):
                    evidence = f"html:{html_rx.pattern[:60]}"
                    break

        if evidence is not None:
            detected_names.append(sig.name)
            by_category[sig.category].append(sig.name)
            details.append(
                {
                    "name": sig.name,
                    "category": sig.category,
                    "evidence": evidence,
                }
            )

    detected_names.sort()
    for cat in TECH_CATEGORIES:
        by_category[cat].sort()
    details.sort(key=lambda item: (item["category"], item["name"]))

    return {
        "technologies": detected_names,
        "tech_count": len(detected_names),
        "tech_by_category": by_category,
        "tech_details": details,
    }


def _extract_jsonld_types_and_sameas(raw_json: str) -> tuple[set[str], list[str]]:
    types: set[str] = set()
    same_as: list[str] = []
    cleaned = raw_json.strip()
    if not cleaned:
        return types, same_as

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return types, same_as

    def _walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                _walk(item)
            return
        if not isinstance(node, dict):
            return
        raw_type = node.get("@type")
        if isinstance(raw_type, str) and raw_type.strip():
            types.add(raw_type.strip())
        elif isinstance(raw_type, list):
            for t in raw_type:
                if isinstance(t, str) and t.strip():
                    types.add(t.strip())

        raw_same = node.get("sameAs")
        if isinstance(raw_same, str) and raw_same.strip():
            same_as.append(raw_same.strip())
        elif isinstance(raw_same, list):
            for s in raw_same:
                if isinstance(s, str) and s.strip():
                    same_as.append(s.strip())

        for key, val in node.items():
            if key in ("@graph", "publisher", "author", "mainEntity", "itemListElement"):
                _walk(val)

    _walk(data)
    return types, same_as


def _classify_social_link(raw_href: str, base_url: str) -> tuple[str, str] | None:
    href = str(raw_href or "").strip()
    if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
        return None
    full = urljoin(base_url, href)
    parsed = urlparse(full)
    if parsed.scheme.lower() not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = (parsed.path or "").strip("/")
    lower_path = path.lower()
    if not path:
        return None

    clean_url = f"https://{host}/{path}"

    if host == "github.com":
        first = lower_path.split("/", 1)[0]
        if first in ("features", "pricing", "login", "signup", "explore", "marketplace", "topics", "sponsors", "about", "security", "site"):
            return None
        return ("github", clean_url)

    if host in ("x.com", "twitter.com"):
        first = lower_path.split("/", 1)[0]
        if first in ("intent", "share", "home", "search", "hashtag", "i", "explore", "login", "signup", "tos", "privacy"):
            return None
        return ("x_twitter", clean_url)

    if host == "linkedin.com":
        if lower_path.startswith(("company/", "in/", "school/", "showcase/")):
            return ("linkedin", clean_url)
        return None

    if host in ("youtube.com", "m.youtube.com"):
        if lower_path.startswith(("@", "channel/", "c/", "user/")):
            return ("youtube", f"https://youtube.com/{path}")
        return None

    return None


def _clean_mailto_address(href: str) -> str | None:
    raw = unquote(href[len("mailto:") :]).split("?", 1)[0].strip()
    if not raw:
        return None
    candidate = raw.split(",", 1)[0].strip().lower()
    if not _EMAIL_RE.match(candidate):
        return None
    domain = candidate.rsplit("@", 1)[-1]
    if domain in _IGNORED_EMAIL_DOMAINS:
        return None
    return candidate


class _PageMetadataParser(HTMLParser):
    """Single-pass stdlib HTML parser for SEO tags, JSON-LD, language, mailto, and social links."""

    def __init__(self, base_url: str, *, extract_contacts: bool = True) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.extract_contacts = extract_contacts

        self.language: str | None = None
        self.title_parts: list[str] = []
        self.meta_description: str = ""
        self.canonical_url: str | None = None
        self.og_title: str = ""
        self.jsonld_blocks: list[str] = []
        self.public_emails: set[str] = set()
        self.social_links: dict[str, set[str]] = {
            "github": set(),
            "x_twitter": set(),
            "linkedin": set(),
            "youtube": set(),
        }

        self._in_title = False
        self._in_jsonld = False
        self._jsonld_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        attr_map = {k.lower(): (v or "").strip() for k, v in attrs}

        if lower == "html" and not self.language:
            lang = attr_map.get("lang", "")
            if lang:
                self.language = lang

        elif lower == "title":
            self._in_title = True

        elif lower == "meta":
            name = attr_map.get("name", "").lower()
            prop = attr_map.get("property", "").lower()
            content = attr_map.get("content", "")
            if name == "description" and content and not self.meta_description:
                self.meta_description = content
            if prop == "og:title" and content and not self.og_title:
                self.og_title = content

        elif lower == "link":
            rel = attr_map.get("rel", "").lower().split()
            href = attr_map.get("href", "")
            if "canonical" in rel and href and not self.canonical_url:
                self.canonical_url = urljoin(self.base_url, href)

        elif lower == "script":
            script_type = attr_map.get("type", "").lower().split(";", 1)[0].strip()
            if script_type == "application/ld+json":
                self._in_jsonld = True
                self._jsonld_buf = []

        elif lower == "a" and self.extract_contacts:
            href = attr_map.get("href", "")
            if href.lower().startswith("mailto:"):
                addr = _clean_mailto_address(href)
                if addr:
                    self.public_emails.add(addr)
            elif href:
                classified = _classify_social_link(href, self.base_url)
                if classified is not None:
                    platform, clean_url = classified
                    self.social_links[platform].add(clean_url)

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower == "title":
            self._in_title = False
        elif lower == "script" and self._in_jsonld:
            self._in_jsonld = False
            block = "".join(self._jsonld_buf).strip()
            if block:
                self.jsonld_blocks.append(block)
            self._jsonld_buf = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        elif self._in_jsonld:
            self._jsonld_buf.append(data)


def extract_page_metadata(
    html_text: str,
    base_url: str,
    *,
    content_language: str | None = None,
    extract_public_contacts: bool = True,
) -> dict[str, Any]:
    """Extract SEO tags, JSON-LD @types, language, and optional public mailto/social links."""
    parser = _PageMetadataParser(base_url, extract_contacts=extract_public_contacts)
    parser.feed((html_text or "")[:MAX_HTML_BYTES])
    parser.close()

    jsonld_types: set[str] = set()
    for block in parser.jsonld_blocks:
        types, same_as_urls = _extract_jsonld_types_and_sameas(block)
        jsonld_types.update(types)
        if extract_public_contacts:
            for s_url in same_as_urls:
                classified = _classify_social_link(s_url, base_url)
                if classified is not None:
                    platform, clean_url = classified
                    parser.social_links[platform].add(clean_url)

    title = re.sub(r"\s+", " ", "".join(parser.title_parts)).strip()
    meta_desc = re.sub(r"\s+", " ", parser.meta_description).strip()
    og_title = re.sub(r"\s+", " ", parser.og_title).strip()

    lang = parser.language
    if not lang and content_language:
        lang = content_language.split(",", 1)[0].strip() or None

    return {
        "title": title,
        "meta_description": meta_desc,
        "canonical_url": parser.canonical_url,
        "og_title": og_title,
        "jsonld_types": sorted(jsonld_types),
        "language": lang,
        "public_emails": sorted(parser.public_emails) if extract_public_contacts else [],
        "social_links": {
            "github": sorted(parser.social_links["github"]) if extract_public_contacts else [],
            "x_twitter": sorted(parser.social_links["x_twitter"]) if extract_public_contacts else [],
            "linkedin": sorted(parser.social_links["linkedin"]) if extract_public_contacts else [],
            "youtube": sorted(parser.social_links["youtube"]) if extract_public_contacts else [],
        },
    }


def parse_robots_txt_sitemaps(robots_text: str, base_origin: str) -> list[str]:
    """Extract deduplicated Sitemap: directive URLs from robots.txt content."""
    sitemaps: list[str] = []
    seen: set[str] = set()
    for raw_line in (robots_text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip().lower() != "sitemap":
            continue
        cleaned_val = re.sub(r"\s+#.*$", "", value.strip()).strip()
        if not cleaned_val:
            continue
        resolved = urljoin(f"{base_origin}/", cleaned_val)
        if resolved not in seen:
            seen.add(resolved)
            sitemaps.append(resolved)
    return sitemaps


def decompress_sitemap_bytes(raw_bytes: bytes, url: str = "") -> bytes:
    """Safely decompress .xml.gz sitemap payloads with strict decompressed size cap."""
    is_gzip = raw_bytes[:2] == b"\x1f\x8b"
    if not is_gzip:
        return raw_bytes[:MAX_SITEMAP_DECOMPRESSED_BYTES]

    with gzip.GzipFile(fileobj=io.BytesIO(raw_bytes)) as gz:
        data = gz.read(MAX_SITEMAP_DECOMPRESSED_BYTES + 1)
    if len(data) > MAX_SITEMAP_DECOMPRESSED_BYTES:
        raise ValueError(
            f"Decompressed sitemap exceeded {MAX_SITEMAP_DECOMPRESSED_BYTES} byte safety limit: {url}"
        )
    return data


def _parse_lastmod_sort_key(raw_lastmod: str | None) -> float | None:
    text = str(raw_lastmod or "").strip()
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            dt = datetime.strptime(text[:10], fmt).replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue
    return None


def parse_sitemap_document(raw_bytes: bytes, source_url: str = "") -> dict[str, Any]:
    """Parse XML, gzipped XML, or plain-text sitemap safely (with DTD/ENTITY blocking)."""
    payload_bytes = decompress_sitemap_bytes(raw_bytes, url=source_url)
    text = payload_bytes.decode("utf-8", errors="replace").lstrip("\ufeff").strip()
    if not text:
        return {"kind": "empty", "urls": [], "child_sitemaps": [], "lastmods": []}

    # Plain-text URL list sitemap fallback (e.g. sitemap.txt)
    if not text.startswith("<"):
        lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith(("http://", "https://"))]
        if lines:
            return {"kind": "urlset", "urls": lines, "child_sitemaps": [], "lastmods": []}
        return {"kind": "invalid", "urls": [], "child_sitemaps": [], "lastmods": []}

    without_cdata = _CDATA_RE.sub("", text)
    if _UNSAFE_DTD_RE.search(without_cdata):
        raise ValueError(f"Blocked unsafe XML DTD/ENTITY declaration in sitemap: {source_url}")

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"Malformed sitemap XML from {source_url}: {exc}") from exc

    root_tag = root.tag.rsplit("}", 1)[-1].lower()
    urls: list[str] = []
    child_sitemaps: list[str] = []
    lastmods: list[str] = []

    if root_tag == "sitemapindex":
        for elem in root:
            if elem.tag.rsplit("}", 1)[-1].lower() != "sitemap":
                continue
            loc = ""
            lastmod = ""
            for child in elem:
                ctag = child.tag.rsplit("}", 1)[-1].lower()
                if ctag == "loc" and child.text:
                    loc = child.text.strip()
                elif ctag == "lastmod" and child.text:
                    lastmod = child.text.strip()
            if loc:
                child_sitemaps.append(loc)
            if lastmod:
                lastmods.append(lastmod)
        return {
            "kind": "sitemapindex",
            "urls": [],
            "child_sitemaps": child_sitemaps,
            "lastmods": lastmods,
        }

    if root_tag == "urlset":
        for elem in root:
            if elem.tag.rsplit("}", 1)[-1].lower() != "url":
                continue
            loc = ""
            lastmod = ""
            for child in elem:
                ctag = child.tag.rsplit("}", 1)[-1].lower()
                if ctag == "loc" and child.text:
                    loc = child.text.strip()
                elif ctag == "lastmod" and child.text:
                    lastmod = child.text.strip()
            if loc:
                urls.append(loc)
            if lastmod:
                lastmods.append(lastmod)
        return {
            "kind": "urlset",
            "urls": urls,
            "child_sitemaps": [],
            "lastmods": lastmods,
        }

    return {"kind": "unknown", "urls": [], "child_sitemaps": [], "lastmods": []}


def extract_robots_and_sitemaps(
    client: httpx.Client,
    origin: str,
    *,
    max_sitemap_urls: int = 200,
    follow_sitemap_indexes: bool = True,
    max_child_sitemaps: int = DEFAULT_MAX_CHILD_SITEMAPS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Fetch robots.txt, resolve sitemap seeds, and recursively traverse XML/gzip sitemaps."""
    robots_found = False
    robots_sitemaps: list[str] = []
    robots_url = f"{origin}/robots.txt"

    try:
        robots_resp, _ = safe_http_get(
            client,
            robots_url,
            headers={"Accept": "text/plain, */*"},
            sleep_fn=sleep_fn,
        )
        if robots_resp.status_code == 200 and robots_resp.text:
            robots_found = True
            robots_sitemaps = parse_robots_txt_sitemaps(robots_resp.text, origin)
    except (ValueError, httpx.RequestError):
        robots_found = False

    using_fallback_seeds = not bool(robots_sitemaps)
    if robots_sitemaps:
        seed_urls = robots_sitemaps[:10]
    else:
        seed_urls = [f"{origin}/sitemap.xml", f"{origin}/sitemap_index.xml"]

    queue: deque[tuple[str, bool]] = deque((u, False) for u in seed_urls)
    visited: set[str] = set()
    checked_sitemaps: list[str] = []
    sitemap_count = 0
    child_fetches_used = 0
    discovered_urls: set[str] = set()
    sample_urls: list[str] = []
    latest_lastmod: str | None = None
    latest_lastmod_ts: float | None = None
    sample_cap = max(0, int(max_sitemap_urls))

    while queue:
        sm_url, is_child = queue.popleft()
        if sm_url in visited:
            continue
        if is_child and child_fetches_used >= max_child_sitemaps:
            continue

        # Strictly re-validate every sitemap URL (robots.txt or child index) against SSRF!
        try:
            safe_sm_url = assert_safe_public_url(sm_url, preserve_path=True)
        except ValueError:
            continue

        if safe_sm_url in visited:
            continue
        visited.add(safe_sm_url)

        if is_child:
            child_fetches_used += 1

        try:
            sm_resp, resolved_sm_url = safe_http_get(
                client,
                safe_sm_url,
                headers={"Accept": "application/xml, text/xml, application/gzip, */*"},
                sleep_fn=sleep_fn,
            )
            if sm_resp.status_code != 200 or not sm_resp.content:
                continue
            parsed_sm = parse_sitemap_document(sm_resp.content, source_url=resolved_sm_url)
        except (ValueError, httpx.RequestError, OSError, EOFError):
            continue

        kind = parsed_sm["kind"]
        if kind not in ("sitemapindex", "urlset"):
            continue

        sitemap_count += 1
        checked_sitemaps.append(resolved_sm_url)

        for lm in parsed_sm["lastmods"]:
            ts = _parse_lastmod_sort_key(lm)
            if ts is not None and (latest_lastmod_ts is None or ts > latest_lastmod_ts):
                latest_lastmod_ts = ts
                latest_lastmod = lm

        if kind == "urlset":
            for page_url in parsed_sm["urls"]:
                if page_url not in discovered_urls:
                    discovered_urls.add(page_url)
                    if len(sample_urls) < sample_cap:
                        sample_urls.append(page_url)
            # If /sitemap.xml succeeded during fallback probing, no need to probe /sitemap_index.xml
            if using_fallback_seeds and not is_child:
                break

        elif kind == "sitemapindex":
            if follow_sitemap_indexes:
                for child_url in parsed_sm["child_sitemaps"]:
                    if child_url not in visited:
                        queue.append((child_url, True))
            if using_fallback_seeds and not is_child:
                # Drop unvisited fallback probe (/sitemap_index.xml) if /sitemap.xml already was an index
                queue = deque(item for item in queue if item[1])

    return {
        "robots_txt_found": robots_found,
        "sitemap_count": sitemap_count,
        "sitemap_urls_checked": checked_sitemaps,
        "discovered_url_count": len(discovered_urls),
        "latest_lastmod": latest_lastmod,
        "sample_urls": sample_urls,
    }


def profile_website(
    raw_url: str,
    *,
    max_sitemap_urls: int = 200,
    follow_sitemap_indexes: bool = True,
    max_child_sitemaps: int = DEFAULT_MAX_CHILD_SITEMAPS,
    extract_public_contacts: bool = True,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Profile a single public website for tech stack, recursive sitemaps, and SEO/contact metadata."""
    normalized_url = normalize_target_url(raw_url)
    own_client = client is None
    active = (
        client
        if client is not None
        else httpx.Client(
            timeout=25.0,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            follow_redirects=False,
        )
    )

    try:
        resp, final_url = safe_http_get(
            active,
            normalized_url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            max_redirects=3,
            sleep_fn=sleep_fn,
        )
        resp.raise_for_status()

        parsed_final = urlparse(final_url)
        origin = f"{parsed_final.scheme}://{parsed_final.netloc}"
        domain = (parsed_final.hostname or "").lower()
        html_text = resp.text[:MAX_HTML_BYTES]

        tech_info = detect_tech_stack(resp.headers, html_text)
        seo_info = extract_page_metadata(
            html_text,
            final_url,
            content_language=resp.headers.get("content-language"),
            extract_public_contacts=extract_public_contacts,
        )
        sitemap_info = extract_robots_and_sitemaps(
            active,
            origin,
            max_sitemap_urls=max_sitemap_urls,
            follow_sitemap_indexes=follow_sitemap_indexes,
            max_child_sitemaps=max_child_sitemaps,
            sleep_fn=sleep_fn,
        )
    finally:
        if own_client:
            active.close()

    return {
        "record_type": "site_profile",
        "status": "ok",
        "input_url": str(raw_url).strip(),
        "final_url": final_url,
        "domain": domain,
        "http_status": resp.status_code,
        "technologies": tech_info["technologies"],
        "tech_count": tech_info["tech_count"],
        "tech_by_category": tech_info["tech_by_category"],
        "tech_details": tech_info["tech_details"],
        "robots_txt_found": sitemap_info["robots_txt_found"],
        "sitemap_count": sitemap_info["sitemap_count"],
        "sitemap_urls_checked": sitemap_info["sitemap_urls_checked"],
        "discovered_url_count": sitemap_info["discovered_url_count"],
        "latest_lastmod": sitemap_info["latest_lastmod"],
        "sample_urls": sitemap_info["sample_urls"],
        "title": seo_info["title"],
        "meta_description": seo_info["meta_description"],
        "canonical_url": seo_info["canonical_url"],
        "og_title": seo_info["og_title"],
        "jsonld_types": seo_info["jsonld_types"],
        "language": seo_info["language"],
        "public_emails": seo_info["public_emails"],
        "social_links": seo_info["social_links"],
    }


def profile_websites(
    urls: list[str],
    *,
    max_sitemap_urls: int = 200,
    follow_sitemap_indexes: bool = True,
    max_child_sitemaps: int = DEFAULT_MAX_CHILD_SITEMAPS,
    extract_public_contacts: bool = True,
    request_delay_sec: float = 0.25,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Batch-profile multiple websites with strict per-site fault isolation."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in urls:
        token = str(raw or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        cleaned.append(token)

    if not cleaned:
        return []

    own_client = client is None
    active = (
        client
        if client is not None
        else httpx.Client(
            timeout=25.0,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            follow_redirects=False,
        )
    )
    results: list[dict[str, Any]] = []
    try:
        for idx, raw_url in enumerate(cleaned):
            if idx > 0 and request_delay_sec > 0:
                sleep_fn(request_delay_sec)
            try:
                profile = profile_website(
                    raw_url,
                    max_sitemap_urls=max_sitemap_urls,
                    follow_sitemap_indexes=follow_sitemap_indexes,
                    max_child_sitemaps=max_child_sitemaps,
                    extract_public_contacts=extract_public_contacts,
                    client=active,
                    sleep_fn=sleep_fn,
                )
                results.append(profile)
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                results.append(
                    {
                        "record_type": "error",
                        "status": "error",
                        "input_url": raw_url,
                        "http_status": status_code,
                        "error_message": f"HTTP {status_code}: {exc}",
                    }
                )
            except (ValueError, httpx.RequestError) as exc:
                results.append(
                    {
                        "record_type": "error",
                        "status": "error",
                        "input_url": raw_url,
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
        raw_urls = actor_input.get("urls") or []
        urls = [str(u).strip() for u in raw_urls if str(u).strip()]
        if not urls:
            raise ValueError("Provide at least one website URL or domain in 'urls'.")

        max_sitemap_urls = max(0, min(int(actor_input.get("maxSitemapUrls", 200)), 10000))
        follow_indexes = bool(actor_input.get("followSitemapIndexes", True))
        extract_contacts = bool(actor_input.get("extractPublicContacts", True))
        request_delay_ms = max(0, min(int(actor_input.get("requestDelayMs") or 250), 5000))

        records = await asyncio.to_thread(
            profile_websites,
            urls,
            max_sitemap_urls=max_sitemap_urls,
            follow_sitemap_indexes=follow_indexes,
            extract_public_contacts=extract_contacts,
            request_delay_sec=request_delay_ms / 1000.0,
        )

        for rec in records:
            await Actor.push_data(rec)
            if rec.get("status") == "ok" and rec.get("record_type") == "site_profile":
                await Actor.charge(event_name="site_profiled", count=1)


if __name__ == "__main__":
    asyncio.run(main())
