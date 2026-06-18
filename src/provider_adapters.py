"""Safe provider adapters for market context.

This module is intentionally dependency-free. It may call public HTTP endpoints
only when the user explicitly runs an online workflow. It must never read local
private inputs or upload local files to any third-party service.
"""

from __future__ import annotations

import datetime as dt
import csv
import importlib
import io
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol


USER_AGENT = "Mozilla/5.0 (compatible; ai-equity-research-mvp/0.1; +local-research)"
TIMEOUT_SECONDS = 12
MAX_RESPONSE_BYTES = 2_000_000
MARKET_PROVIDER = os.environ.get("AI_EQUITY_MARKET_PROVIDER", "auto").strip().lower()


@dataclass(frozen=True)
class QuoteSnapshot:
    symbol: str
    price: float | None
    currency: str | None
    market_cap: float | None
    quote_time: str | None
    source: str
    status: str


@dataclass(frozen=True)
class FilingLead:
    title: str
    source: str
    fact_date: str | None
    status: str


@dataclass(frozen=True)
class EventLead:
    title: str
    source: str
    fact_date: str | None
    status: str


@dataclass(frozen=True)
class ProviderSafetyProfile:
    name: str
    status: str
    allowed_use: str
    may_read_private_files: bool
    may_upload_user_content: bool
    requires_separate_review: bool
    note: str


class ProviderAdapter(Protocol):
    name: str

    def fetch_market_snapshot(self, ticker: str, market: str | None) -> QuoteSnapshot:
        ...

    def fetch_official_filings(self, ticker: str, market: str | None) -> list[FilingLead]:
        ...

    def fetch_recent_events(self, ticker: str, market: str | None) -> list[EventLead]:
        ...


PROVIDER_SAFETY_REGISTRY: dict[str, ProviderSafetyProfile] = {
    "manual": ProviderSafetyProfile(
        name="manual",
        status="approved",
        allowed_use="user-provided or official-source inputs",
        may_read_private_files=False,
        may_upload_user_content=False,
        requires_separate_review=False,
        note="No external package or network dependency.",
    ),
    "yahoo_quote_endpoint": ProviderSafetyProfile(
        name="yahoo_quote_endpoint",
        status="limited",
        allowed_use="public quote and market snapshot context only",
        may_read_private_files=False,
        may_upload_user_content=False,
        requires_separate_review=False,
        note="Direct public endpoint; not official evidence and not primary for A-share.",
    ),
    "yahoo_chart_endpoint": ProviderSafetyProfile(
        name="yahoo_chart_endpoint",
        status="limited",
        allowed_use="public quote fallback context only",
        may_read_private_files=False,
        may_upload_user_content=False,
        requires_separate_review=False,
        note="Direct public chart endpoint; not official evidence and not primary for A-share.",
    ),
    "stooq_quote_csv": ProviderSafetyProfile(
        name="stooq_quote_csv",
        status="limited",
        allowed_use="public delayed quote fallback for US/HK market context only",
        may_read_private_files=False,
        may_upload_user_content=False,
        requires_separate_review=False,
        note="Direct public CSV endpoint; not official evidence and no local file upload.",
    ),
    "sina_quote_endpoint": ProviderSafetyProfile(
        name="sina_quote_endpoint",
        status="limited",
        allowed_use="public delayed A-share quote context only",
        may_read_private_files=False,
        may_upload_user_content=False,
        requires_separate_review=False,
        note="Direct public Sina quote endpoint; not official filing evidence.",
    ),
    "yfinance_optional": ProviderSafetyProfile(
        name="yfinance_optional",
        status="optional_limited",
        allowed_use="public market data helper only when explicitly enabled by the user",
        may_read_private_files=False,
        may_upload_user_content=False,
        requires_separate_review=False,
        note="Third-party package, not official Yahoo; use only as market context and keep disabled by default.",
    ),
    "sec": ProviderSafetyProfile(
        name="sec",
        status="approved_stub",
        allowed_use="official US filing leads and company facts after implementation",
        may_read_private_files=False,
        may_upload_user_content=False,
        requires_separate_review=False,
        note="Use official SEC/data.sec.gov patterns with identity and rate-limit discipline.",
    ),
    "akshare_stub": ProviderSafetyProfile(
        name="akshare_stub",
        status="blocked_pending_review",
        allowed_use="China market quote context after separate package review",
        may_read_private_files=False,
        may_upload_user_content=False,
        requires_separate_review=True,
        note="Third-party package not installed or executed in MVP.",
    ),
}


def provider_safety_profile(name: str) -> ProviderSafetyProfile:
    return PROVIDER_SAFETY_REGISTRY.get(
        name,
        ProviderSafetyProfile(
            name=name,
            status="unknown_blocked",
            allowed_use="none",
            may_read_private_files=False,
            may_upload_user_content=False,
            requires_separate_review=True,
            note="Unknown provider is blocked until reviewed.",
        ),
    )


