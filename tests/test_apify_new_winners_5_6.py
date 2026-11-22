"""Comprehensive offline unit tests for Apify Global Winners #5 & #6:
5. ats_jobs_board_extractor_actor (ats-greenhouse-lever-ashby-jobs-extractor)
6. tech_stack_sitemap_intel_actor (website-tech-stack-sitemap-extractor)
"""

from __future__ import annotations

import ast
import gzip
import json
from pathlib import Path

import httpx
import pytest

from tracks.track1_apify.ats_jobs_board_extractor_actor.main import (
    TECH_TAG_PATTERNS,
    assert_safe_public_url as ats_assert_safe_url,
    classify_seniority,
    classify_workplace_type,
    extract_ats_boards,
    extract_board_jobs,
    extract_salary_from_text,
    extract_tech_tags,
    html_to_clean_text,
    parse_board_target,
    safe_http_get as ats_safe_get,
)
from tracks.track1_apify.tech_stack_sitemap_intel_actor.main import (
    TECH_CATEGORIES,
    TECH_SIGNATURES,
    assert_safe_public_url as intel_assert_safe_url,
    decompress_sitemap_bytes,
    detect_tech_stack,
    extract_page_metadata,
    parse_robots_txt_sitemaps,
    parse_sitemap_document,
    profile_website,
    profile_websites,
    safe_http_get as intel_safe_get,
)

ACTOR_ROOT = Path("tracks/track1_apify")
NEW_WINNER_ACTORS = (
    "ats_jobs_board_extractor_actor",
    "tech_stack_sitemap_intel_actor",
)


# ---------------------------------------------------------------------------
# Cross-Actor Packaging, Standalone Isolation & Apify Schema Compliance Tests
# ---------------------------------------------------------------------------


