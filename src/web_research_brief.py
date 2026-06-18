"""Generate a safe web research query plan or brief for the MVP.

Default mode is offline query planning. Online mode intentionally avoids crawling and uses:

- a public quote endpoint when available,
- lightweight search-result snippets as leads,
- no raw page storage,
- conservative labels when network data cannot be verified.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import provider_adapters
from provider_adapters import QuoteSnapshot, fetch_market_snapshot, provider_safety_profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"

USER_AGENT = "ai-equity-research-mvp/0.1 (research brief generator)"
TIMEOUT_SECONDS = 12
MAX_RESPONSE_BYTES = 2_000_000
SEARCH_ERRORS: list[str] = []


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    query: str


@dataclass(frozen=True)
class EvidenceCard:
    claim: str
    source_url: str
    publisher: str
    source_tier: str
    fact_date: str
    retrieved_at: str
    label: str
    why_it_matters: str
    could_change: str
    confidence: str
    query_or_gap: str
    metric: str = ""
    value: str = ""
    unit: str = ""
    period: str = ""
    gate_status: str = "accepted"
    gate_reason: str = ""


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "web-research"


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def set_timeout_seconds(value: int) -> None:
    global TIMEOUT_SECONDS
    TIMEOUT_SECONDS = max(1, int(value))
    provider_adapters.set_timeout_seconds(TIMEOUT_SECONDS)


def set_market_provider(value: str | None) -> None:
    provider_adapters.set_market_provider(value)


def configured_llm_provider() -> bool:
    return bool(os.environ.get("AI_EQUITY_WEB_LLM_ENDPOINT") and os.environ.get("AI_EQUITY_WEB_LLM_API_KEY"))


def http_get(url: str, accept: str = "*/*") -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        payload = response.read(MAX_RESPONSE_BYTES + 1)[:MAX_RESPONSE_BYTES]
        return payload.decode(charset, errors="replace")


def normalize_ddg_url(url: str) -> str:
    url = html.unescape(url)
    if "uddg=" in url:
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        uddg = query.get("uddg")
        if uddg:
            return uddg[0]
    return url


def search_duckduckgo(query: str, limit: int = 5) -> list[SearchResult]:
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    try:
        page = http_get(url, accept="text/html")
    except Exception as exc:  # noqa: BLE001
        SEARCH_ERRORS.append(f"{query}: {type(exc).__name__}: {exc}")
        return []

    blocks = re.split(r'<div class="result', page)[1:]
    if not blocks:
        marker = clean_text(page[:180])
        SEARCH_ERRORS.append(f"{query}: no parseable DuckDuckGo results; response_start={marker}")
        return []
    results: list[SearchResult] = []
    for block in blocks:
        title_match = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.S)
        if not title_match:
            continue
        snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>|class="result__snippet"[^>]*>(.*?)</div>', block, flags=re.S)
        raw_snippet = ""
        if snippet_match:
            raw_snippet = snippet_match.group(1) or snippet_match.group(2) or ""
        result = SearchResult(
            title=clean_text(title_match.group(2)),
            url=normalize_ddg_url(title_match.group(1)),
            snippet=clean_text(raw_snippet),
            query=query,
        )
        if result.title and result.url:
            results.append(result)
        if len(results) >= limit:
            break
    if not results:
        SEARCH_ERRORS.append(f"{query}: result blocks found but no parseable titles")
    return results


def result_score(result: SearchResult, company: str) -> int:
    text = f"{result.title} {result.url} {result.snippet}".lower()
    score = 0
    priority_tokens = [
        "investor",
        "ir.",
        "sse.com.cn",
        "szse.cn",
        "cninfo.com.cn",
        "sec.gov",
        "hkexnews",
        "announcement",
        "annual report",
        "earnings",
        "results",
        "reuters",
        "yahoo finance",
        "marketwatch",
    ]
    for token in priority_tokens:
        if token in text:
            score += 3
    for token in ["forum", "reddit", "stocktwits", "rumor", "blog"]:
        if token in text:
            score -= 4
    if company and company.lower() in text:
        score += 2
    return score


def dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    deduped: list[SearchResult] = []
    for result in results:
        key = urllib.parse.urlparse(result.url).netloc.lower() + urllib.parse.urlparse(result.url).path.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def result_domain(result: SearchResult) -> str:
    return urllib.parse.urlparse(result.url).netloc.lower().removeprefix("www.")


def url_domain(url: str) -> str:
    if url in {"not_found", "n/a", "none", ""}:
        return ""
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")


def domain_matches(domain: str, suffixes: set[str]) -> bool:
    return any(domain == suffix or domain.endswith(f".{suffix}") for suffix in suffixes)


def source_tier(result: SearchResult, market: str | None) -> str:
    domain = result_domain(result)
    market_key = (market or "").lower()
    blocked = {
        "reddit.com",
        "stocktwits.com",
        "x.com",
        "twitter.com",
        "facebook.com",
        "youtube.com",
        "medium.com",
        "seekingalpha.com",
    }
    if domain_matches(domain, blocked):
        return "rejected"

    if market_key in {"cn", "china", "a-share", "ashare"}:
        official = {"cninfo.com.cn", "sse.com.cn", "szse.cn", "bse.cn"}
        secondary = {"eastmoney.com", "finance.sina.com.cn", "sina.com.cn", "sinajs.cn"}
        if domain_matches(domain, official):
            return "official"
        if domain_matches(domain, secondary):
            return "secondary_market_data"
        return "rejected"

    if market_key in {"hk", "hong kong"}:
        official = {"hkexnews.hk", "hkex.com.hk"}
        secondary = {"finance.yahoo.com", "aastocks.com", "investing.com"}
        if domain_matches(domain, official):
            return "official"
        if domain_matches(domain, secondary):
            return "secondary_market_data"
        return "rejected"

    if market_key in {"us", "usa", "nyse", "nasdaq", "america"}:
        official = {"sec.gov", "data.sec.gov", "nasdaq.com", "nyse.com"}
        secondary = {"finance.yahoo.com", "marketwatch.com"}
        news = {"reuters.com", "apnews.com", "bloomberg.com"}
        if domain_matches(domain, official):
            return "official"
        if domain_matches(domain, secondary):
            return "secondary_market_data"
        if domain_matches(domain, news):
            return "news_lead"
        return "rejected"

    return "unclassified"


COMPANY_SUFFIXES = {
    "inc",
    "inc.",
    "corp",
    "corp.",
    "corporation",
    "company",
    "co",
    "co.",
    "ltd",
    "ltd.",
    "limited",
    "plc",
    "group",
    "holdings",
    "holding",
    "class",
}


def company_domain_tokens(company: str | None) -> set[str]:
    if not company:
        return set()
    tokens = {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+", company)
        if len(token) >= 4 and token.lower() not in COMPANY_SUFFIXES
    }
    return tokens


def is_likely_company_ir_url(url: str, company: str | None) -> bool:
    domain = url_domain(url)
    path = urllib.parse.urlparse(url).path.lower()
    if not domain:
        return False
    company_tokens = company_domain_tokens(company)
    domain_without_suffix = domain.split(".")[0]
    domain_parts = set(domain.split("."))
    has_company_token = bool(company_tokens & domain_parts) or domain_without_suffix in company_tokens
    has_ir_path = any(token in path for token in ["investor", "ir", "newsroom", "press", "financial", "quarter", "annual"])
    return has_company_token and (domain.startswith("investor.") or has_ir_path)


def source_tier_for_url(url: str, market: str | None, company: str | None = None) -> str:
    domain = url_domain(url)
    if not domain:
        return "data_gap"
    if is_likely_company_ir_url(url, company):
        return "official_company_ir"
    return source_tier(SearchResult(title="", url=url, snippet="", query=""), market)


def card_source_gate(source_url: str, label: str, market: str | None, company: str | None = None) -> tuple[str, str, str]:
    clean_label = label.strip().lower()
    clean_url = source_url.strip()
    if clean_label == "data_gap" or clean_url in {"not_found", "n/a", "none", ""}:
        return "data_gap", "data_gap", "No public source returned for this evidence gap."
    parsed = urllib.parse.urlparse(clean_url)
    if parsed.scheme not in {"http", "https"}:
        return "rejected", "rejected", "Source URL is not an http(s) public URL."
    tier = source_tier_for_url(clean_url, market, company)
    if tier == "rejected":
        return "rejected", tier, f"Source domain {url_domain(clean_url)} is outside the market whitelist."
    if tier == "unclassified":
        return "watch", tier, f"Source domain {url_domain(clean_url)} is unclassified; verify before using as hard evidence."
    return "accepted", tier, "Source domain passed market whitelist."


def accepted_results(results: list[SearchResult], market: str | None) -> list[SearchResult]:
    return [item for item in results if source_tier(item, market) != "rejected"]


def allowed_source_names(market: str | None) -> list[str]:
    return [source for source, _reason in market_source_whitelist(market)]


def public_source_targets(market: str | None) -> dict[str, list[str]]:
    market_key = (market or "").lower()
    if market_key in {"us", "usa", "nyse", "nasdaq", "america"}:
        return {
            "market_snapshot": ["nasdaq.com", "finance.yahoo.com", "marketwatch.com"],
            "official_results": ["sec.gov", "company investor relations"],
            "valuation_expectations": ["finance.yahoo.com", "marketwatch.com", "reuters.com", "company investor relations"],
            "recent_events": ["company investor relations", "sec.gov", "reuters.com", "apnews.com"],
        }
    if market_key in {"cn", "china", "a-share", "ashare"}:
        return {
            "market_snapshot": ["eastmoney.com", "sina.com.cn", "akshare-style market data if available"],
            "official_results": ["cninfo.com.cn", "sse.com.cn", "szse.cn", "bse.cn"],
            "valuation_expectations": ["eastmoney.com", "sina.com.cn", "user-provided Wind/Bloomberg export"],
            "recent_events": ["cninfo.com.cn", "sse.com.cn", "szse.cn", "company investor relations"],
        }
    return {
        "market_snapshot": ["reputable market data provider"],
        "official_results": ["company investor relations", "local exchange", "local regulator"],
        "valuation_expectations": ["reputable market data provider", "major financial news"],
        "recent_events": ["company investor relations", "major financial news"],
    }


def default_gap_tasks() -> list[str]:
    return [
        "current price and market cap",
        "latest official financial results",
        "recent material news or guidance",
        "consensus or peer valuation context",
        "disconfirming evidence that could change rating or confidence",
    ]


def normalize_evidence_tasks(tasks: list[str]) -> list[str]:
    normalized: list[str] = []
    for task in tasks:
        for part in re.split(r";\s*", str(task)):
            clean = part.strip()
            clean = re.sub(r"^(?:and|or)\s+", "", clean, flags=re.IGNORECASE)
            if clean:
                normalized.append(clean)
    return normalized


def combined_gap_tasks(tasks: list[str]) -> list[str]:
    combined: list[str] = []
    for task in [*default_gap_tasks(), *normalize_evidence_tasks(tasks)]:
        clean = task.strip()
        key = clean.lower()
        if clean and key not in {item.lower() for item in combined}:
            combined.append(clean)
    return combined


def build_queries(company: str, ticker: str, market: str | None) -> list[str]:
    base = f"{ticker} {company}".strip()
    if market and market.lower() in {"cn", "china", "a-share", "ashare"}:
        queries = [
            f"site:cninfo.com.cn {ticker} {company} annual report latest announcement",
            f"site:sse.com.cn {ticker} {company} announcement latest results",
            f"site:szse.cn {ticker} {company} announcement latest results",
            f"{ticker} {company} investor relations latest results",
            f"{ticker} {company} share price market cap",
            f"{ticker} {company} consensus estimate valuation PE",
        ]
    elif market and market.lower() in {"hk", "hong kong"}:
        queries = [
            f"site:hkexnews.hk {ticker} {company} announcement results",
            f"site:hkexnews.hk {ticker} {company} annual report",
            f"{ticker} {company} investor relations latest results",
            f"{ticker} {company} share price market cap HKD",
            f"{company} valuation PE EV EBITDA Hong Kong",
        ]
    elif market and market.lower() in {"us", "usa", "nyse", "nasdaq", "america"}:
        queries = [
            f"site:sec.gov {ticker} {company} 10-K 10-Q 8-K",
            f"{ticker} {company} investor relations latest results",
            f"{ticker} {company} current price market cap",
            f"{ticker} {company} guidance latest",
            f"{ticker} {company} valuation PE PFCF EV EBITDA",
            f"{ticker} {company} latest news material event",
        ]
    else:
        queries = [
            f"{base} official filings latest results",
            f"{base} investor relations latest results",
            f"{base} current price market cap",
            f"{base} guidance latest",
            f"{base} latest news material event",
            f"{base} valuation PE PFCF EV EBITDA",
        ]
    return [query for query in queries if query.strip()]


def build_gap_queries(company: str, ticker: str, market: str | None, evidence_tasks: list[str]) -> list[str]:
    base = f"{ticker} {company}".strip()
    market_key = (market or "").lower()
    queries: list[str] = []
    task_text = " ".join(evidence_tasks).lower()

    if any(token in task_text for token in ["price", "quote", "market cap", "valuation", "reconcile"]):
        if market_key in {"cn", "china", "a-share", "ashare"}:
            queries.extend([
                f"{base} current share price market cap",
                f"{base} PFCF PE valuation latest",
            ])
        elif market_key in {"us", "usa", "nyse", "nasdaq", "america"}:
            queries.extend([
                f"{base} current price market cap",
                f"{base} valuation PE PFCF EV EBITDA",
            ])
        else:
            queries.extend([
                f"{base} current price market cap",
                f"{base} valuation PE PFCF",
            ])

    if any(token in task_text for token in ["annual", "filing", "official", "fiscal year", "share count", "fcf definition", "reconcile"]):
        if market_key in {"cn", "china", "a-share", "ashare"}:
            queries.extend([
                f"site:cninfo.com.cn {ticker} {company} annual report free cash flow shares",
                f"site:sse.com.cn {ticker} {company} annual report announcement",
                f"site:cninfo.com.cn {ticker} {company} cash flow statement shares outstanding",
            ])
        elif market_key in {"hk", "hong kong"}:
            queries.extend([
                f"site:hkexnews.hk {ticker} {company} annual report cash flow shares",
            ])
        elif market_key in {"us", "usa", "nyse", "nasdaq", "america"}:
            queries.extend([
                f"site:sec.gov {ticker} {company} 10-K cash flow shares outstanding",
            ])
        else:
            queries.append(f"{base} annual report cash flow shares outstanding")

    if any(token in task_text for token in ["consensus", "target", "estimate", "peer"]):
        queries.extend([
            f"{base} consensus estimate target price",
            f"{base} peer valuation PE PFCF EV EBITDA",
        ])

    if any(token in task_text for token in ["news", "event", "risk", "guidance"]):
        queries.extend([
            f"{base} latest results guidance announcement",
            f"{base} latest material news risk",
        ])

    if not queries:
        queries = build_queries(company, ticker, market)[:4]

    seen: set[str] = set()
    deduped: list[str] = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            deduped.append(query)
    return deduped[:8]


def market_source_whitelist(market: str | None) -> list[tuple[str, str]]:
    market_key = (market or "").lower()
    if market_key in {"cn", "china", "a-share", "ashare"}:
        return [
            ("cninfo.com.cn", "Official disclosure hub for CN listed-company announcements"),
            ("sse.com.cn", "Shanghai Stock Exchange announcements and supervision"),
            ("szse.cn", "Shenzhen Stock Exchange announcements and supervision"),
            ("bse.cn", "Beijing Stock Exchange announcements and supervision"),
            ("company IR", "Company investor relations and official releases"),
            ("eastmoney/sina/akshare", "Market quote and valuation helper only; label as secondary"),
        ]
    if market_key in {"hk", "hong kong"}:
        return [
            ("hkexnews.hk", "Official HKEX announcements and filings"),
            ("hkex.com.hk", "Exchange information and market structure"),
            ("company IR", "Company investor relations and official releases"),
            ("reputable market data provider", "Quote and market cap helper only"),
        ]
    if market_key in {"us", "usa", "nyse", "nasdaq", "america"}:
        return [
            ("sec.gov / data.sec.gov", "Official SEC filings and XBRL APIs"),
            ("company IR", "Company earnings releases, presentations, transcripts where available"),
            ("exchange website", "Listing and market notices where relevant"),
            ("reputable market data provider", "Quote and market cap helper only"),
            ("established financial news", "Material event leads only"),
        ]
    return [
        ("company IR", "Company official releases"),
        ("local exchange / regulator", "Official filings and announcements"),
        ("reputable market data provider", "Quote and market cap helper only"),
        ("established financial news", "Material event leads only"),
    ]


def query_intent(query: str) -> str:
    lower = query.lower()
    if any(token in lower for token in ["current price", "share price", "market cap"]):
        return "Update market snapshot and valuation bridge."
    if any(token in lower for token in ["investor relations", "latest results", "earnings", "results"]):
        return "Find latest official financial update."
    if any(token in lower for token in ["guidance"]):
        return "Check guidance that could change thesis probability."
    if any(token in lower for token in ["news", "material event", "announcement", "annual report"]):
        return "Identify material recent events, not general noise."
    if any(token in lower for token in ["valuation", "pe", "pfcf", "ev ebitda", "consensus estimate"]):
        return "Update valuation context and market expectations."
    return "Support web research brief only if source quality is acceptable."


def render_query_plan(company: str, ticker: str, market: str | None, evidence_tasks: list[str] | None = None) -> str:
    generated_at = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    tasks = combined_gap_tasks(evidence_tasks or [])
    queries = build_gap_queries(company, ticker, market, tasks) if tasks else build_queries(company, ticker, market)
    lines = [
        "# Web Research Search Log",
        "",
        f"Company: {company}",
        f"Ticker: {ticker}",
        f"Market: {market or ''}",
        f"Generated at: {generated_at}",
        "Mode: offline diagnostic; no network request made",
        "Use: audit trail only; not memo input",
        "",
        "## Evidence Gaps",
        "",
    ]
    if tasks:
        lines.extend(f"- {task}" for task in tasks)
    else:
        lines.append("- Generic market refresh; no specific evidence gap supplied.")
    lines.extend(
        [
            "",
            "## Allowed Sources",
            "",
            *[f"- {source}: {reason}" for source, reason in market_source_whitelist(market)],
            "",
            "## Candidate Queries",
            "",
        ]
    )
    for query in queries:
        lines.append(f"- {query}")
    return "\n".join(lines) + "\n"


def collect_search_results(
    company: str,
    ticker: str,
    market: str | None,
    per_query: int,
    max_queries: int | None = None,
) -> list[SearchResult]:
    SEARCH_ERRORS.clear()
    all_results: list[SearchResult] = []
    queries = build_queries(company, ticker, market)
    if max_queries is not None:
        queries = queries[:max(0, max_queries)]
    for query in queries:
        all_results.extend(search_duckduckgo(query, limit=per_query))
    return sorted(dedupe_results(all_results), key=lambda item: result_score(item, company), reverse=True)


def privacy_safe_llm_payload(company: str, ticker: str, market: str | None, evidence_tasks: list[str]) -> dict[str, object]:
    tasks = combined_gap_tasks(evidence_tasks)
    return {
        "company": company,
        "ticker": ticker,
        "market": market or "",
        "evidence_gaps": tasks[:8],
        "allowed_sources": allowed_source_names(market),
        "source_targets_by_gap": public_source_targets(market),
        "strict_gap_contract": [
            "Return at least one evidence card for each evidence gap whenever public data is available.",
            "For current price and market cap, prioritize market data pages such as Nasdaq, Yahoo Finance, MarketWatch, or company IR stock-price pages for US stocks.",
            "For CN A-share stocks, use only cninfo.com.cn, sse.com.cn, szse.cn, bse.cn, eastmoney.com, finance.sina.com.cn, sina.com.cn, or company official IR pages.",
            "For CN market snapshot, prefer eastmoney.com or finance.sina.com.cn/sina.com.cn. Do not use generic AI answer pages, forums, OCR snippets, or zh.app-style generated pages.",
            "For market data cards, include concrete metric/value/unit/period fields, e.g. metric='current_price', value='195.64', unit='USD', period='latest available quote'.",
            "For market cap cards, include metric='market_cap', value and unit such as 'USD bn'.",
            "For official results cards, include concrete revenue/EPS/margin values when available.",
            "If a gap cannot be filled, return a data_gap card with label=data_gap, source_url=not_found, confidence=Low, and explain why.",
            "Do not replace market snapshot with official filing data; market snapshot needs quote/market-cap context.",
            "Do not invent figures. If exact current quote is unavailable, return the best dated market snapshot and label it stale or delayed.",
            "If the only available text is garbled, OCR-fragmented, unsourced, or not from the allowed source list, return data_gap instead of an evidence card.",
        ],
        "forbidden_inputs": [
            "local file contents",
            "local file paths",
            "private user notes",
            "uploaded report text",
            "memo draft text",
            "portfolio holdings",
        ],
        "output_schema": {
            "evidence_cards": [
                {
                    "claim": "concise factual claim",
                    "source_url": "public URL",
                    "publisher": "publisher or source name",
                    "source_tier": "official | secondary_market_data | news_lead | rejected",
                    "fact_date": "YYYY-MM-DD or unknown",
                    "label": "fact | estimate | opinion | market_data | search_lead",
                    "metric": "current_price | market_cap | revenue | eps | consensus_pe | target_price | other",
                    "value": "numeric or concise value when available",
                    "unit": "USD | USD bn | shares | x | % | other",
                    "period": "latest quote | FY2026 Q2 | trailing twelve months | other",
                    "why_it_matters": "rating / thesis / valuation / trigger impact",
                    "could_change": "specific memo field this could change",
                    "confidence": "High | Medium | Low",
                    "query_or_gap": "gap this card addresses",
                }
            ],
            "noise_removed": ["ignored items and reason"],
        },
    }


def llm_system_prompt() -> str:
    return (
        "You are a public web research assistant for a local equity research MVP. "
        "Use only public information. Do not ask for or infer private files. "
        "Return evidence cards only; do not give Buy/Sell ratings or investment advice. "
        "You must address every evidence gap in the request. For any gap you cannot fill, "
        "return a data_gap evidence card with source_url='not_found' and explain the missing data. "
        "For current price and market cap, prioritize market data sources and do not substitute SEC filing data. "
        "Use direct public URLs, not markdown links. Source tiers will be independently checked by domain whitelist. "
        "Include concrete metric, value, unit, and period fields whenever the evidence is quantitative. "
        "Every card must include a public source URL, source tier, fact date if available, "
        "why it matters, and what memo field it could change. Prefer official filings, "
        "company IR, exchange/regulator sources, reputable market data, and major news. "
        "Reject social/forum/commentary, generic AI-generated pages, OCR fragments, garbled snippets, and non-whitelisted domains. "
        "Return valid JSON only."
    )


def extract_json_object(text: str) -> dict[str, object]:
    try:
        loaded = json.loads(text)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            loaded = json.loads(text[start : end + 1])
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def llm_chat_completion(payload: dict[str, object]) -> dict[str, object]:
    endpoint = os.environ.get("AI_EQUITY_WEB_LLM_ENDPOINT", "").strip()
    api_key = os.environ.get("AI_EQUITY_WEB_LLM_API_KEY", "").strip()
    model = os.environ.get("AI_EQUITY_WEB_LLM_MODEL", "gpt-4o-mini").strip()
    enable_web_plugin = os.environ.get("AI_EQUITY_WEB_LLM_WEB_PLUGIN", "").strip().lower() in {"1", "true", "yes", "on"}
    web_engine = os.environ.get("AI_EQUITY_WEB_LLM_WEB_ENGINE", "").strip()
    web_max_results = os.environ.get("AI_EQUITY_WEB_LLM_WEB_MAX_RESULTS", "5").strip()
    if not endpoint or not api_key:
        raise RuntimeError("AI_EQUITY_WEB_LLM_ENDPOINT and AI_EQUITY_WEB_LLM_API_KEY are required for llm provider.")

    request_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": llm_system_prompt()},
            {
                "role": "user",
                "content": (
                    "Collect public evidence cards for this equity research gap request. "
                    "Return JSON only.\n\n"
                    + json.dumps(payload, ensure_ascii=False, indent=2)
                ),
            },
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    if enable_web_plugin:
        plugin: dict[str, object] = {"id": "web"}
        if web_engine:
            plugin["engine"] = web_engine
        try:
            plugin["max_results"] = max(1, min(10, int(web_max_results)))
        except ValueError:
            plugin["max_results"] = 5
        request_payload["plugins"] = [plugin]
    data = json.dumps(request_payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    referer = os.environ.get("AI_EQUITY_WEB_LLM_HTTP_REFERER", "").strip()
    app_title = os.environ.get("AI_EQUITY_WEB_LLM_APP_TITLE", "").strip()
    if referer:
        headers["HTTP-Referer"] = referer
    if app_title:
        headers["X-Title"] = app_title
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers=headers,
        method="POST",
    )
    last_error: Exception | None = None
    raw = ""
    for _attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)[:MAX_RESPONSE_BYTES].decode("utf-8", errors="replace")
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    if not raw and last_error:
        raise last_error
    response_json = json.loads(raw)
    content = ""
    choices = response_json.get("choices", [])
    if choices and isinstance(choices, list):
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = message.get("content", "") if isinstance(message, dict) else ""
    if not content:
        content = raw
    return extract_json_object(content)


def normalize_evidence_card(raw: object, retrieved_at: str, market: str | None, company: str | None = None) -> EvidenceCard | None:
    if not isinstance(raw, dict):
        return None
    claim = str(raw.get("claim") or "").strip()
    source_url = str(raw.get("source_url") or "").strip()
    markdown_url = re.search(r"\((https?://[^)]+)\)", source_url)
    if markdown_url:
        source_url = markdown_url.group(1)
    label = str(raw.get("label") or "fact").strip()
    if not claim or not source_url:
        return None
    gate_status, tier, gate_reason = card_source_gate(source_url, label, market, company)
    model_tier = str(raw.get("source_tier") or "unclassified").strip()
    if model_tier and model_tier != tier and gate_status == "accepted":
        gate_reason = f"{gate_reason} Model tier '{model_tier}' corrected to '{tier}'."
    return EvidenceCard(
        claim=claim,
        source_url=source_url,
        publisher=str(raw.get("publisher") or "").strip(),
        source_tier=tier,
        fact_date=str(raw.get("fact_date") or "unknown").strip(),
        retrieved_at=retrieved_at,
        label=label,
        metric=str(raw.get("metric") or "").strip(),
        value=str(raw.get("value") or "").strip(),
        unit=str(raw.get("unit") or "").strip(),
        period=str(raw.get("period") or "").strip(),
        why_it_matters=str(raw.get("why_it_matters") or "").strip(),
        could_change=str(raw.get("could_change") or "").strip(),
        confidence=str(raw.get("confidence") or "Low").strip(),
        query_or_gap=str(raw.get("query_or_gap") or "").strip(),
        gate_status=gate_status,
        gate_reason=gate_reason,
    )


def collect_llm_evidence_cards(
    company: str,
    ticker: str,
    market: str | None,
    evidence_tasks: list[str],
) -> tuple[list[EvidenceCard], list[str]]:
    retrieved_at = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    payload = privacy_safe_llm_payload(company, ticker, market, normalize_evidence_tasks(evidence_tasks))
    try:
        result = llm_chat_completion(payload)
    except Exception as exc:  # noqa: BLE001
        return [], [f"llm provider failed: {type(exc).__name__}: {exc}"]
    raw_cards = result.get("evidence_cards", [])
    cards = [card for item in raw_cards if (card := normalize_evidence_card(item, retrieved_at, market, company))]
    diagnostics: list[str] = []
    if not cards:
        diagnostics.append("llm provider returned no valid evidence cards")
    noise = result.get("noise_removed", [])
    if isinstance(noise, list) and noise:
        diagnostics.append("noise_removed=" + "; ".join(str(item)[:120] for item in noise[:3]))
    return cards, diagnostics


def format_money(value: float | None, currency: str | None) -> str:
    if value is None:
        return ""
    prefix = f"{currency} " if currency else ""
    if abs(value) >= 1_000_000_000:
        return f"{prefix}{value / 1_000_000_000:.2f}bn"
    if abs(value) >= 1_000_000:
        return f"{prefix}{value / 1_000_000:.2f}mn"
    return f"{prefix}{value:.2f}"


def quote_provider_name(quote: QuoteSnapshot) -> str:
    if "query1.finance.yahoo.com" in quote.source:
        return "yahoo_quote_endpoint"
    if "query2.finance.yahoo.com" in quote.source:
        return "yahoo_chart_endpoint"
    if quote.source in {"manual", "sec", "akshare_stub"}:
        return quote.source
    if quote.source.startswith("yfinance:"):
        return "yfinance_optional"
    if "stooq.com" in quote.source:
        return "stooq_quote_csv"
    if "hq.sinajs.cn" in quote.source:
        return "sina_quote_endpoint"
    return "manual" if quote.source == "" else quote.source


def render_result(result: SearchResult, market: str | None, could_change: str) -> list[str]:
    fact = result.title
    if result.snippet:
        fact = f"{fact} - {result.snippet}"
    return [
        f"- Fact: {fact}",
        f"  Source: {result.url}",
        f"  Source tier: {source_tier(result, market)}",
        "  Fact date: search-result date not verified",
        "  Label: search result lead, verify source page before using as hard evidence",
        f"  Why it matters: {could_change}",
        f"  Could change: {could_change}",
        f"  Query: {result.query}",
    ]


def render_evidence_card(card: EvidenceCard) -> list[str]:
    lines = [
        f"- Fact: {card.claim}",
        f"  Source: {card.source_url}",
        f"  Publisher: {card.publisher}",
        f"  Source tier: {card.source_tier}",
        f"  Fact date: {card.fact_date}",
        f"  Retrieved at: {card.retrieved_at}",
        f"  Label: {card.label}",
    ]
    if card.metric or card.value or card.unit or card.period:
        lines.extend(
            [
                f"  Metric: {card.metric}",
                f"  Value: {card.value}",
                f"  Unit: {card.unit}",
                f"  Period: {card.period}",
            ]
        )
    lines.extend(
        [
        f"  Why it matters: {card.why_it_matters}",
        f"  Could change: {card.could_change}",
        f"  Confidence: {card.confidence}",
        f"  Gap: {card.query_or_gap}",
        f"  Source gate: {card.gate_status} - {card.gate_reason}",
        ]
    )
    return lines


def brief_mode_label(
    quote: QuoteSnapshot,
    accepted: list[SearchResult],
    event_results: list[SearchResult],
    valuation_results: list[SearchResult],
) -> str:
    if quote.price is not None and not accepted and not event_results and not valuation_results:
        return "quote_only_fallback"
    if quote.price is not None and accepted and not event_results and not valuation_results:
        return "market_context_only"
    if event_results or valuation_results:
        return "multi_source_web_brief"
    if accepted:
        return "search_leads_only"
    return "no_usable_web_evidence"


def recovery_tasks(company: str, ticker: str, market: str | None) -> list[str]:
    market_key = (market or "").lower()
    if market_key in {"cn", "china", "a-share", "ashare"}:
        return [
            f"Official filings: search cninfo.com.cn and sse.com.cn directly for {ticker} announcements, annual report, and results releases.",
            f"Valuation context: use Eastmoney or Sina Finance only as secondary sources for peer multiples, market cap, and trading context for {ticker}.",
            "Expectation gap: add one concrete consensus revision, peer multiple range, or guidance change before changing rating confidence.",
        ]
    if market_key in {"us", "usa", "nyse", "nasdaq", "america"}:
        return [
            f"Official filings: pull the latest 10-K, 10-Q, and 8-K from sec.gov for {company} ({ticker}).",
            "Valuation context: use Yahoo Finance or MarketWatch only as secondary sources for peer multiples and current trading context.",
            "Expectation gap: add one concrete consensus, guidance, or peer-valuation datapoint before changing rating confidence.",
        ]
    return [
        "Official filings: collect the latest company disclosures from the primary exchange or regulator site.",
        "Valuation context: use secondary market-data pages only for peer multiples and trading context.",
        "Expectation gap: add one concrete consensus, guidance, or peer-valuation datapoint before changing rating confidence.",
    ]


def render_brief(
    company: str,
    ticker: str,
    market: str | None,
    quote: QuoteSnapshot,
    results: list[SearchResult],
    network_enabled: bool,
) -> str:
    retrieved_at = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    accepted = accepted_results(results, market)
    rejected_count = len(results) - len(accepted)
    market_results = [item for item in accepted if any(token in item.query.lower() for token in ["price", "share price", "market cap"])]
    event_results = [item for item in accepted if any(token in item.query.lower() for token in ["latest", "news", "announcement", "results", "annual report"])]
    valuation_results = [item for item in accepted if any(token in item.query.lower() for token in ["valuation", "pe", "pfcf", "ev ebitda", "consensus estimate"])]
    safety = provider_safety_profile(quote_provider_name(quote))
    brief_mode = brief_mode_label(quote, accepted, event_results, valuation_results)

    lines = [
        "# Web Research Brief",
        "",
        f"Company: {company}",
        f"Ticker: {ticker}",
        f"Market: {market or ''}",
        f"Retrieved at: {retrieved_at}",
        "Search scope: current price, market cap, latest results, recent events, valuation context",
        "",
        "## Market Snapshot",
        "",
    ]
    if quote.price is not None:
        lines.extend(
            [
                f"- Current price: {format_money(quote.price, quote.currency)}",
                f"- Market cap: {format_money(quote.market_cap, quote.currency)}",
                f"- Source: {quote.source}",
                f"- Fact date: {quote.quote_time or 'quote endpoint date not available'}",
                "- Label: market data provider quote",
            ]
        )
    else:
        lines.extend(
            [
                "- Current price:",
                "- Market cap:",
                f"- Source: {quote.source}",
                "- Fact date:",
                f"- Label: quote unavailable; status={quote.status}",
            ]
        )
    if market_results:
        lines.append("- Search leads:")
        for result in market_results[:3]:
            lines.append(f"  - {result.title} | {source_tier(result, market)} | {result.url}")

    lines.extend(["", "## Recent Events", ""])
    if event_results:
        for result in event_results[:5]:
            lines.extend(render_result(result, market, "thesis condition probability or rating-change trigger"))
    else:
        lines.append("- Fact:")
        lines.append("  Source:")
        lines.append("  Fact date:")
        lines.append("  Why it matters:")
        lines.append("  Could change:")

    lines.extend(["", "## Valuation / Estimate Updates", ""])
    if valuation_results:
        for result in valuation_results[:4]:
            lines.extend(render_result(result, market, "valuation bridge or market expectation"))
    else:
        lines.append("- Fact:")
        lines.append("  Source:")
        lines.append("  Fact date:")
        lines.append("  Why it matters:")
        lines.append("  Could change:")

    lines.extend(["", "## Audit", ""])
    lines.append(f"- Brief mode: {brief_mode}")
    lines.append(f"- Provider safety: {safety.name} / {safety.status}; private_file_read={safety.may_read_private_files}; user_content_upload={safety.may_upload_user_content}")
    lines.append(f"- Source filter: accepted={len(accepted)}; rejected={rejected_count}; raw_pages_stored=false; network_enabled={network_enabled}")
    if SEARCH_ERRORS:
        lines.append(f"- Search diagnostics: failures={len(SEARCH_ERRORS)}; first_error={SEARCH_ERRORS[0]}")
    if brief_mode in {"quote_only_fallback", "market_context_only", "no_usable_web_evidence"}:
        lines.extend(["", "## Recovery Tasks", ""])
        for task in recovery_tasks(company, ticker, market):
            lines.append(f"- {task}")
    return "\n".join(lines) + "\n"


def render_llm_brief(
    company: str,
    ticker: str,
    market: str | None,
    cards: list[EvidenceCard],
    diagnostics: list[str],
    evidence_tasks: list[str],
) -> str:
    retrieved_at = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    accepted_cards = [card for card in cards if card.gate_status in {"accepted", "watch"}]
    def gap_key(card: EvidenceCard) -> str:
        text = " ".join([card.query_or_gap, card.metric, card.could_change, card.claim]).lower()
        if any(token in text for token in ["current_price", "current price", "market cap", "quote"]):
            return "market_snapshot"
        if any(token in text for token in ["consensus", "valuation", "multiple", "target_price", "target price"]):
            return "valuation"
        if any(token in text for token in ["result", "revenue", "eps", "margin", "official"]):
            return "official_results"
        if any(token in text for token in ["news", "event", "guidance"]):
            return "recent_events"
        return (card.query_or_gap or card.metric or card.could_change).strip().lower()

    filled_gaps = {gap_key(card) for card in accepted_cards if gap_key(card)}
    data_gap_cards = [
        card
        for card in cards
        if card.gate_status == "data_gap"
        and gap_key(card) not in filled_gaps
    ]
    rejected_cards = [card for card in cards if card.gate_status == "rejected"]
    market_cards = [
        card
        for card in accepted_cards
        if any(token in f"{card.metric} {card.could_change} {card.query_or_gap}".lower() for token in ["price", "market cap", "valuation", "current_price", "market_cap"])
    ]
    event_cards = [card for card in accepted_cards if any(token in f"{card.could_change} {card.query_or_gap}".lower() for token in ["news", "event", "guidance", "results", "thesis", "trigger"])]
    market_card_keys = {(card.claim, card.source_url, card.metric, card.value) for card in market_cards}
    valuation_cards = [
        card
        for card in accepted_cards
        if any(token in f"{card.could_change} {card.query_or_gap}".lower() for token in ["valuation", "multiple", "consensus", "estimate", "peer"])
        and (card.claim, card.source_url, card.metric, card.value) not in market_card_keys
    ]
    shown_card_keys = {
        (card.claim, card.source_url, card.metric, card.value)
        for card in [*market_cards, *event_cards, *valuation_cards]
    }
    other_cards = [
        card
        for card in accepted_cards
        if (card.claim, card.source_url, card.metric, card.value) not in shown_card_keys
    ]
    lines = [
        "# Web Research Brief",
        "",
        f"Company: {company}",
        f"Ticker: {ticker}",
        f"Market: {market or ''}",
        f"Retrieved at: {retrieved_at}",
        "Search scope: LLM-assisted public evidence-card collection for current research gaps",
        "Provider: llm_web_research",
        "",
        "## Privacy Gate",
        "",
        "- Sent to provider: company, ticker, market, evidence gaps, allowed sources, output schema.",
        "- Not sent to provider: local file contents, local file paths, private notes, uploaded reports, memo drafts, portfolio holdings.",
        "",
        "## Evidence Gaps",
        "",
    ]
    lines.extend(f"- {task}" for task in combined_gap_tasks(evidence_tasks))
    lines.extend(["", "## Market Snapshot", ""])
    if market_cards:
        for card in market_cards[:4]:
            lines.extend(render_evidence_card(card))
    else:
        lines.append("- Current price:")
        lines.append("- Market cap:")
        lines.append("- Source:")
        lines.append("- Label: no valid market snapshot card returned")
    lines.extend(["", "## Recent Events", ""])
    if event_cards:
        for card in event_cards[:6]:
            lines.extend(render_evidence_card(card))
    else:
        lines.append("- Fact:")
        lines.append("  Source:")
        lines.append("  Why it matters:")
        lines.append("  Could change:")
    lines.extend(["", "## Valuation / Estimate Updates", ""])
    if valuation_cards:
        for card in valuation_cards[:6]:
            lines.extend(render_evidence_card(card))
    else:
        lines.append("- Fact:")
        lines.append("  Source:")
        lines.append("  Why it matters:")
        lines.append("  Could change:")
    if other_cards:
        lines.extend(["", "## Other Accepted Evidence", ""])
        for card in other_cards[:6]:
            lines.extend(render_evidence_card(card))
    lines.extend(["", "## Audit", ""])
    lines.append("- Provider safety: llm_web_research / limited; private_file_read=false; user_content_upload=false")
    lines.append(f"- Source filter: evidence_cards={len(cards)}; accepted_or_watch={len(accepted_cards)}; data_gap={len(data_gap_cards)}; rejected={len(rejected_cards)}; raw_pages_stored=false; network_enabled=true")
    if data_gap_cards:
        lines.append("- Data gaps reported by provider:")
        for card in data_gap_cards[:5]:
            lines.append(f"  - {card.query_or_gap or card.claim}: {card.gate_reason}")
    if rejected_cards:
        lines.append("- Rejected sources:")
        for card in rejected_cards[:5]:
            lines.append(f"  - {card.source_url}: {card.gate_reason}")
    if diagnostics:
        lines.append(f"- Provider diagnostics: {'; '.join(diagnostics[:3])}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a safe web search log or compact web research brief for the MVP.")
    parser.add_argument("--company", required=True, help="Company name.")
    parser.add_argument("--ticker", required=True, help="Ticker or symbol.")
    parser.add_argument("--market", help="Market hint, e.g. US, CN, HK.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for the output. Defaults to outputs so generated files can be reviewed before entering inputs.")
    parser.add_argument("--output", help="Specific output Markdown path.")
    parser.add_argument("--per-query", type=int, default=4, help="Search results per query.")
    parser.add_argument("--max-queries", type=int, default=3, help="Maximum search queries in online mode. Keep this small for low-cost testing.")
    parser.add_argument("--timeout-seconds", type=int, default=25, help="HTTP timeout per request in online mode.")
    parser.add_argument("--market-provider", choices=("auto", "yahoo", "yfinance"), default="auto", help="Market data provider. yfinance is optional and must already be installed locally.")
    parser.add_argument("--research-provider", choices=("search", "llm", "auto"), default=os.environ.get("AI_EQUITY_WEB_PROVIDER", "search"), help="Online research provider: search=quote plus search leads, llm=privacy-gated evidence cards, auto=llm if configured else search.")
    parser.add_argument("--evidence-task", action="append", default=[], help="Evidence gap to send to the online research provider. Can be repeated.")
    parser.add_argument("--skip-search", action="store_true", help="Online mode: fetch quote only and skip search-result requests.")
    parser.add_argument("--online", action="store_true", help="Generate an online web brief. Default is offline search log.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    suffix = "web-research" if args.online else "web-search-log"
    output_path = Path(args.output).expanduser() if args.output else Path(args.output_dir) / f"{slugify(args.ticker)}-{suffix}.md"
    if not output_path.is_absolute():
        output_path = (PROJECT_ROOT / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not args.online:
        output_path.write_text(render_query_plan(args.company, args.ticker, args.market), encoding="utf-8")
        print(f"Wrote {output_path}")
        print("Mode: offline search log")
        return 0

    set_timeout_seconds(args.timeout_seconds)
    set_market_provider(args.market_provider)
    research_provider = args.research_provider
    if research_provider == "auto":
        research_provider = "llm" if configured_llm_provider() else "search"
    if research_provider == "llm":
        cards, diagnostics = collect_llm_evidence_cards(args.company, args.ticker, args.market, args.evidence_task)
        brief = render_llm_brief(args.company, args.ticker, args.market, cards, diagnostics, args.evidence_task)
        output_path.write_text(brief, encoding="utf-8")
        print(f"Wrote {output_path}")
        print(f"Provider: llm_web_research")
        print(f"Evidence cards: {len(cards)}")
        if diagnostics:
            print(f"Diagnostics: {diagnostics[0]}")
        return 0

    quote = fetch_market_snapshot(args.ticker, args.market)
    results = []
    if not args.skip_search:
        results = collect_search_results(
            args.company,
            args.ticker,
            args.market,
            per_query=args.per_query,
            max_queries=args.max_queries,
        )
    brief = render_brief(args.company, args.ticker, args.market, quote, results, network_enabled=True)
    output_path.write_text(brief, encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"Quote status: {quote.status}")
    print(f"Search leads: {len(results)}")
    if SEARCH_ERRORS:
        print(f"Search failures: {len(SEARCH_ERRORS)}; first={SEARCH_ERRORS[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