def set_timeout_seconds(value: int) -> None:
    global TIMEOUT_SECONDS
    TIMEOUT_SECONDS = max(1, int(value))


def set_market_provider(value: str | None) -> None:
    global MARKET_PROVIDER
    MARKET_PROVIDER = (value or "auto").strip().lower()


def is_cn_market(market: str | None) -> bool:
    return (market or "").strip().lower() in {"cn", "china", "a-share", "ashare", "a\u80a1"}


def is_us_market(market: str | None) -> bool:
    return (market or "").strip().lower() in {"us", "usa", "nyse", "nasdaq", "america"}


def is_hk_market(market: str | None) -> bool:
    return (market or "").strip().lower() in {"hk", "hong kong", "\u6e2f\u80a1"}


def safe_http_get(url: str, accept: str = "*/*") -> str:
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


class ManualProvider:
    name = "manual"

    def __init__(self, reason: str = "manual or official-source input required") -> None:
        self.reason = reason

    def fetch_market_snapshot(self, ticker: str, market: str | None) -> QuoteSnapshot:
        return QuoteSnapshot(ticker, None, None, None, None, self.name, self.reason)

    def fetch_official_filings(self, ticker: str, market: str | None) -> list[FilingLead]:
        return []

    def fetch_recent_events(self, ticker: str, market: str | None) -> list[EventLead]:
        return []


class YahooQuoteProvider:
    """Direct Yahoo quote endpoint adapter.

    Use only as market context. This is not an official filing source and should
    not be the primary source for A-share research.
    """

    name = "yahoo_quote_endpoint"

    def fetch_market_snapshot(self, ticker: str, market: str | None) -> QuoteSnapshot:
        candidates = yahoo_symbol_candidates(ticker, market)
        if not candidates:
            return QuoteSnapshot("", None, None, None, None, self.name, "missing ticker")

        errors: list[str] = []
        for symbol in candidates:
            encoded = urllib.parse.quote(symbol)
            url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={encoded}"
            try:
                payload = json.loads(safe_http_get(url, accept="application/json"))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{symbol}: {exc}")
                chart = fetch_yahoo_chart_quote(symbol)
                if chart.price is not None:
                    return chart
                errors.append(chart.status)
                continue
            results = payload.get("quoteResponse", {}).get("result", [])
            if not results:
                errors.append(f"{symbol}: empty quote")
                continue
            item = results[0]
            price = item.get("regularMarketPrice")
            market_cap = item.get("marketCap")
            quote_time = item.get("regularMarketTime")
            quote_time_text = None
            if isinstance(quote_time, int):
                quote_time_text = dt.datetime.fromtimestamp(quote_time, tz=dt.timezone.utc).isoformat()
            return QuoteSnapshot(
                symbol=symbol,
                price=float(price) if isinstance(price, (int, float)) else None,
                currency=item.get("currency") if isinstance(item.get("currency"), str) else None,
                market_cap=float(market_cap) if isinstance(market_cap, (int, float)) else None,
                quote_time=quote_time_text,
                source=url,
                status="ok; market context only",
            )
        fallback = fetch_stooq_quote(candidates[0], market)
        if fallback.price is not None:
            return fallback
        return QuoteSnapshot(candidates[0], None, None, None, None, self.name, "; ".join([*errors[:3], fallback.status]))

    def fetch_official_filings(self, ticker: str, market: str | None) -> list[FilingLead]:
        return []

    def fetch_recent_events(self, ticker: str, market: str | None) -> list[EventLead]:
        return []