def test_new_winner_actors_standalone_isolation_and_schemas() -> None:
    expected_names = {
        "ats_jobs_board_extractor_actor": "ats-greenhouse-lever-ashby-jobs-extractor",
        "tech_stack_sitemap_intel_actor": "website-tech-stack-sitemap-extractor",
    }

    for folder in NEW_WINNER_ACTORS:
        base = ACTOR_ROOT / folder
        main_py = base / "main.py"
        assert (base / "__init__.py").exists(), f"Missing __init__.py in {folder}"
        assert main_py.exists(), f"Missing {main_py}"
        assert (base / "Dockerfile").exists(), f"Missing Dockerfile in {folder}"
        assert (base / "requirements.txt").exists(), f"Missing requirements.txt in {folder}"
        assert (base / "README.md").exists(), f"Missing README.md in {folder}"
        assert len((base / "README.md").read_text(encoding="utf-8")) > 500

        source = main_py.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(main_py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("makemoney"), f"{folder} imports makemoney"
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("makemoney"), f"{folder} imports makemoney"

        actor_json = json.loads((base / ".actor/actor.json").read_text(encoding="utf-8"))
        assert actor_json["actorSpecification"] == 1
        assert actor_json["name"] == expected_names[folder]
        assert actor_json["input"] == "./input_schema.json"
        assert actor_json["dockerfile"] == "../Dockerfile"

        schema = json.loads((base / ".actor/input_schema.json").read_text(encoding="utf-8"))
        assert schema["title"]
        assert schema["type"] == "object"
        assert schema["schemaVersion"] == 1
        props = schema["properties"]
        assert isinstance(props, dict) and props
        for key, prop in props.items():
            assert str(prop.get("title") or "").strip(), f"{folder}:{key} missing title"
            assert str(prop.get("type") or "").strip(), f"{folder}:{key} missing type"
            assert str(prop.get("description") or "").strip(), f"{folder}:{key} missing description"
            if prop.get("type") in {"array", "object"}:
                assert str(prop.get("editor") or "").strip(), f"{folder}:{key} missing editor"


def test_new_winner_actors_pay_per_event_specs() -> None:
    ats_ppe = json.loads(
        (ACTOR_ROOT / "ats_jobs_board_extractor_actor/.actor/pay_per_event.json").read_text(
            encoding="utf-8"
        )
    )
    assert ats_ppe["pricingModel"] == "PAY_PER_EVENT"
    assert ats_ppe["minimalMaxTotalChargeUsd"] == 0.05
    ats_events = ats_ppe["pricingPerEvent"]["actorChargeEvents"]
    assert ats_events["job_extracted"]["eventPriceUsd"] == 0.001
    assert ats_events["job_extracted"]["isPrimaryEvent"] is True

    intel_ppe = json.loads(
        (ACTOR_ROOT / "tech_stack_sitemap_intel_actor/.actor/pay_per_event.json").read_text(
            encoding="utf-8"
        )
    )
    assert intel_ppe["pricingModel"] == "PAY_PER_EVENT"
    assert intel_ppe["minimalMaxTotalChargeUsd"] == 0.05
    intel_events = intel_ppe["pricingPerEvent"]["actorChargeEvents"]
    assert intel_events["site_profiled"]["eventPriceUsd"] == 0.002
    assert intel_events["site_profiled"]["isPrimaryEvent"] is True


# ---------------------------------------------------------------------------
# Actor #5: Greenhouse, Lever & Ashby ATS Jobs Board Extractor
# ---------------------------------------------------------------------------


def test_ats_parse_board_targets_and_url_autodetection() -> None:
    gh_dict = parse_board_target({"provider": "greenhouse", "slug": "stripe"})
    assert gh_dict["provider"] == "greenhouse"
    assert gh_dict["slug"] == "stripe"
    assert gh_dict["api_url"] == "https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true"

    gh_url = parse_board_target("https://boards.greenhouse.io/stripe")
    assert gh_url["provider"] == "greenhouse"
    assert gh_url["slug"] == "stripe"
    assert gh_url["api_url"] == "https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true"

    gh_eu = parse_board_target("https://job-boards.eu.greenhouse.io/acme-eu")
    assert gh_eu["provider"] == "greenhouse"
    assert gh_eu["eu_region"] is True
    assert gh_eu["api_url"] == "https://boards-api.eu.greenhouse.io/v1/boards/acme-eu/jobs?content=true"

    lv_url = parse_board_target("https://jobs.lever.co/netlify")
    assert lv_url["provider"] == "lever"
    assert lv_url["slug"] == "netlify"
    assert lv_url["api_url"] == "https://api.lever.co/v0/postings/netlify?mode=json"

    lv_eu = parse_board_target("https://jobs.eu.lever.co/eurocorp")
    assert lv_eu["provider"] == "lever"
    assert lv_eu["eu_region"] is True
    assert lv_eu["api_url"] == "https://api.eu.lever.co/v0/postings/eurocorp?mode=json"

    ab_url = parse_board_target("https://jobs.ashbyhq.com/linear")
    assert ab_url["provider"] == "ashby"
    assert ab_url["slug"] == "linear"
    assert (
        ab_url["api_url"]
        == "https://api.ashbyhq.com/posting-api/job-board/linear?includeCompensation=true"
    )

    shorthand = parse_board_target("ashby:openai")
    assert shorthand["provider"] == "ashby"
    assert shorthand["slug"] == "openai"


def test_ats_ssrf_host_validation_and_redirect_blocking() -> None:
    for bad_input in (
        "http://127.0.0.1/stripe",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/jobs",
        "http://192.168.1.3/jobs",
        "http://localhost:8080/jobs",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://[::1]/jobs",
        "http://[::ffff:127.0.0.1]/jobs",
        "https://user:pass@boards.greenhouse.io/stripe",
        "file:///etc/passwd",
        "https://evil.example.com/stripe",
        {"provider": "greenhouse", "slug": "../etc/passwd"},
        {"provider": "workday", "slug": "acme"},
    ):
        with pytest.raises(ValueError):
            parse_board_target(bad_input)

    with pytest.raises(ValueError):
        ats_assert_safe_url("http://169.254.169.254/latest/meta-data")

    def evil_redirect_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data"})

    with httpx.Client(transport=httpx.MockTransport(evil_redirect_handler)) as client:
        with pytest.raises(ValueError, match="Forbidden non-public IP"):
            ats_safe_get(
                client,
                "https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true",
            )

    def non_ats_redirect_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(301, headers={"Location": "https://8.8.8.8/evil"})

    with httpx.Client(transport=httpx.MockTransport(non_ats_redirect_handler)) as client:
        with pytest.raises(ValueError, match="not an allowed ATS API host"):
            ats_safe_get(
                client,
                "https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true",
            )


def test_ats_enrichment_workplace_seniority_salary_and_tech_tags() -> None:
    assert len(TECH_TAG_PATTERNS) >= 35

    # Workplace classification
    assert classify_workplace_type(explicit_value="Remote") == "remote"
    assert classify_workplace_type(is_remote_flag=True) == "remote"
    assert classify_workplace_type(location="San Francisco, CA (Hybrid)") == "hybrid"
    assert classify_workplace_type(location="New York, NY - On-site") == "onsite"
    assert classify_workplace_type(location="Remote - US") == "remote"
    assert (
        classify_workplace_type(
            location="Berlin",
            description_text="This is a 100% remote role open across EU timezones.",
        )
        == "remote"
    )
    assert classify_workplace_type(location="Tokyo, Japan") == "unspecified"

    # Seniority classification across all 6 tiers
    assert classify_seniority("Software Engineering Intern") == "intern"
    assert classify_seniority("Junior Frontend Engineer") == "junior"
    assert classify_seniority("Associate Product Manager") == "junior"
    assert classify_seniority("Software Engineer") == "mid"
    assert classify_seniority("Product Manager") == "mid"
    assert classify_seniority("Senior Backend Engineer") == "senior"
    assert classify_seniority("Senior Product Manager") == "senior"
    assert classify_seniority("Senior / Staff Fullstack Engineer") == "staff_principal"
    assert classify_seniority("Principal Distributed Systems Architect") == "staff_principal"
    assert classify_seniority("Engineering Manager, Core Infra") == "manager_exec"
    assert classify_seniority("VP of Engineering") == "manager_exec"
    assert classify_seniority("Director of AI Research") == "manager_exec"

    # Salary text extraction
    assert extract_salary_from_text("Base range is $180,000 - $220,000 USD per year.") == (
        180000,
        220000,
        "USD",
        "yearly",
    )
    assert extract_salary_from_text("Compensation: $150k–$195k + equity") == (
        150000,
        195000,
        "USD",
        "yearly",
    )
    assert extract_salary_from_text("Salary: €85,000 - €105,000 annually") == (
        85000,
        105000,
        "EUR",
        "yearly",
    )
    assert extract_salary_from_text("Contract rate: $65 - $85/hr") == (
        65,
        85,
        "USD",
        "hourly",
    )
    assert extract_salary_from_text("Enjoy $20 - $50 lunch credit every Friday!") == (
        None,
        None,
        None,
        None,
    )

    # Tech tags & false-positive hygiene
    tags = extract_tech_tags(
        "Staff AI Infrastructure Engineer",
        "Build services in Python, TypeScript, Go, Rust, C++, Solidity, SQL, PyTorch, React, Kubernetes, AWS, Terraform, and PostgreSQL.",
    )
    for expected in (
        "AWS",
        "C++",
        "Go",
        "Kubernetes",
        "PostgreSQL",
        "PyTorch",
        "Python",
        "React",
        "Rust",
        "SQL",
        "Solidity",
        "Terraform",
        "TypeScript",
    ):
        assert expected in tags

    # Avoid matching lowercase "go" or matching "Java" inside "JavaScript"
    clean_tags = extract_tech_tags(
        "Frontend Developer",
        "We go fast and build modern JavaScript apps with React.",
    )
    assert "JavaScript" in clean_tags
    assert "React" in clean_tags
    assert "Go" not in clean_tags
    assert "Java" not in clean_tags

    # Greenhouse HTML-entity-escaped content cleaning
    cleaned = html_to_clean_text("&lt;h2&gt;Role&lt;/h2&gt;&lt;p&gt;Build &lt;b&gt;fast&lt;/b&gt; APIs.&lt;/p&gt;")
    assert "Role" in cleaned
    assert "Build fast APIs." in cleaned
    assert "<h2>" not in cleaned


def test_ats_greenhouse_lever_ashby_mocked_parsing_filters_retry_and_fault_isolation() -> None:
    calls: dict[str, int] = {"greenhouse": 0}
    sleeps: list[float] = []

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if "boards-api.greenhouse.io/v1/boards/stripe/jobs" in url:
            calls["greenhouse"] += 1
            if calls["greenhouse"] == 1:
                return httpx.Response(429, headers={"Retry-After": "1"})
            return httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "id": 1001,
                            "title": "Senior Infrastructure Engineer",
                            "company_name": "Stripe",
                            "absolute_url": "https://stripe.com/jobs/1001",
                            "location": {"name": "Remote - US"},
                            "departments": [{"id": 1, "name": "Engineering"}],
                            "metadata": [{"name": "Team", "value": "Core Cloud"}],
                            "first_published": "2026-11-01T12:00:00Z",
                            "content": "&lt;p&gt;Scale Kubernetes, Go, and AWS systems. Base range: $195,000 - $245,000 USD.&lt;/p&gt;",
                        },
                        {
                            "id": 1002,
                            "title": "Account Executive",
                            "company_name": "Stripe",
                            "absolute_url": "https://stripe.com/jobs/1002",
                            "location": {"name": "New York, NY"},
                            "departments": [{"id": 2, "name": "Sales"}],
                            "first_published": "2026-11-02T12:00:00Z",
                            "content": "&lt;p&gt;On-site enterprise sales role.&lt;/p&gt;",
                        },
                    ]
                },
            )

        if "api.lever.co/v0/postings/netflix" in url:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "lev-99",
                        "text": "Staff ML Engineer",
                        "categories": {
                            "department": "AI Platform",
                            "team": "Recommendations",
                            "location": "Los Gatos, CA",
                        },
                        "workplaceType": "hybrid",
                        "salaryRange": {
                            "min": 250000,
                            "max": 340000,
                            "currency": "USD",
                            "interval": "per-year-salary",
                        },
                        "createdAt": 1763510400000,
                        "hostedUrl": "https://jobs.lever.co/netflix/lev-99",
                        "applyUrl": "https://jobs.lever.co/netflix/lev-99/apply",
                        "descriptionPlain": "Train large PyTorch and Spark recommendation models.",
                        "lists": [
                            {
                                "text": "Requirements",
                                "content": "<li>Strong Python and SQL skills</li>",
                            }
                        ],
                        "additionalPlain": "Equal opportunity employer.",
                    }
                ],
            )

        if "api.ashbyhq.com/posting-api/job-board/linear" in url:
            return httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "id": "ash-77",
                            "title": "Senior / Staff Fullstack Engineer",
                            "department": "Product",
                            "team": "Core App",
                            "location": "Europe",
                            "secondaryLocations": [{"location": "North America"}],
                            "publishedAt": "2026-11-10T10:00:00Z",
                            "isListed": True,
                            "isRemote": True,
                            "workplaceType": "Remote",
                            "applyUrl": "https://jobs.ashbyhq.com/linear/ash-77/application",
                            "descriptionPlain": "Craft real-time TypeScript, React, and PostgreSQL sync engines.",
                            "compensation": {
                                "summaryComponents": [
                                    {
                                        "compensationType": "Salary",
                                        "currencyCode": "USD",
                                        "minValue": 210000,
                                        "maxValue": 265000,
                                        "interval": "1 YEAR",
                                    }
                                ]
                            },
                        },
                        {
                            "id": "ash-hidden",
                            "title": "Unlisted Internal Role",
                            "isListed": False,
                            "descriptionPlain": "Should be ignored.",
                        },
                    ]
                },
            )

        if "api.lever.co/v0/postings/missingco" in url:
            return httpx.Response(404, text="Not Found")

        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows = extract_ats_boards(
            [
                {"provider": "greenhouse", "slug": "stripe"},
                {"provider": "lever", "slug": "netflix"},
                "https://jobs.ashbyhq.com/linear",
                "https://jobs.lever.co/missingco",
                "http://127.0.0.1/stripe",
            ],
            request_delay_sec=0.0,
            client=client,
            sleep_fn=sleeps.append,
        )

        # Retry-After=1 on Greenhouse 429 was honored
        assert calls["greenhouse"] == 2
        assert 1.0 in sleeps

        ok_jobs = [r for r in rows if r["record_type"] == "job"]
        errors = [r for r in rows if r["record_type"] == "error"]
        assert len(ok_jobs) == 4  # 2 GH + 1 Lever + 1 Ashby (unlisted skipped)
        assert len(errors) == 2  # 404 missingco + SSRF 127.0.0.1

        gh_eng = next(j for j in ok_jobs if j["job_id"] == "1001")
        assert gh_eng["provider"] == "greenhouse"
        assert gh_eng["department"] == "Engineering"
        assert gh_eng["team"] == "Core Cloud"
        assert gh_eng["workplace_type"] == "remote"
        assert gh_eng["seniority"] == "senior"
        assert gh_eng["salary_min"] == 195000
        assert gh_eng["salary_max"] == 245000
        assert gh_eng["salary_currency"] == "USD"
        assert {"AWS", "Go", "Kubernetes"}.issubset(set(gh_eng["tech_tags"]))

        lv_ml = next(j for j in ok_jobs if j["job_id"] == "lev-99")
        assert lv_ml["provider"] == "lever"
        assert lv_ml["workplace_type"] == "hybrid"
        assert lv_ml["seniority"] == "staff_principal"
        assert lv_ml["salary_min"] == 250000
        assert lv_ml["salary_max"] == 340000
        assert lv_ml["salary_interval"] == "yearly"
        assert lv_ml["published_at"] is not None and lv_ml["published_at"].endswith("Z")
        assert {"PyTorch", "Python", "SQL", "Spark"}.issubset(set(lv_ml["tech_tags"]))

        ab_fs = next(j for j in ok_jobs if j["job_id"] == "ash-77")
        assert ab_fs["provider"] == "ashby"
        assert ab_fs["workplace_type"] == "remote"
        assert ab_fs["seniority"] == "staff_principal"
        assert ab_fs["location"] == "Europe, North America"
        assert ab_fs["salary_min"] == 210000
        assert ab_fs["salary_max"] == 265000
        assert {"PostgreSQL", "React", "TypeScript"}.issubset(set(ab_fs["tech_tags"]))

        # Verify filters: remoteOnly + keywordFilter + departmentFilter + maxJobsPerBoard
        filtered = extract_board_jobs(
            {"provider": "greenhouse", "slug": "stripe"},
            remote_only=True,
            keyword_filter="kubernetes",
            department_filter="engineering",
            max_jobs=1,
            client=client,
            sleep_fn=sleeps.append,
        )
        assert len(filtered) == 1
        assert filtered[0]["job_id"] == "1001"


# ---------------------------------------------------------------------------
# Actor #6: Website Tech Stack, Recursive Sitemap & SEO Intelligence Extractor
# ---------------------------------------------------------------------------


def test_tech_stack_catalog_size_and_7_category_detection() -> None:
    assert len(TECH_SIGNATURES) >= 60
    covered_categories = {sig.category for sig in TECH_SIGNATURES}
    assert covered_categories == set(TECH_CATEGORIES)

    headers = httpx.Headers(
        [
            ("Server", "cloudflare"),
            ("CF-Ray", "8abc123-NRT"),
            ("X-Vercel-Id", "hnd1::abc123"),
            ("X-Shopify-Stage", "production"),
            ("X-Powered-By", "Next.js"),
            ("Sentry-Trace", "deadbeef-1234-1"),
            ("Set-Cookie", "hubspotutk=xyz123; Path=/"),
        ]
    )
    html_sample = """
    <html lang="en">
      <head>
        <meta name="generator" content="WordPress 6.6" />
        <script src="/_next/static/chunks/main.js"></script>
        <script src="https://www.googletagmanager.com/gtag/js?id=G-ABC12345"></script>
        <script src="https://www.googletagmanager.com/gtm.js?id=GTM-XYZ99"></script>
        <script src="https://connect.facebook.net/en_US/fbevents.js"></script>
        <script src="https://cdn.segment.com/analytics.js/v1/abc/analytics.min.js"></script>
        <script src="https://us.i.posthog.com/static/array.js"></script>
        <script src="https://js.stripe.com/v3/"></script>
        <script src="https://widget.intercom.io/widget/abc"></script>
        <script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>
        <script src="https://cdn.auth0.com/js/auth0-spa-js/2.0/auth0-spa-js.production.js"></script>
        <link rel="stylesheet" href="https://cdn.tailwindcss.com" />
      </head>
      <body><div data-wf-site="12345" class="cf-turnstile"></div></body>
    </html>
    """
    result = detect_tech_stack(headers, html_sample)
    detected = set(result["technologies"])
    expected_subset = {
        "Next.js",
        "React",
        "Tailwind CSS",
        "Shopify",
        "WordPress",
        "Webflow",
        "Google Analytics 4",
        "Google Tag Manager",
        "Meta Pixel",
        "Segment",
        "PostHog",
        "Sentry",
        "Stripe",
        "Cloudflare",
        "Vercel",
        "Intercom",
        "HubSpot",
        "Cloudflare Turnstile",
        "Auth0",
    }
    assert expected_subset.issubset(detected)
    assert result["tech_count"] == len(result["technologies"])
    for cat in TECH_CATEGORIES:
        assert len(result["tech_by_category"][cat]) >= 1