class YFinanceOptionalProvider:
    """Optional yfinance adapter.

    This adapter is disabled unless the user explicitly selects it. It imports
    yfinance lazily and falls back to the direct endpoint adapter if the package
    is not installed or the request fails.
    """

    name = "yfinance_optional"

    def __init__(self, fallback: ProviderAdapter | None = None) -> None:
        self.fallback = fallback or YahooQuoteProvider()

    def fetch_market_snapshot(self, ticker: str, market: str | None) -> QuoteSnapshot:
        candidates = yahoo_symbol_candidates(ticker, market)
        if not candidates:
            return self.fallback.fetch_market_snapshot(ticker, market)
        try:
            yf = importlib.import_module("yfinance")
        except Exception as exc:  # noqa: BLE001
            fallback = self.fallback.fetch_market_snapshot(ticker, market)
            return QuoteSnapshot(
                fallback.symbol,
                fallback.price,
                fallback.currency,
                fallback.market_cap,
                fallback.quote_time,
                fallback.source,
                f"yfinance unavailable: {exc}; fallback={fallback.status}",
            )

        errors: list[str] = []
        for symbol in candidates:
            try:
                item = yf.Ticker(symbol)
                fast_info = getattr(item, "fast_info", {}) or {}
                price = fast_info.get("last_price") or fast_info.get("lastPrice")
                market_cap = fast_info.get("market_cap") or fast_info.get("marketCap")
                currency = fast_info.get("currency")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{symbol}: {exc}")
                continue
            if price is None:
                errors.append(f"{symbol}: empty quote")
                continue
            return QuoteSnapshot(
                symbol=symbol,
                price=float(price),
                currency=currency if isinstance(currency, str) else None,
                market_cap=float(market_cap) if isinstance(market_cap, (int, float)) else None,
                quote_time=None,
                source=f"yfinance:{symbol}",
                status="ok; market context only; optional yfinance adapter",
            )

        fallback = self.fallback.fetch_market_snapshot(ticker, market)
        return QuoteSnapshot(
            fallback.symbol,
            fallback.price,
            fallback.currency,
            fallback.market_cap,
            fallback.quote_time,
            fallback.source,
            f"yfinance failed: {'; '.join(errors[:3])}; fallback={fallback.status}",
        )

    def fetch_official_filings(self, ticker: str, market: str | None) -> list[FilingLead]:
        return []

    def fetch_recent_events(self, ticker: str, market: str | None) -> list[EventLead]:
        return []


class SecFilingProvider:
    name = "sec"

    def fetch_market_snapshot(self, ticker: str, market: str | None) -> QuoteSnapshot:
        return QuoteSnapshot(ticker, None, None, None, None, self.name, "SEC does not provide quote context")

    def fetch_official_filings(self, ticker: str, market: str | None) -> list[FilingLead]:
        return []

    def fetch_recent_events(self, ticker: str, market: str | None) -> list[EventLead]:
        return []