def test_intel_ssrf_and_redirect_hop_revalidation() -> None:
    for bad_url in (
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/",
        "http://192.168.1.3/",
        "http://localhost:3000/",
        "http://metadata.google.internal/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "https://user:pass@8.8.8.8/",
        "file:///etc/passwd",
    ):
        with pytest.raises(ValueError):
            intel_assert_safe_url(bad_url)

    # Hop 1 -> public IP, Hop 2 -> cloud metadata IP must be blocked!
    hop_count = {"n": 0}

    def evil_chain(req: httpx.Request) -> httpx.Response:
        hop_count["n"] += 1
        if hop_count["n"] == 1:
            return httpx.Response(301, headers={"Location": "https://1.1.1.1/step2"})
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data"})

    with httpx.Client(transport=httpx.MockTransport(evil_chain)) as client:
        with pytest.raises(ValueError, match="Forbidden non-public IP"):
            intel_safe_get(client, "https://8.8.8.8/", max_redirects=3)

    # Infinite redirect loop blocked after max_redirects=3
    def loop_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(301, headers={"Location": "https://8.8.8.8/loop"})

    with httpx.Client(transport=httpx.MockTransport(loop_handler)) as client:
        with pytest.raises(ValueError, match="Exceeded maximum redirects"):
            intel_safe_get(client, "https://8.8.8.8/", max_redirects=3)


def test_intel_robots_gzip_sitemap_index_recursion_and_dtd_guard() -> None:
    robots = """
    User-agent: *
    Disallow: /admin
    Sitemap: https://8.8.8.8/sitemap-index.xml # main index
    """
    assert parse_robots_txt_sitemaps(robots, "https://8.8.8.8") == [
        "https://8.8.8.8/sitemap-index.xml"
    ]

    # DTD/ENTITY XXE attack blocked cleanly
    xxe_xml = b'<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><urlset/>'
    with pytest.raises(ValueError, match="Blocked unsafe XML DTD/ENTITY"):
        parse_sitemap_document(xxe_xml, "https://8.8.8.8/evil.xml")

    # Gzip decompression works seamlessly
    xml_body = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://8.8.8.8/docs/a</loc><lastmod>2026-11-18T00:00:00Z</lastmod></url>"
        b"<url><loc>https://8.8.8.8/docs/b</loc><lastmod>2026-11-19T12:30:00Z</lastmod></url>"
        b"</urlset>"
    )
    gz_bytes = gzip.compress(xml_body)
    assert decompress_sitemap_bytes(gz_bytes, "https://8.8.8.8/s.xml.gz") == xml_body

    parsed_gz = parse_sitemap_document(gz_bytes, "https://8.8.8.8/s.xml.gz")
    assert parsed_gz["kind"] == "urlset"
    assert len(parsed_gz["urls"]) == 2