class SinaQuoteProvider:
    """Direct Sina quote endpoint adapter for A-share market context."""

    name = "sina_quote_endpoint"

    def fetch_market_snapshot(self, ticker: str, market: str | None) -> QuoteSnapshot:
        symbol = sina_symbol(ticker)
        if not symbol:
            return QuoteSnapshot(ticker, None, None, None, None, self.name, "no Sina symbol candidate")
        url = f"https://hq.sinajs.cn/list={urllib.parse.quote(symbol)}"
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/plain,*/*",
                "Referer": "https://finance.sina.com.cn/",
            },
        )
        last_error: Exception | None = None
        payload = ""
        for _attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                    payload = response.read(MAX_RESPONSE_BYTES + 1)[:MAX_RESPONSE_BYTES].decode("gb18030", errors="replace")
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if not payload:
            return QuoteSnapshot(symbol, None, None, None, None, url, f"{symbol}: {last_error}")
        match = re.search(r'="([^"]*)"', payload)
        if not match or not match.group(1):
            return QuoteSnapshot(symbol, None, None, None, None, url, f"{symbol}: empty Sina quote")
        fields = match.group(1).split(",")
        if len(fields) < 32:
            return QuoteSnapshot(symbol, None, None, None, None, url, f"{symbol}: malformed Sina quote")
        price = parse_float(fields[3])
        quote_date = fields[30].strip() if len(fields) > 30 else ""
        quote_time = fields[31].strip() if len(fields) > 31 else ""
        return QuoteSnapshot(
            symbol=symbol,
            price=price,
            currency="CNY",
            market_cap=None,
            quote_time=f"{quote_date} {quote_time}".strip() or None,
            source=url,
            status="ok; delayed market context only; Sina quote endpoint",
        )

    def fetch_official_filings(self, ticker: str, market: str | None) -> list[FilingLead]:
        return []

    def fetch_recent_events(self, ticker: str, market: str | None) -> list[EventLead]:
        return []


class AkshareStubProvider:
    name = "akshare_stub"

    def fetch_market_snapshot(self, ticker: str, market: str | None) -> QuoteSnapshot:
        return QuoteSnapshot(
            ticker,
            None,
            None,
            None,
            None,
            self.name,
            "AKShare adapter not enabled; third-party package requires separate safety review",
        )

    def fetch_official_filings(self, ticker: str, market: str | None) -> list[FilingLead]:
        return []

    def fetch_recent_events(self, ticker: str, market: str | None) -> list[EventLead]:
        return []


def yahoo_symbol_candidates(ticker: str, market: str | None) -> list[str]:
    clean = ticker.strip().upper()
    if not clean:
        return []
    if "." in clean or clean.endswith((" HK", " CH")):
        return [clean.replace(" ", ".")]
    if is_hk_market(market) and re.fullmatch(r"\d{1,5}", clean):
        return [f"{clean.zfill(4)}.HK", clean]
    if is_cn_market(market):
        return []
    if re.fullmatch(r"\d{6}", clean):
        return []
    return [clean]


def parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sina_symbol(ticker: str) -> str | None:
    clean = ticker.strip().lower()
    if re.fullmatch(r"(sh|sz|bj)\d{6}", clean):
        return clean
    digits = re.sub(r"\D", "", clean)
    if not re.fullmatch(r"\d{6}", digits):
        return None
    if digits.startswith(("600", "601", "603", "605", "688", "689")):
        return f"sh{digits}"
    if digits.startswith(("000", "001", "002", "003", "300", "301")):
        return f"sz{digits}"
    if digits.startswith(("4", "8", "9")):
        return f"bj{digits}"
    return None


def stooq_symbol(symbol: str, market: str | None) -> str | None:
    clean = symbol.strip().lower().replace(" ", ".")
    if not clean:
        return None
    if is_cn_market(market):
        return None
    if is_hk_market(market):
        base = clean.removesuffix(".hk").zfill(4)
        return f"{base}.hk"
    if "." in clean:
        clean = clean.split(".", 1)[0]
    if re.fullmatch(r"[a-z]{1,6}", clean):
        return f"{clean}.us"
    return None


def fetch_yahoo_chart_quote(symbol: str) -> QuoteSnapshot:
    encoded = urllib.parse.quote(symbol)
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{encoded}?range=1d&interval=1d"
    try:
        payload = json.loads(safe_http_get(url, accept="application/json"))
    except Exception as exc:  # noqa: BLE001
        return QuoteSnapshot(symbol, None, None, None, None, "yahoo_chart_endpoint", f"{symbol}: {exc}")
    results = payload.get("chart", {}).get("result", [])
    if not results:
        error = payload.get("chart", {}).get("error")
        return QuoteSnapshot(symbol, None, None, None, None, "yahoo_chart_endpoint", f"{symbol}: empty chart result; error={error}")
    item = results[0]
    meta = item.get("meta", {})
    price = meta.get("regularMarketPrice") or meta.get("previousClose")
    quote_time = meta.get("regularMarketTime")
    quote_time_text = None
    if isinstance(quote_time, int):
        quote_time_text = dt.datetime.fromtimestamp(quote_time, tz=dt.timezone.utc).isoformat()
    return QuoteSnapshot(
        symbol,
        float(price) if isinstance(price, (int, float)) else None,
        meta.get("currency") if isinstance(meta.get("currency"), str) else None,
        None,
        quote_time_text,
        url,
        "ok; market context only; Yahoo chart fallback",
    )


def fetch_stooq_quote(symbol: str, market: str | None) -> QuoteSnapshot:
    stooq = stooq_symbol(symbol, market)
    if not stooq:
        return QuoteSnapshot(symbol, None, None, None, None, "stooq_quote_csv", "no stooq symbol candidate")
    url = f"https://stooq.com/q/l/?s={urllib.parse.quote(stooq)}&f=sd2t2ohlcv&h&e=csv"
    try:
        payload = safe_http_get(url, accept="text/csv")
        rows = list(csv.DictReader(io.StringIO(payload)))
    except Exception as exc:  # noqa: BLE001
        return QuoteSnapshot(stooq, None, None, None, None, "stooq_quote_csv", f"{stooq}: {exc}")
    if not rows:
        return QuoteSnapshot(stooq, None, None, None, None, "stooq_quote_csv", f"{stooq}: empty csv")
    row = rows[0]
    close = row.get("Close")
    if not close or close.upper() == "N/D":
        return QuoteSnapshot(stooq, None, None, None, None, "stooq_quote_csv", f"{stooq}: no quote")
    date = row.get("Date") or ""
    time = row.get("Time") or ""
    return QuoteSnapshot(
        stooq,
        float(close),
        "USD" if stooq.endswith(".us") else None,
        None,
        f"{date} {time}".strip() or None,
        url,
        "ok; delayed market context only",
    )


def select_market_snapshot_provider(market: str | None) -> ProviderAdapter:
    if is_cn_market(market):
        return SinaQuoteProvider()
    if MARKET_PROVIDER == "yfinance":
        return YFinanceOptionalProvider()
    if MARKET_PROVIDER not in {"auto", "yahoo"}:
        return ManualProvider(f"unknown market provider: {MARKET_PROVIDER}")
    if is_us_market(market) or is_hk_market(market) or not market:
        return YahooQuoteProvider()
    return ManualProvider("no approved market snapshot adapter for this market")


def fetch_market_snapshot(ticker: str, market: str | None) -> QuoteSnapshot:
    return select_market_snapshot_provider(market).fetch_market_snapshot(ticker, market)