def test_intel_full_profile_gzip_recursion_seo_contacts_retry_and_batch_isolation() -> None:
    calls: dict[str, int] = {"home": 0}
    sleeps: list[float] = []

    child1_gz = gzip.compress(
        b'<?xml version="1.0"?>'
        b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://8.8.8.8/blog/post-1</loc><lastmod>2026-11-15</lastmod></url>"
        b"<url><loc>https://8.8.8.8/blog/post-2</loc><lastmod>2026-11-19T08:00:00Z</lastmod></url>"
        b"</urlset>"
    )
    child2_xml = (
        b'<?xml version="1.0"?>'
        b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<url><loc>https://8.8.8.8/pricing</loc><lastmod>2026-11-10</lastmod></url>"
        b"</urlset>"
    )
    index_xml = (
        b'<?xml version="1.0"?>'
        b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<sitemap><loc>https://8.8.8.8/sitemaps/blog.xml.gz</loc><lastmod>2026-11-19T08:00:00Z</lastmod></sitemap>"
        b"<sitemap><loc>https://8.8.8.8/sitemaps/pages.xml</loc><lastmod>2026-11-10</lastmod></sitemap>"
        b"<sitemap><loc>http://169.254.169.254/ssrf.xml</loc></sitemap>"
        b"<sitemap><loc>https://8.8.8.8/sitemaps/extra-3.xml</loc></sitemap>"
        b"<sitemap><loc>https://8.8.8.8/sitemaps/extra-4.xml</loc></sitemap>"
        b"<sitemap><loc>https://8.8.8.8/sitemaps/extra-5.xml</loc></sitemap>"
        b"<sitemap><loc>https://8.8.8.8/sitemaps/extra-6-capped.xml</loc></sitemap>"
        b"</sitemapindex>"
    )

    home_html = """
    <!doctype html>
    <html lang="en-US">
      <head>
        <title>Acme Cloud — Developer Platform</title>
        <meta name="description" content="Deploy globally in seconds." />
        <meta property="og:title" content="Acme Cloud OG" />
        <link rel="canonical" href="/home" />
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@graph": [
              {
                "@type": "Organization",
                "name": "Acme Cloud",
                "sameAs": [
                  "https://github.com/acme-cloud",
                  "https://x.com/acmecloud",
                  "https://www.linkedin.com/company/acme-cloud",
                  "https://youtube.com/@acmecloud"
                ]
              },
              {"@type": ["WebSite", "SoftwareApplication"]}
            ]
          }
        </script>
        <script src="/_next/static/chunks/app.js"></script>
        <script src="https://js.stripe.com/v3/"></script>
        <script src="https://us.i.posthog.com/static/array.js"></script>
      </head>
      <body>
        <a href="mailto:Hello@AcmeCloud.io?subject=Demo">Contact</a>
        <a href="mailto:ignore@example.com">Placeholder</a>
        <a href="https://twitter.com/intent/tweet?text=share">Share</a>
      </body>
    </html>
    """

    def handler(req: httpx.Request) -> httpx.Response:
        host = req.url.host
        path = req.url.path

        if host == "1.1.1.1":
            return httpx.Response(500, text="Internal Error")

        if host == "8.8.8.8":
            if path in ("", "/"):
                calls["home"] += 1
                if calls["home"] == 1:
                    return httpx.Response(503, headers={"Retry-After": "1"})
                return httpx.Response(
                    200,
                    headers={"Server": "Vercel", "X-Vercel-Id": "sfo1::xyz"},
                    text=home_html,
                )
            if path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nSitemap: https://8.8.8.8/sitemap_index.xml\n")
            if path == "/sitemap_index.xml":
                return httpx.Response(200, content=index_xml)
            if path == "/sitemaps/blog.xml.gz":
                return httpx.Response(200, headers={"Content-Type": "application/gzip"}, content=child1_gz)
            if path == "/sitemaps/pages.xml":
                return httpx.Response(200, content=child2_xml)
            if path.startswith("/sitemaps/extra-"):
                return httpx.Response(
                    200,
                    content=(
                        b'<?xml version="1.0"?><urlset>'
                        + f"<url><loc>https://8.8.8.8{path}/page</loc></url>".encode("utf-8")
                        + b"</urlset>"
                    ),
                )

        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows = profile_websites(
            ["https://1.1.1.1", "http://127.0.0.1", "8.8.8.8"],
            max_sitemap_urls=2,
            follow_sitemap_indexes=True,
            extract_public_contacts=True,
            request_delay_sec=0.0,
            client=client,
            sleep_fn=sleeps.append,
        )

        assert calls["home"] == 2
        assert 1.0 in sleeps

        ok_rows = [r for r in rows if r["record_type"] == "site_profile"]
        err_rows = [r for r in rows if r["record_type"] == "error"]
        assert len(ok_rows) == 1
        assert len(err_rows) == 2

        site = ok_rows[0]
        assert site["domain"] == "8.8.8.8"
        assert site["http_status"] == 200
        assert {"Next.js", "PostHog", "React", "Stripe", "Vercel"}.issubset(set(site["technologies"]))
        assert site["robots_txt_found"] is True
        # 1 index + max 5 child sitemaps (SSRF child skipped cleanly, 6th valid child capped at 5)
        assert site["sitemap_count"] == 6
        assert site["discovered_url_count"] == 6  # 2 blog + 1 pricing + 3 extra (extra-3, extra-4, extra-5)
        assert len(site["sample_urls"]) == 2  # capped by max_sitemap_urls=2
        assert site["latest_lastmod"] == "2026-11-19T08:00:00Z"

        assert site["title"] == "Acme Cloud — Developer Platform"
        assert site["meta_description"] == "Deploy globally in seconds."
        assert site["canonical_url"] == "https://8.8.8.8/home"
        assert site["og_title"] == "Acme Cloud OG"
        assert site["language"] == "en-US"
        assert site["jsonld_types"] == ["Organization", "SoftwareApplication", "WebSite"]
        assert site["public_emails"] == ["hello@acmecloud.io"]
        assert site["social_links"]["github"] == ["https://github.com/acme-cloud"]
        assert site["social_links"]["x_twitter"] == ["https://x.com/acmecloud"]
        assert site["social_links"]["linkedin"] == ["https://linkedin.com/company/acme-cloud"]
        assert site["social_links"]["youtube"] == ["https://youtube.com/@acmecloud"]

        # Verify extract_public_contacts=False suppresses emails and social links
        no_contact = profile_website(
            "https://8.8.8.8",
            extract_public_contacts=False,
            follow_sitemap_indexes=False,
            client=client,
            sleep_fn=sleeps.append,
        )
        assert no_contact["public_emails"] == []
        assert all(v == [] for v in no_contact["social_links"].values())
        assert no_contact["sitemap_count"] == 1  # index only, no child traversal


def test_intel_fallback_sitemap_when_robots_missing() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path in ("", "/"):
            return httpx.Response(200, text="<html lang='ja'><head><title>Test</title></head></html>")
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/sitemap.xml":
            return httpx.Response(404)
        if req.url.path == "/sitemap_index.xml":
            return httpx.Response(
                200,
                content=(
                    b'<?xml version="1.0"?><urlset>'
                    b"<url><loc>https://8.8.8.8/only-page</loc><lastmod>2026-11-12</lastmod></url>"
                    b"</urlset>"
                ),
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        site = profile_website("https://8.8.8.8", client=client, sleep_fn=lambda _: None)
        assert site["robots_txt_found"] is False
        assert site["sitemap_count"] == 1
        assert site["discovered_url_count"] == 1
        assert site["sample_urls"] == ["https://8.8.8.8/only-page"]
        assert site["latest_lastmod"] == "2026-11-12"
        assert site["language"] == "ja"

    # Also test extract_page_metadata directly for share-link filtering
    meta = extract_page_metadata(
        """
        <html lang="en">
          <head><title>Hi</title></head>
          <body>
            <a href="https://twitter.com/share?url=https://x.io">Share</a>
            <a href="https://www.linkedin.com/shareArticle?mini=true">Share LI</a>
            <a href="https://github.com/features">Features</a>
            <a href="https://github.com/stripe">Stripe GH</a>
          </body>
        </html>
        """,
        "https://stripe.com/",
    )
    assert meta["social_links"]["github"] == ["https://github.com/stripe"]
    assert meta["social_links"]["x_twitter"] == []
    assert meta["social_links"]["linkedin"] == []
