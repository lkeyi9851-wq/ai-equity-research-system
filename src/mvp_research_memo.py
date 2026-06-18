"""MVP pipeline: official source package -> extracted notes -> research memo.

This version treats the input as a company source package, not a lone file.
For the first MVP, that means:

- annual report / official filing = factual base
- analyst reports / Bloomberg notes = conclusion examples and reasoning chains
- output = source notes plus a Markdown research memo
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

import web_research_brief
from quality_evaluator import evaluate as evaluate_quality


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_INPUT_DIR = PROJECT_ROOT / "inputs"
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv", ".json", ".xlsx", ".xlsm"}

SECTION_KEYWORDS = {
    "business_description": ["business", "overview", "operations", "principal activities", "construction machinery"],
    "segment_or_product_mix": ["segment", "product", "geographic", "overseas", "excavator", "concrete machinery", "hoisting machinery"],
    "financial_direction": ["revenue", "net sales", "operating income", "net income", "gross margin", "profit"],
    "cash_flow_and_capex": ["operating cash flow", "cash provided by operating", "capital expenditures", "free cash flow", "capex"],
    "balance_sheet_risk": ["cash and cash equivalents", "debt", "liquidity", "borrowings", "working capital"],
    "management_outlook": ["outlook", "guidance", "expect", "strategy", "management guided", "fy26 outlook"],
    "capital_allocation": ["dividend", "share repurchase", "buyback", "capital allocation"],
    "top_risks": ["risk factors", "competition", "tariff", "geopolitics", "fx risk", "foreign exchange"],
    "valuation_context": ["price target", "target price", "potential upside", "overweight", "buy", "rating", "dcf", "valuation"],
    "market_context": ["web research brief", "current price", "last price", "share price", "market cap", "volume", "quote"],
    "recent_events": ["latest news", "recent news", "announcement", "press release", "earnings release", "guidance", "regulatory filing"],
    "external_thesis": ["thesis", "initiate", "overweight", "price target", "potential upside", "growth driver", "results briefing", "takeaway", "re-rating", "going global", "electrification", "aftermarket", "mining"],
}


METRIC_PATTERNS = {
    "revenue": [
        r"(?:revenue|sales).{0,80}?(?:Rmb|RMB|CNY|USD|HKD|\$)?\s*[\d,.]+ ?(?:million|billion|bn)?",
        r"(?:Revenue|Sales).{0,60}?(?:grew|rose|increased).{0,80}",
    ],
    "profit": [
        r"(?:net profit|net income|profit|earnings).{0,100}?(?:Rmb|RMB|CNY|USD|HKD|\$)?\s*[\d,.]+ ?(?:million|billion|bn)?",
        r"(?:profit|earnings).{0,60}?(?:grew|rose|increased).{0,80}",
    ],
    "gross_margin": [
        r"(?:gross margin|GPM).{0,80}?\d+(?:\.\d+)?\s*(?:%|ppt)?",
    ],
    "cash_flow": [
        r"(?:operating cash flow|net cash provided by operating activities|free cash flow|FCF).{0,100}?(?:Rmb|RMB|CNY|USD|HKD|\$)?\s*[\d,.]+ ?(?:million|billion|bn)?",
    ],
    "debt_or_liquidity": [
        r"(?:liquidity|debt|cash|borrowings).{0,100}?(?:Rmb|RMB|CNY|USD|HKD|\$)?\s*[\d,.]+ ?(?:million|billion|bn|%)?",
    ],
    "price_target": [
        r"(?:Price Target|target price).{0,100}?(?:Rmb|RMB|HK\$|HKD|CNY|\$)?\s*\d+(?:\.\d+)?",
        r"\bPT\b.{0,60}?(?:Rmb|RMB|HK\$|HKD|CNY|\$)\s*\d+(?:\.\d+)?",
        r"(?:Rmb|RMB|HK\$|HKD|CNY|\$)\s*\d+(?:\.\d+)?.{0,50}?(?:Price Target|target price|\bPT\b)",
    ],
    "rating": [
        r"\b(?:OW|Overweight|Buy|Neutral|Sell)\s+rating\b.{0,100}",
        r"\bOverweight\b.{0,100}",
    ],
    "current_price": [
        r"(?:current price|last price|share price|close|closing price|price).{0,80}?(?:Rmb|RMB|CNY|USD|HKD|\$)?\s*\d+(?:\.\d+)?",
        r"(?:Rmb|RMB|CNY|USD|HKD|\$)\s*\d+(?:\.\d+)?.{0,50}?(?:current price|last price|share price|close|closing price)",
    ],
}

ANALYST_ANCHORS = [
    "thesis:",
    "we initiate",
    "sany heavy hosted",
    "fast '25",
    "revenue/profit",
    "revenue/profit in",
    "fast '25 revenue",
    "revenue in 2025",
    "post-fy earnings",
    "management guided",
    "for '26, sany guided",
    "for '26",
    "we forecast",
    "earnings momentum",
    "primary earnings driver",
    "price target",
    "overweight price",
    "potential upside",
    "overseas",
    "electrification",
    "aftermarket",
    "mining",
]

BOILERPLATE_MARKERS = [
    "this material is neither intended",
    "may not be reprinted",
    "see page",
    "analyst certification",
    "important disclosures",
    "does and seeks to do business",
    "investors should consider",
    "equity research coverage",
]


@dataclass(frozen=True)
class SourceDocument:
    path: Path
    text: str
    source_type: str
    category: str


@dataclass(frozen=True)
class EvidenceSnippet:
    bucket: str
    text: str
    source_name: str
    location: str
    category: str


@dataclass(frozen=True)
class SourceMapItem:
    source_name: str
    category: str
    source_type: str
    span: str
    useful_entries: tuple[str, ...]
    extraction_quality: str


@dataclass(frozen=True)
class FinancialSnapshot:
    source_name: str | None = None
    latest_period: str = "latest"
    forecast_period_1: str = "next year"
    forecast_period_2: str = "following year"
    revenue_growth_latest: float | None = None
    revenue_growth_f1: float | None = None
    revenue_growth_f2: float | None = None
    gross_margin_latest: float | None = None
    gross_margin_f1: float | None = None
    gross_margin_f2: float | None = None
    eps_growth_latest: float | None = None
    eps_growth_f1: float | None = None
    eps_growth_f2: float | None = None
    fcf_latest: float | None = None
    fcf_per_share_latest: float | None = None
    price_to_fcf_latest: float | None = None
    eps_f1: float | None = None
    eps_f2: float | None = None
    current_price: float | None = None
    current_price_source: str | None = None
    current_price_currency: str | None = None
    target_price: float | None = None
    target_price_source: str | None = None
    target_price_currency: str | None = None
    overseas_revenue_latest: float | None = None
    overseas_share_latest: float | None = None
    overseas_gpm_latest: float | None = None
    domestic_gpm_latest: float | None = None


@dataclass(frozen=True)
class ValuationReconciliation:
    source_pfcf: float | None = None
    recalculated_pfcf: float | None = None
    pfcf_mismatch_pct: float | None = None
    fcf_yield: float | None = None
    pe_f1: float | None = None
    pe_f2: float | None = None
    target_upside: float | None = None
    conflict: bool = False
    confidence_cap: str = "High"
    note: str = "Valuation inputs reconcile or are insufficient for a conflict test."


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value)
    return value.strip("-") or "company"


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def read_csv_file(path: Path) -> str:
    rows: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        for index, row in enumerate(reader):
            if index >= 400:
                rows.append("[truncated after 400 rows]")
                break
            rows.append(" | ".join(cell.strip() for cell in row))
    return "\n".join(rows)


def read_json_file(path: Path) -> str:
    raw_text = read_text_file(path)
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text
    return json.dumps(data, ensure_ascii=False, indent=2)


def read_xlsx_file(path: Path) -> str:
    try:
        import openpyxl  # type: ignore
    except ImportError as exc:
        raise RuntimeError("XLSX support requires openpyxl in the active Python environment.") from exc

    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    parts: list[str] = []
    for sheet in workbook.worksheets[:8]:
        parts.append(f"[Sheet: {sheet.title}]")
        for row_index, row in enumerate(sheet.iter_rows(values_only=True)):
            if row_index >= 180:
                parts.append("[sheet truncated after 180 rows]")
                break
            values = ["" if cell is None else str(cell) for cell in row]
            if any(value.strip() for value in values):
                parts.append(" | ".join(values))
    return "\n".join(parts)


def read_pdf_file(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PDF support requires pypdf. Convert the filing to text or install pypdf."
        ) from exc

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page_index, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(f"\n[Page {page_index + 1}]\n{page_text}")
    return "\n".join(pages)


def read_source_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return read_text_file(path)
    if suffix == ".csv":
        return read_csv_file(path)
    if suffix == ".json":
        return read_json_file(path)
    if suffix in {".xlsx", ".xlsm"}:
        return read_xlsx_file(path)
    if suffix == ".pdf":
        return read_pdf_file(path)
    raise ValueError(f"Unsupported input format: {path.suffix}")

def classify_source(path: Path, text: str) -> str:
    name = path.name.lower()
    head = text[:8000].lower()
    suffix = path.suffix.lower()
    if suffix == ".json" and ("evidence_patch" in head or "valuation_patch" in head or "current_price" in head):
        return "evidence_patch"
    if "finance chall" in head or "pair trade portfolio" in head or "our variant view" in head:
        return "reference_sample"
    if suffix in {".xlsx", ".xlsm", ".csv"} and any(
        token in head
        for token in [
            "bbg adj highlights",
            "standardized",
            "company financial",
            "free cash flow",
            "revenue, adj",
            "income statement",
            "balance sheet",
            "cash flow",
            "gross margin",
            "ebitda",
            "eps",
            "enterprise value",
        ]
    ):
        return "financial_data"
    if suffix in {".md", ".json", ".txt"} and (
        "web research brief" in head
        or "web research search log" in head
        or "retrieved at:" in head
        or "source_url" in head
        or "retrieved_at" in head
        or any(token in name for token in ["web-research", "web_research"])
    ):
        return "web_research"
    if any(token in name for token in ["bbg", "ubs", "jp", "jpmorgan", "research"]):
        return "analyst_report"
    if any(token in head for token in ["price target", "overweight", "j.p. morgan", "ubs", "bloomberg intelligence"]):
        return "analyst_report"
    if "\u5e74\u5ea6\u62a5\u544a" in text[:12000] or "annual report" in head or "form 10-k" in head:
        return "annual_report"
    return "supplement"
    return "supplement"


def discover_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    files = [
        item
        for item in sorted(input_path.iterdir())
        if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS and not item.name.startswith(".")
    ]
    if not files:
        raise ValueError(f"No supported source files found in {input_path}")
    return files


def load_sources(input_path: Path) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for path in discover_input_files(input_path):
        raw_text = read_source_text(path)
        if path.suffix.lower() in {".xlsx", ".xlsm", ".csv"}:
            text = "\n".join(normalize_whitespace(line) for line in raw_text.splitlines() if line.strip())
        else:
            text = normalize_whitespace(raw_text)
        if not text:
            continue
        documents.append(
            SourceDocument(
                path=path,
                text=text,
                source_type=path.suffix.lower().lstrip("."),
                category=classify_source(path, text),
            )
        )
    if not documents:
        raise ValueError(f"No extractable text found in {input_path}")
    return documents


def split_into_blocks(text: str) -> Iterable[tuple[int, str]]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    if len(paragraphs) < 20:
        paragraphs = [item.strip() for item in re.split(r"(?<=[銆傦紒锛?!?])\s+", text) if item.strip()]

    cursor = 0
    for paragraph in paragraphs:
        start = text.find(paragraph, cursor)
        if start < 0:
            start = text.find(paragraph)
        if start < 0:
            start = cursor
        cursor = start + len(paragraph)
        if len(paragraph) <= 850:
            yield start, paragraph
        else:
            for index in range(0, len(paragraph), 700):
                piece = paragraph[index : index + 850].strip()
                if piece:
                    yield start + index, piece


def page_at_position(text: str, position: int) -> str:
    pages = list(re.finditer(r"\[Page\s+(\d+)\]", text, flags=re.IGNORECASE))
    if pages:
        current = pages[0].group(1)
        for match in pages:
            if match.start() > position:
                break
            current = match.group(1)
        return f"page {current}"

    sheets = list(re.finditer(r"\[Sheet:\s*([^\]]+)\]", text))
    if sheets:
        current_sheet = sheets[0].group(1)
        for match in sheets:
            if match.start() > position:
                break
            current_sheet = match.group(1)
        return f"sheet {current_sheet}"

    return f"char {position}"


def source_span(document: SourceDocument) -> str:
    if document.source_type == "pdf":
        pages = re.findall(r"\[Page\s+(\d+)\]", document.text, flags=re.IGNORECASE)
        if pages:
            return f"{len(set(pages))} pages extracted"
        return "pdf text extracted, page markers unavailable"
    if document.source_type in {"xlsx", "xlsm"}:
        sheets = re.findall(r"\[Sheet:\s*([^\]]+)\]", document.text)
        if sheets:
            return "sheets: " + ", ".join(sheets[:8])
        return "spreadsheet rows extracted"
    if document.source_type == "csv":
        return "csv rows extracted"
    return "text extracted"


def extraction_quality(document: SourceDocument) -> str:
    text = document.text
    if len(text) < 800:
        return "partial"
    replacement_count = text.count("\ufffd")
    if replacement_count > 20:
        return "noisy encoding"
    if document.source_type == "pdf" and "[Page " not in text:
        return "partial pdf extraction"
    table_markers = text.count("|") + text.lower().count("[sheet:")
    if table_markers > 80:
        return "table-heavy"
    return "usable"


SOURCE_MAP_BUCKETS = (
    "business_description",
    "segment_or_product_mix",
    "financial_direction",
    "cash_flow_and_capex",
    "balance_sheet_risk",
    "management_outlook",
    "capital_allocation",
    "top_risks",
    "valuation_context",
    "market_context",
    "recent_events",
)


def build_source_map(documents: list[SourceDocument], max_entries: int = 5) -> list[SourceMapItem]:
    items: list[SourceMapItem] = []
    for document in documents:
        useful: list[str] = []
        seen: set[str] = set()
        if document.category == "reference_sample":
            useful.append("reference sample only; excluded from evidence")
        else:
            blocks = list(split_into_blocks(document.text))
            for bucket in SOURCE_MAP_BUCKETS:
                if bucket in {"valuation_context"} and document.category not in {"analyst_report", "web_research"}:
                    continue
                if bucket in {"market_context", "recent_events"} and document.category != "web_research":
                    continue
                keywords = SECTION_KEYWORDS[bucket]
                for start, block in blocks:
                    lower = block.lower()
                    if not any(keyword.lower() in lower for keyword in keywords):
                        continue
                    location = page_at_position(document.text, start)
                    label = f"{location}: {bucket_title(bucket)}"
                    if label not in seen:
                        seen.add(label)
                        useful.append(label)
                    break
                if len(useful) >= max_entries:
                    break
        if not useful:
            useful.append("no decision-relevant section found in first pass")
        items.append(
            SourceMapItem(
                source_name=document.path.name,
                category=document.category,
                source_type=document.source_type,
                span=source_span(document),
                useful_entries=tuple(useful),
                extraction_quality=extraction_quality(document),
            )
        )
    return items


def clean_snippet(text: str, max_length: int = 420) -> str:
    text = normalize_whitespace(text)
    if len(text) <= max_length:
        return text
    stops = [text.rfind(mark, 0, max_length) for mark in (".", ";", "!", "?")]
    stop = max(stops)
    if stop >= 180:
        return text[: stop + 1]
    return text[:max_length].rstrip() + "..."


def trim_analyst_block(text: str) -> str:
    lower = text.lower()
    anchor_positions = [lower.find(anchor) for anchor in ANALYST_ANCHORS if lower.find(anchor) >= 0]
    if anchor_positions:
        text = text[min(anchor_positions) :]
    return text


def is_boilerplate_only(text: str) -> bool:
    lower = text.lower()
    if any(marker in lower for marker in BOILERPLATE_MARKERS) and not any(anchor in lower for anchor in ANALYST_ANCHORS):
        return True
    email_count = len(re.findall(r"[\w.\-]+@[\w.\-]+", text))
    return email_count >= 2 and not any(anchor in lower for anchor in ANALYST_ANCHORS)


def analyst_score(item: EvidenceSnippet) -> int:
    lower = item.text.lower()
    score = 0
    for anchor in ANALYST_ANCHORS:
        if anchor in lower:
            score += 3
    if "price target" in lower or "pt of" in lower:
        score += 3
    if "rating" in lower or "overweight" in lower:
        score += 2
    if any(marker in lower for marker in BOILERPLATE_MARKERS):
        score -= 4
    if "table_eps" in lower:
        score -= 8
    return score


def collect_evidence(documents: list[SourceDocument], max_per_bucket: int = 8) -> list[EvidenceSnippet]:
    evidence: list[EvidenceSnippet] = []
    seen: set[tuple[str, str, str]] = set()
    bucket_source_counts: dict[tuple[str, str], int] = {}

    for document in documents:
        if document.category == "reference_sample":
            continue
        for start, block in split_into_blocks(document.text):
            lower = block.lower()
            for bucket, keywords in SECTION_KEYWORDS.items():
                if bucket in {"valuation_context", "external_thesis"} and document.category not in {"analyst_report", "web_research"}:
                    continue
                if bucket in {"market_context", "recent_events"} and document.category != "web_research":
                    continue
                source_key = (bucket, document.path.name)
                if bucket_source_counts.get(source_key, 0) >= max_per_bucket:
                    continue
                if any(keyword.lower() in lower for keyword in keywords):
                    candidate = trim_analyst_block(block) if document.category == "analyst_report" else block
                    if document.category == "analyst_report" and is_boilerplate_only(candidate):
                        continue
                    snippet = clean_snippet(candidate)
                    key = (bucket, document.path.name, snippet[:120])
                    if key in seen:
                        continue
                    seen.add(key)
                    evidence.append(
                        EvidenceSnippet(
                            bucket=bucket,
                            text=snippet,
                            source_name=document.path.name,
                            location=page_at_position(document.text, start),
                            category=document.category,
                        )
                    )
                    bucket_source_counts[source_key] = bucket_source_counts.get(source_key, 0) + 1

    return evidence


def collect_metric_mentions(documents: list[SourceDocument], max_per_metric: int = 8) -> dict[str, list[EvidenceSnippet]]:
    mentions: dict[str, list[EvidenceSnippet]] = {}
    for metric, patterns in METRIC_PATTERNS.items():
        metric_items: list[EvidenceSnippet] = []
        seen: set[str] = set()
        active_documents = [document for document in documents if document.category != "reference_sample"]
        if metric in {"price_target", "rating"}:
            ordered_documents = [document for document in active_documents if document.category == "analyst_report"]
        elif metric == "current_price":
            ordered_documents = [document for document in active_documents if document.category == "web_research"] + [
                document for document in active_documents if document.category == "analyst_report"
            ]
        else:
            ordered_documents = sorted(active_documents, key=lambda document: 0 if document.category == "annual_report" else 1)
        for document in ordered_documents:
            if metric in {"price_target", "rating"} and document.category != "analyst_report":
                continue
            for pattern in patterns:
                for match in re.findall(pattern, document.text, flags=re.IGNORECASE | re.DOTALL):
                    item = clean_snippet(match, max_length=240)
                    compact_key = re.sub(r"\s+", " ", item.lower())[:180]
                    if compact_key in seen:
                        continue
                    seen.add(compact_key)
                    metric_items.append(
                        EvidenceSnippet(
                            bucket=metric,
                            text=item,
                            source_name=document.path.name,
                            location="regex match",
                            category=document.category,
                        )
                    )
                    if len(metric_items) >= max_per_metric:
                        break
                if len(metric_items) >= max_per_metric:
                    break
            if len(metric_items) >= max_per_metric:
                break
        mentions[metric] = metric_items
    return mentions


def metric_score(item: EvidenceSnippet) -> int:
    lower = item.text.lower()
    score = 0
    if item.category == "analyst_report":
        score += 2
    if "price target:" in lower or "pt of" in lower:
        score += 6
    if re.search(r"(rmb|hk\$|hkd|\$)\s*\d", item.text, flags=re.IGNORECASE):
        score += 3
    if "rating" in lower or "overweight" in lower:
        score += 4
    if "company ticker" in lower or "prev end date" in lower:
        score -= 4
    return score


def best_metric_text(items: list[EvidenceSnippet], default: str) -> str:
    if not items:
        return default
    best = sorted(items, key=metric_score, reverse=True)[0]
    return best.text


def collect_analyst_reasoning(evidence: list[EvidenceSnippet]) -> list[EvidenceSnippet]:
    analyst_items = [
        item
        for item in evidence
        if item.category == "analyst_report" and item.bucket in {"external_thesis", "valuation_context", "management_outlook", "financial_direction", "top_risks"}
    ]
    balanced: list[EvidenceSnippet] = []
    seen_sources = sorted({item.source_name for item in analyst_items})
    seen_text: set[str] = set()
    for source in seen_sources:
        source_items = sorted(
            [item for item in analyst_items if item.source_name == source],
            key=analyst_score,
            reverse=True,
        )
        added = 0
        for item in source_items:
            key = re.sub(r"\s+", " ", item.text.lower())[:180]
            if key in seen_text:
                continue
            seen_text.add(key)
            balanced.append(item)
            added += 1
            if added >= 4:
                break
    return balanced[:18]

def bucket_title(bucket: str) -> str:
    titles = {
        "business_description": "Business Description",
        "segment_or_product_mix": "Segment / Product Mix",
        "financial_direction": "Financial Direction",
        "cash_flow_and_capex": "Cash Flow And Capex",
        "balance_sheet_risk": "Balance Sheet Risk",
        "management_outlook": "Management Outlook",
        "capital_allocation": "Capital Allocation",
        "top_risks": "Top Risks",
        "valuation_context": "Valuation Context",
        "market_context": "Market Context",
        "recent_events": "Recent Events",
        "external_thesis": "External Thesis",
        "current_price": "Current Price",
        "price_target": "Price Target",
        "rating": "Rating",
        "gross_margin": "Gross Margin",
        "cash_flow": "Cash Flow",
        "debt_or_liquidity": "Debt / Liquidity",
        "revenue": "Revenue",
        "profit": "Profit",
    }
    return titles.get(bucket, bucket.replace("_", " ").title())
    return titles.get(bucket, bucket.replace("_", " ").title())


def infer_company_name(documents: list[SourceDocument], fallback: str) -> str:
    combined_head = "\n".join(document.text[:5000] for document in documents)
    for pattern in (
        r"(涓変竴閲嶅伐鑲′唤鏈夐檺鍏徃)",
        r"鍏徃绠€绉癧:锛歖\s*([\u4e00-\u9fffA-Za-z0-9&., '\-]{2,40})",
        r"([A-Z][A-Za-z0-9&., '\-]{2,80})\s+(?:Annual Report|Equity Research)",
    ):
        match = re.search(pattern, combined_head, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" .,-")
    return fallback


def infer_request_fields(request: str | None) -> dict[str, str]:
    if not request:
        return {}
    fields: dict[str, str] = {}
    ticker_match = re.search(r"\b\d{5,6}\b|\b[A-Z]{1,5}(?:\.[A-Z]{1,3})?\b", request)
    if ticker_match:
        fields["ticker"] = ticker_match.group(0)
    fields["language"] = "EN"
    company_match = re.search(r"([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9 .&-]{1,30})(?:鐨剕,|锛寍\s)+(?:鐮旂┒|鍒嗘瀽|memo|鎶ュ憡)", request)
    if company_match:
        fields["company"] = company_match.group(1).strip()
    if "涓変竴" in request.lower() or "sany" in request.lower():
        fields.setdefault("company", "涓変竴閲嶅伐")
        fields.setdefault("ticker", "600031")
    return fields


def source_label(document: SourceDocument) -> str:
    today = dt.date.today().isoformat()
    return (
        f"{document.path.name}; category: {document.category}; type: {document.source_type}; "
        f"date retrieved: {today}; status: readable source file, extraction quality depends on PDF encoding."
    )


def first_text(items: list[EvidenceSnippet], default: str = "Not enough evidence extracted from source files.") -> str:
    return items[0].text if items else default


def items_for_bucket(evidence: list[EvidenceSnippet], bucket: str, category: str | None = None) -> list[EvidenceSnippet]:
    items = [item for item in evidence if item.bucket == bucket]
    if category:
        items = [item for item in items if item.category == category]
    return items

def sufficiency(
    documents: list[SourceDocument],
    evidence: list[EvidenceSnippet],
    metrics: dict[str, list[EvidenceSnippet]],
) -> tuple[str, list[str]]:
    categories = {document.category for document in documents}
    buckets = {item.bucket for item in evidence}
    missing: list[str] = []

    if "annual_report" not in categories:
        missing.append("official annual report or filing")

    required_buckets = {
        "business_description": "business description",
        "financial_direction": "financial direction",
        "top_risks": "risk factors",
    }
    for bucket, label in required_buckets.items():
        if bucket not in buckets:
            missing.append(label)

    if not metrics.get("revenue"):
        missing.append("revenue data")
    if not metrics.get("profit"):
        missing.append("profit data")

    if len(missing) <= 2:
        return "enough for MVP memo with disclosed limitations", missing
    if len(missing) <= 5:
        return "usable, but memo should emphasize limitations", missing
    return "not enough for a full standard memo; focused data request recommended", missing


def autonomous_research_plan(
    documents: list[SourceDocument],
    evidence: list[EvidenceSnippet],
    metrics: dict[str, list[EvidenceSnippet]],
    snapshot: FinancialSnapshot,
) -> dict[str, object]:
    categories = {document.category for document in documents}
    buckets = {item.bucket for item in evidence}
    tasks: list[str] = []

    if "annual_report" not in categories:
        tasks.append("Fetch official annual report or filing.")
    if "financial_data" not in categories:
        tasks.append("Add structured financial table or model extract.")
    if not snapshot.current_price:
        tasks.append("Refresh current price and price date.")
    if "analyst_report" not in categories and "web_research" not in categories:
        tasks.append("Collect recent news, industry context, and consensus or peer valuation.")
    elif not metrics.get("price_target") and not snapshot.target_price:
        tasks.append("Collect consensus or peer valuation; external target price is optional.")
    if "top_risks" not in buckets:
        tasks.append("Extract company-specific risk factors.")
    if snapshot.price_to_fcf_latest is not None and snapshot.fcf_per_share_latest is not None and snapshot.current_price:
        reconciliation = valuation_reconciliation(snapshot)
        if reconciliation.conflict:
            tasks.insert(0, "Reconcile valuation inputs before increasing rating confidence.")

    if not tasks:
        tasks.append("No blocking data task; proceed with memo and disclose remaining uncertainty.")

    return {
        "available_sources": {
            "official": source_count(documents, "annual_report"),
            "financial_data": source_count(documents, "financial_data"),
            "external_views": source_count(documents, "analyst_report"),
            "web": source_count(documents, "web_research"),
        },
        "evidence_gaps": tasks[:5],
        "next_tasks": tasks[:5],
        "mode_actions": {
            "off": "Show evidence request only.",
            "auto": "Generate offline targeted search log.",
            "online": "Generate compact web brief only after explicit network permission.",
        },
    }


def source_sufficiency_gate(status: str, missing: list[str], snapshot: FinancialSnapshot) -> dict[str, object]:
    reconciliation = valuation_reconciliation(snapshot)
    blocking_items = list(missing)
    if reconciliation.conflict:
        blocking_items.append("valuation reconciliation")
    can_issue_rating = status.startswith("enough") and not blocking_items[:1]
    if status.startswith("enough") and reconciliation.conflict:
        can_issue_rating = True
    return {
        "can_issue_rating": can_issue_rating,
        "confidence_cap": reconciliation.confidence_cap,
        "blocking_items": blocking_items[:5],
        "read": "Enough for directional rating with confidence cap." if can_issue_rating else "Not enough for a clean rating without more source work.",
    }


def market_expectation_gap(
    snapshot: FinancialSnapshot,
    evidence: list[EvidenceSnippet],
    documents: list[SourceDocument] | None = None,
) -> dict[str, str]:
    tags = market_assumption_tags(collect_analyst_reasoning(evidence))
    reconciliation = valuation_reconciliation(snapshot)
    web_impact = web_evidence_impact(documents or [])
    if tags:
        driver = " / ".join(tags[:3])
        framing = "External views emphasize"
    elif snapshot.overseas_share_latest is not None or snapshot.gross_margin_f2 is not None:
        driver = "growth, mix, margin, and cash conversion"
        framing = "Company data supports"
    else:
        driver = "financial transmission"
        framing = "Current sources only partially support"
    if reconciliation.conflict:
        return {
            "status": "Potential gap, not cleanly investable yet",
            "gap": f"{framing} {driver}, but valuation inputs do not reconcile.",
            "evidence_needed": "Refresh price, FCF/share, fiscal year, share count, and source P/FCF definition.",
        }
    if reconciliation.target_upside is not None and reconciliation.target_upside >= 0.20:
        return {
            "status": "Potential positive gap",
            "gap": f"External target implies {fmt_upside(reconciliation.target_upside)} upside; test whether {driver} is underpriced rather than consensus-known.",
            "evidence_needed": "Consensus estimates, current price date, peer multiples, and disconfirming news.",
        }
    if web_impact.get("risk_check"):
        return {
            "status": "Gap challenged by web evidence",
            "gap": f"{framing} {driver}, but web risk evidence must be reconciled before treating the gap as investable.",
            "evidence_needed": "Verify the web risk source, estimate impact, and decide whether it changes rating or confidence.",
        }
    if web_impact.get("valuation_expectation"):
        return {
            "status": "Gap under review",
            "gap": f"{framing} {driver}. Web valuation evidence provides a market-expectation anchor, but mispricing still needs estimate and peer reconciliation.",
            "evidence_needed": "Compare web consensus/peer/target evidence with current multiple, forecasts, and recent revisions.",
        }
    return {
        "status": "Gap not proven",
        "gap": f"{framing} {driver}, but market mispricing is not proven from current sources.",
        "evidence_needed": "Current valuation, consensus assumptions, peer range, and recent revisions.",
    }


def dcf_readiness_gate(snapshot: FinancialSnapshot, view: dict[str, str], expectation: dict[str, str]) -> dict[str, str]:
    reconciliation = valuation_reconciliation(snapshot)
    if reconciliation.conflict:
        return {
            "status": "Not ready",
            "reason": "Reconcile valuation inputs before building DCF.",
            "next": "Fix price, FCF/share, source multiple, fiscal year, and share count.",
        }
    if not view["rating"].startswith(("Buy", "Sell")):
        return {
            "status": "Not needed yet",
            "reason": "Directional opportunity is not strong enough.",
            "next": "Improve expectation-gap evidence before modeling.",
        }
    if expectation["status"].startswith("Potential"):
        return {
            "status": "Ask user",
            "reason": "Directional thesis may affect investment action and valuation inputs are clean enough.",
            "next": "Offer DCF / Excel model as next step.",
        }
    return {
        "status": "Not needed yet",
        "reason": "Market expectation gap is not proven.",
        "next": "Collect consensus and peer valuation first.",
    }


def build_learning_points(analyst_reasoning: list[EvidenceSnippet], metrics: dict[str, list[EvidenceSnippet]]) -> list[str]:
    points: list[str] = []
    text = " ".join(item.text.lower() for item in analyst_reasoning)
    if "overseas" in text or "global" in text:
        points.append("External reports often use overseas revenue mix and overseas margin as core thesis evidence.")
    if "electrification" in text or "electric" in text:
        points.append("External reports may treat electrification or green equipment as growth and re-rating drivers.")
    if "mining" in text:
        points.append("Mining equipment can be used as evidence for higher-end products and customer stickiness.")
    if "aftermarket" in text:
        points.append("Aftermarket exposure can support margin stability and earnings durability.")
    if metrics.get("price_target") or metrics.get("rating"):
        points.append("Sell-side reports usually start from rating and target price, then support them with growth, margin, valuation, and risk assumptions.")
    if not points:
        points.append("The useful pattern is to break conclusions into rating, valuation, growth driver, margin path, and risk constraint.")
    return points[:5]
    return points


def render_evidence_list(items: list[EvidenceSnippet], limit: int = 5) -> list[str]:
    if not items:
        return ["- Not extracted."]
    return [f"- {short_evidence(item)}" for item in items[:limit]]


def render_source_map(items: list[SourceMapItem]) -> list[str]:
    lines: list[str] = []
    for item in items:
        lines.append(
            f"- {item.source_name} ({item.category}; {item.source_type}; {item.span}; quality: {item.extraction_quality})"
        )
        for entry in item.useful_entries[:5]:
            lines.append(f"  - {entry}")
    return lines


def short_text(text: str, max_length: int = 180) -> str:
    text = normalize_whitespace(text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\[[Pp]age \d+\]", "", text).strip()
    if len(text) <= max_length:
        return text
    stops = [text.rfind(mark, 0, max_length) for mark in (".", ";", "!", "?")]
    stop = max(stops)
    if stop >= 70:
        return text[: stop + 1]
    return text[:max_length].rstrip() + "..."


def short_evidence(item: EvidenceSnippet, max_length: int = 180) -> str:
    return f"{short_text(item.text, max_length)} [{item.source_name}]"

def evidence_score(item: EvidenceSnippet) -> int:
    text = item.text.lower()
    score = 0
    if item.category == "annual_report":
        score += 2
    if any(token in text for token in ["disclaimer", "table of contents", "important notice"]):
        score -= 8
    bucket_tokens = {
        "segment_or_product_mix": ["revenue", "overseas", "excavator", "concrete", "hoisting", "segment"],
        "top_risks": ["risk", "geopolitics", "tariff", "competition", "foreign exchange"],
        "business_description": ["business", "principal", "product", "construction machinery"],
        "financial_direction": ["revenue", "profit", "margin", "net income"],
    }
    for token in bucket_tokens.get(item.bucket, []):
        if token in text:
            score += 3
    return score
    return score


def best_item(items: list[EvidenceSnippet]) -> EvidenceSnippet | None:
    return sorted(items, key=metric_score, reverse=True)[0] if items else None


def source_count(documents: list[SourceDocument], category: str) -> int:
    return len([document for document in documents if document.category == category])


def source_index(documents: list[SourceDocument]) -> dict[str, str]:
    evidence_documents = [document for document in documents if document.category != "reference_sample"]
    return {document.path.name: f"S{index}" for index, document in enumerate(evidence_documents, start=1)}


def source_ref(item: EvidenceSnippet, index: dict[str, str]) -> str:
    return index.get(item.source_name, item.source_name)

def concise_thesis(analyst_reasoning: list[EvidenceSnippet]) -> list[str]:
    text = " ".join(item.text.lower() for item in analyst_reasoning)
    thesis: list[str] = []
    if "overseas" in text or "global" in text:
        thesis.append("Overseas expansion is a recurring external thesis line.")
    if "electrification" in text or "electric" in text:
        thesis.append("Electrification is used as a potential growth or re-rating driver.")
    if "mining" in text:
        thesis.append("Mining equipment is used as evidence for higher-end products and stickier customers.")
    if "aftermarket" in text:
        thesis.append("Aftermarket exposure is framed as a margin-stability driver.")
    if not thesis:
        thesis.append("External reports usually combine growth, margin, valuation, and risk into one thesis chain.")
    return thesis[:4]


def noise_judgement(evidence: list[EvidenceSnippet], metrics: dict[str, list[EvidenceSnippet]]) -> list[str]:
    judgements = [
        "Remove: disclaimers, analyst lists, copyright pages, tables of contents, headers, and footers.",
        "Down-rank: target price itself; keep the assumptions behind it.",
    ]
    if metrics.get("price_target"):
        judgements.append("Keep: target price or rating only when linked to revenue, margin, cash flow, or valuation assumptions.")
    if items_for_bucket(evidence, "business_description", "annual_report"):
        judgements.append("Keep: official annual-report facts as the factual base.")
    return judgements


def strongest_support(
    evidence: list[EvidenceSnippet],
    metrics: dict[str, list[EvidenceSnippet]],
) -> list[str]:
    support: list[str] = []
    for label, metric in [
        ("Revenue", "revenue"),
        ("Profit", "profit"),
        ("Gross margin", "gross_margin"),
        ("Cash flow", "cash_flow"),
    ]:
        item = factual_metric_item(metrics, metric)
        if item:
            support.append(f"{label}: {short_evidence(item, max_length=120)}")

    target_item = best_item(metrics.get("price_target", []))
    if target_item:
        support.append(f"Target price / rating: {short_evidence(target_item, max_length=120)}")

    for label, bucket in [
        ("Business", "business_description"),
        ("Product / segment", "segment_or_product_mix"),
    ]:
        items = items_for_bucket(evidence, bucket, "annual_report") or items_for_bucket(evidence, bucket)
        if items:
            best = sorted(items, key=evidence_score, reverse=True)[0]
            support.append(f"{label}: {short_evidence(best, max_length=120)}")
    return support[:8]
    return support[:8]


def metric_item(metrics: dict[str, list[EvidenceSnippet]], key: str) -> EvidenceSnippet | None:
    return best_item(metrics.get(key, []))


def factual_metric_item(metrics: dict[str, list[EvidenceSnippet]], key: str) -> EvidenceSnippet | None:
    items = metrics.get(key, [])
    official = [item for item in items if item.category == "annual_report"]
    financial = [item for item in items if item.category == "financial_data"]
    if official:
        return best_item(official)
    if financial:
        return best_item(financial)
    return best_item(items)


def evidence_item(evidence: list[EvidenceSnippet], bucket: str, category: str | None = None) -> EvidenceSnippet | None:
    items = items_for_bucket(evidence, bucket, category) or items_for_bucket(evidence, bucket)
    if not items:
        return None
    return sorted(items, key=evidence_score, reverse=True)[0]


def risk_item(evidence: list[EvidenceSnippet]) -> EvidenceSnippet | None:
    items = items_for_bucket(evidence, "top_risks")
    strong_items = []
    for item in items:
        text = item.text.lower()
        if is_boilerplate_only(item.text) or any(token in text for token in ["distributed by", "professional investors", "not for further distribution"]):
            continue
        if "competitive advantage" in text:
            continue
        if any(token in text for token in ["risk factor", "key risk", "downside risk", "risk:"]):
            strong_items.append(item)
    return sorted(strong_items, key=evidence_score, reverse=True)[0] if strong_items else None


def parse_number(value: str) -> float | None:
    value = value.strip()
    if not value or value in {"-", "None", "N/A", "n/a"}:
        return None
    value = value.replace(",", "").replace("%", "")
    value = re.sub(r"^[^\d.\-]+", "", value)
    value = re.sub(r"[^\d.\-].*$", "", value)
    try:
        return float(value)
    except ValueError:
        return None


def row_values(line: str) -> list[str]:
    values = [cell.strip() for cell in line.split("|")]
    if len(values) >= 2:
        first = values[0].lower()
        second = values[1].lower()
        if first == "growth %" and second == "yoy":
            values = ["Growth %, YoY", *values[2:]]
        elif first == "eps" and second in {"adj", "adjusted"}:
            values = ["EPS, Adj", *values[2:]]
    return values


def iter_sheet_rows(document: SourceDocument, sheet_name: str) -> Iterable[list[str]]:
    active_sheet = ""
    for line in document.text.splitlines():
        if line.startswith("[Sheet:"):
            active_sheet = line
            continue
        if sheet_name in active_sheet:
            values = row_values(line)
            if values:
                yield values


def find_header_row(document: SourceDocument, sheet_name: str) -> list[str] | None:
    for values in iter_sheet_rows(document, sheet_name):
        period_cells = [
            value
            for value in values[1:]
            if re.search(r"\bfy\s*\d{4}\b|\d{4}\s+[a-z]\s*\(|\d{1,2}/\d{1,2}/\d{4}", value.lower())
            or any(token in value.lower() for token in ["current/ltm", "last 12m"])
        ]
        if len(period_cells) >= 3:
            return values
    return None


def find_financial_row(document: SourceDocument, sheet_name: str, row_label: str) -> list[str] | None:
    for values in iter_sheet_rows(document, sheet_name):
        if values[0].strip().lower() == row_label.lower():
            return values
    return None


def find_first_financial_row(document: SourceDocument, sheet_name: str, labels: list[str]) -> list[str] | None:
    label_set = {label.lower() for label in labels}
    for values in iter_sheet_rows(document, sheet_name):
        if values[0].strip().lower() in label_set:
            return values
    return None


def find_row_after(document: SourceDocument, sheet_name: str, anchor_label: str, row_label: str, occurrence: int = 1) -> list[str] | None:
    active_sheet = ""
    armed = False
    seen = 0
    for line in document.text.splitlines():
        if line.startswith("[Sheet:"):
            active_sheet = line
            armed = False
            continue
        if sheet_name not in active_sheet:
            continue
        values = row_values(line)
        if not values:
            continue
        label = values[0].strip().lower()
        if label == anchor_label.lower():
            armed = True
            seen = 0
            continue
        if armed and label == row_label.lower():
            seen += 1
            if seen == occurrence:
                return values
    return None


def period_indices(headers: list[str] | None) -> tuple[int | None, int | None, int | None, str, str, str]:
    if not headers:
        return None, None, None, "latest", "next year", "following year"

    forecast_indices: list[int] = []
    actual_indices: list[int] = []
    for index, header in enumerate(headers):
        label = header.strip()
        lower = label.lower()
        if not re.search(r"\bfy\s*\d{4}\b|\d{4}\s+[a-z]\s*\(|\d{1,2}/\d{1,2}/\d{4}", lower):
            continue
        if "ltm" in lower or "current" in lower:
            continue
        if "est" in lower or "fwd" in lower or "forecast" in lower:
            forecast_indices.append(index)
        else:
            actual_indices.append(index)

    latest_index = actual_indices[-1] if actual_indices else None
    f1 = forecast_indices[0] if len(forecast_indices) >= 1 else None
    f2 = forecast_indices[1] if len(forecast_indices) >= 2 else None
    latest_label = headers[latest_index].strip() if latest_index is not None else "latest"
    f1_label = headers[f1].strip() if f1 is not None else "next year"
    f2_label = headers[f2].strip() if f2 is not None else "following year"
    return latest_index, f1, f2, latest_label, f1_label, f2_label


def cell_number(row: list[str] | None, index: int) -> float | None:
    if not row or index >= len(row):
        return None
    return parse_number(row[index])


def parse_web_metric_cards(text: str) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for block in re.split(r"\n(?=- Fact: )", text):
        if "Metric:" not in block or "Value:" not in block:
            continue
        source_gate = re.search(r"^\s*Source gate:\s*([a-z_]+)", block, flags=re.IGNORECASE | re.MULTILINE)
        if source_gate and source_gate.group(1).lower() not in {"accepted", "watch"}:
            continue
        if "Source gate:" in block and not source_gate:
            continue
        card: dict[str, str] = {}
        for key in ("Metric", "Value", "Unit", "Period", "Source", "Source tier", "Fact date", "Confidence"):
            match = re.search(rf"^\s*{re.escape(key)}:\s*(.+)$", block, flags=re.IGNORECASE | re.MULTILINE)
            if match:
                card[key.lower().replace(" ", "_")] = match.group(1).strip()
        if card:
            cards.append(card)
    return cards


def parse_web_evidence_cards(documents: list[SourceDocument]) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for document in documents:
        if document.category != "web_research":
            continue
        text = document.text
        for block in re.split(r"\n(?=- Fact: )", text):
            if "- Fact:" not in block:
                continue
            gate_match = re.search(r"^\s*Source gate:\s*([a-z_]+)", block, flags=re.IGNORECASE | re.MULTILINE)
            if gate_match and gate_match.group(1).lower() not in {"accepted", "watch"}:
                continue
            card: dict[str, str] = {"source_name": document.path.name}
            fact_match = re.search(r"- Fact:[ \t]*(.*)$", block, flags=re.MULTILINE)
            if fact_match:
                card["claim"] = fact_match.group(1).strip()
            for key in (
                "Source",
                "Publisher",
                "Source tier",
                "Fact date",
                "Label",
                "Metric",
                "Value",
                "Unit",
                "Period",
                "Why it matters",
                "Could change",
                "Confidence",
                "Gap",
                "Source gate",
            ):
                match = re.search(rf"^[ \t]*{re.escape(key)}:[ \t]*(.*)$", block, flags=re.IGNORECASE | re.MULTILINE)
                if match:
                    card[key.lower().replace(" ", "_")] = match.group(1).strip()
            claim = card.get("claim", "")
            source = card.get("source", "")
            if claim or source:
                cards.append(card)

        current_match = re.search(r"^- Current price:\s*(.+)$", text, flags=re.IGNORECASE | re.MULTILINE)
        source_match = re.search(r"^- Source:\s*(.+)$", text, flags=re.IGNORECASE | re.MULTILINE)
        if current_match and current_match.group(1).strip():
            cards.append(
                {
                    "source_name": document.path.name,
                    "claim": f"Current price: {current_match.group(1).strip()}",
                    "source": source_match.group(1).strip() if source_match else document.path.name,
                    "label": "market_data",
                    "metric": "current_price",
                    "value": current_match.group(1).strip(),
                    "could_change": "Market snapshot and valuation bridge",
                    "gap": "current price and market cap",
                    "confidence": "Medium",
                }
            )
    return cards


def web_card_category(card: dict[str, str]) -> str:
    text = " ".join(card.get(key, "") for key in ["metric", "gap", "could_change", "claim", "label"]).lower()
    if any(token in text for token in ["current_price", "current price", "market cap", "quote"]):
        return "market_snapshot"
    if any(token in text for token in ["risk", "disconfirm", "negative", "downgrade", "warning", "headwind"]):
        return "risk_check"
    if any(token in text for token in ["consensus", "target_price", "target price", "valuation", "multiple", "peer", "p/e", "pe"]):
        return "valuation_expectation"
    if any(token in text for token in ["result", "revenue", "eps", "margin", "guidance", "news", "event"]):
        return "official_or_news"
    return "other"


def web_evidence_impact(documents: list[SourceDocument]) -> dict[str, object]:
    cards = parse_web_evidence_cards(documents)
    brief_mode = ""
    for document in documents:
        if document.category != "web_research":
            continue
        match = re.search(r"^- Brief mode:\s*(.+)$", document.text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            brief_mode = match.group(1).strip()
            break
        has_price = bool(re.search(r"^- Current price:\s*\S+", document.text, flags=re.IGNORECASE | re.MULTILINE))
        accepted_zero = bool(re.search(r"^\s*- Source filter:\s*accepted=0\b", document.text, flags=re.IGNORECASE | re.MULTILINE))
        has_fallback_note = "LLM Fallback Note" in document.text
        if has_price and accepted_zero:
            brief_mode = "quote_only_fallback" if has_fallback_note else "market_context_only"
            break
    groups: dict[str, list[dict[str, str]]] = {
        "market_snapshot": [],
        "valuation_expectation": [],
        "official_or_news": [],
        "risk_check": [],
        "other": [],
    }
    for card in cards:
        groups.setdefault(web_card_category(card), []).append(card)

    def summarize(card: dict[str, str]) -> str:
        claim = card.get("claim") or card.get("value") or "accepted web evidence"
        source = card.get("source") or card.get("source_name") or "web"
        confidence = card.get("confidence")
        suffix = f"; confidence {confidence}" if confidence else ""
        return f"{short_text(claim, 120)} [{source}{suffix}]"

    impact = {
        "accepted_cards": len(cards),
        "brief_mode": brief_mode or "not_reported",
        "market_snapshot": [summarize(card) for card in groups["market_snapshot"][:2]],
        "valuation_expectation": [summarize(card) for card in groups["valuation_expectation"][:3]],
        "official_or_news": [summarize(card) for card in groups["official_or_news"][:3]],
        "risk_check": [summarize(card) for card in groups["risk_check"][:3]],
        "other": [summarize(card) for card in groups["other"][:2]],
    }
    if groups["valuation_expectation"]:
        impact["expectation_read"] = "Web evidence adds a market-expectation anchor; verify whether it is consensus, peer, or stale."
    elif brief_mode == "quote_only_fallback":
        impact["expectation_read"] = "Web input is quote-only fallback: price context updated, but official results and valuation evidence are still missing."
    elif groups["market_snapshot"]:
        impact["expectation_read"] = "Web evidence updates market price context, but does not prove expectation gap."
    elif cards:
        impact["expectation_read"] = "Web evidence adds context but not enough valuation/consensus evidence."
    else:
        impact["expectation_read"] = "No accepted web evidence entered the memo."
    return impact


def normalized_currency(unit: str | None, default: str | None = None) -> str | None:
    clean = (unit or "").strip()
    if not clean:
        return default
    lower = clean.lower()
    if lower in {"usd", "$", "us$"}:
        return "USD"
    if lower in {"cny", "rmb", "rmb/share"}:
        return "Rmb"
    if lower in {"hkd", "hk$"}:
        return "HKD"
    return clean


def extract_report_prices(documents: list[SourceDocument]) -> dict[str, str | float | None]:
    result: dict[str, str | float | None] = {
        "current_price": None,
        "current_price_source": None,
        "current_price_currency": None,
        "target_price": None,
        "target_price_source": None,
        "target_price_currency": None,
    }
    active_documents = [
        document
        for document in documents
        if document.category in {"web_research", "analyst_report"}
    ]
    for document in active_documents:
        text = document.text
        if document.category == "web_research":
            for card in parse_web_metric_cards(text):
                metric = card.get("metric", "").lower()
                value = parse_number(card.get("value", ""))
                if value is None:
                    continue
                source_detail = card.get("source") or document.path.name
                source = f"{document.path.name} ({source_detail})" if source_detail != document.path.name else document.path.name
                if metric == "current_price":
                    result["current_price"] = value
                    result["current_price_source"] = source
                    result["current_price_currency"] = normalized_currency(
                        card.get("unit"),
                        result.get("current_price_currency") if isinstance(result.get("current_price_currency"), str) else None,
                    )
                elif metric == "target_price":
                    result["target_price"] = value
                    result["target_price_source"] = source
                    result["target_price_currency"] = normalized_currency(
                        card.get("unit"),
                        result.get("target_price_currency") if isinstance(result.get("target_price_currency"), str) else None,
                    )
        current_patterns = [
            r"(?:current price|last price|share price|closing price|close|price).{0,80}?(?:Rmb|RMB|CNY|USD|HKD|\$)?\s*(\d+(?:\.\d+)?)",
            r"(?:Rmb|RMB|CNY|USD|HKD|\$)\s*(\d+(?:\.\d+)?).{0,60}?(?:current price|last price|share price|closing price|close)",
            r"600031(?:\.SS| CH)?[\s\S]{0,120}?Price:\s*(?:Rmb|RMB|CNY)\s*(\d+(?:\.\d+)?)",
            r"Sany Heavy Industry - A[\s\S]{0,180}?(?:CNY|Rmb|RMB)\s*(\d+(?:\.\d+)?)\s+OW",
        ]
        for pattern in current_patterns:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            if matches and result["current_price"] is None:
                result["current_price"] = float(matches[-1])
                result["current_price_source"] = document.path.name
                if result["current_price_currency"] is None:
                    if re.search(r"\bUSD\b|\$", text, flags=re.IGNORECASE):
                        result["current_price_currency"] = "USD"
                    elif re.search(r"\bHKD\b|HK\$", text, flags=re.IGNORECASE):
                        result["current_price_currency"] = "HKD"
                    elif re.search(r"\bCNY\b|\bRMB\b|Rmb", text, flags=re.IGNORECASE):
                        result["current_price_currency"] = "Rmb"
                    else:
                        result["current_price_currency"] = "Rmb"
        if document.category == "web_research":
            continue
        target_patterns = [
            r"600031(?:\.SS| CH)?[\s\S]{0,160}?Price Target:\s*(?:Rmb|RMB|CNY)\s*(\d+(?:\.\d+)?)",
            r"Sany Heavy Industry - A[\s\S]{0,240}?(?:Rmb|RMB|CNY)\s*(\d+(?:\.\d+)?)\s+(?:Dec|FY|n/c)",
            r"PT kept at Rmb(\d+(?:\.\d+)?)",
        ]
        for pattern in target_patterns:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            if matches:
                result["target_price"] = float(matches[-1])
                result["target_price_source"] = document.path.name
                if result["target_price_currency"] is None:
                    result["target_price_currency"] = "Rmb"
    return result


def evidence_patch_values(documents: list[SourceDocument]) -> dict[str, object]:
    merged: dict[str, object] = {}
    for document in documents:
        if document.category != "evidence_patch":
            continue
        try:
            data = json.loads(document.text)
        except json.JSONDecodeError:
            continue
        patch = data.get("evidence_patch", data)
        if isinstance(patch, dict):
            merged.update(patch)
            merged.setdefault("patch_source", document.path.name)
    return merged


def patch_float(values: dict[str, object], *keys: str) -> float | None:
    for key in keys:
        value = values.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            parsed = parse_number(value)
            if parsed is not None:
                return parsed
    return None


def is_placeholder_source(value: object) -> bool:
    return "placeholder" in str(value or "").lower()


def apply_evidence_patch(snapshot: FinancialSnapshot, documents: list[SourceDocument]) -> FinancialSnapshot:
    patch = evidence_patch_values(documents)
    if not patch:
        return snapshot

    patched: dict[str, object] = {}
    current_price = patch_float(patch, "current_price", "price")
    current_price_source = patch.get("current_price_source") or patch.get("price_source") or patch.get("patch_source") or "evidence_patch"
    if current_price is not None and not (snapshot.current_price is not None and is_placeholder_source(current_price_source)):
        patched["current_price"] = current_price
        patched["current_price_source"] = str(current_price_source)
        patched["current_price_currency"] = str(patch.get("current_price_currency") or patch.get("currency") or snapshot.current_price_currency or "Rmb")

    fcf_per_share = patch_float(patch, "fcf_per_share", "FCF_per_share")
    if fcf_per_share is not None:
        patched["fcf_per_share_latest"] = fcf_per_share

    source_pfcf = patch_float(patch, "source_pfcf", "P_FCF", "price_to_fcf")
    if source_pfcf is not None:
        patched["price_to_fcf_latest"] = source_pfcf

    target_price = patch_float(patch, "target_price", "target_price_external")
    if target_price is not None:
        patched["target_price"] = target_price
        patched["target_price_source"] = str(patch.get("target_price_source") or patch.get("patch_source") or "evidence_patch")
        patched["target_price_currency"] = str(patch.get("target_price_currency") or patch.get("currency") or snapshot.target_price_currency or "Rmb")

    eps_f1 = patch_float(patch, "eps_f1", "EPS_f1")
    if eps_f1 is not None:
        patched["eps_f1"] = eps_f1
    eps_f2 = patch_float(patch, "eps_f2", "EPS_f2")
    if eps_f2 is not None:
        patched["eps_f2"] = eps_f2

    return replace(snapshot, **patched) if patched else snapshot


def extract_financial_snapshot(documents: list[SourceDocument]) -> FinancialSnapshot:
    financial_documents = [document for document in documents if document.category == "financial_data"]
    if not financial_documents:
        prices = extract_report_prices(documents)
        snapshot = FinancialSnapshot(
            current_price=prices.get("current_price") if isinstance(prices.get("current_price"), float) else None,
            current_price_source=prices.get("current_price_source") if isinstance(prices.get("current_price_source"), str) else None,
            current_price_currency=prices.get("current_price_currency") if isinstance(prices.get("current_price_currency"), str) else None,
            target_price=prices.get("target_price") if isinstance(prices.get("target_price"), float) else None,
            target_price_source=prices.get("target_price_source") if isinstance(prices.get("target_price_source"), str) else None,
            target_price_currency=prices.get("target_price_currency") if isinstance(prices.get("target_price_currency"), str) else None,
        )
        return apply_evidence_patch(snapshot, documents)
    document = financial_documents[0]
    key_headers = find_header_row(document, "Key highlights") or find_header_row(document, "IS")
    latest_idx, f1_idx, f2_idx, latest_label, f1_label, f2_label = period_indices(key_headers)

    growth = find_first_financial_row(document, "Key highlights", ["Growth %, YoY", "Revenue Growth", "Revenue Growth %, YoY"])
    gross_margin = find_first_financial_row(document, "Key highlights", ["Margin %", "Gross Margin"])
    eps_growth = None
    seen_growth = 0
    for values in iter_sheet_rows(document, "Key highlights"):
        if values and values[0].strip().lower() == "growth %, yoy":
            seen_growth += 1
            if seen_growth == 2:
                eps_growth = values
                break

    fcf = find_first_financial_row(document, "Key highlights", ["Free Cash Flow", "FCF"])
    if not fcf:
        fcf = find_first_financial_row(document, "CF", ["Free Cash Flow", "FCF"])
    fcf_per_share = find_first_financial_row(document, "CF", ["Free Cash Flow per Basic Share", "FCF per Share"])
    eps = find_first_financial_row(document, "Key highlights", ["EPS, Adj", "EPS"])

    cf_headers = find_header_row(document, "CF")
    cf_latest_idx, _, _, _, _, _ = period_indices(cf_headers)
    price_to_fcf = find_first_financial_row(document, "CF", ["Price to Free Cash Flow", "P/FCF", "Price / FCF"])

    location_headers = find_header_row(document, "Locations Segments")
    location_latest_idx, _, _, _, _, _ = period_indices(location_headers)
    overseas = find_financial_row(document, "Locations Segments", "Overseas")
    overseas_share = find_row_after(document, "Locations Segments", "Overseas", "% of Total")
    overseas_gpm = find_row_after(document, "Locations Segments", "Gross Margin", "Overseas")
    domestic_gpm = find_row_after(document, "Locations Segments", "Gross Margin", "Mainland China")
    prices = extract_report_prices(documents)

    snapshot = FinancialSnapshot(
        source_name=document.path.name,
        latest_period=latest_label,
        forecast_period_1=f1_label,
        forecast_period_2=f2_label,
        revenue_growth_latest=cell_number(growth, latest_idx) if latest_idx is not None else None,
        revenue_growth_f1=cell_number(growth, f1_idx) if f1_idx is not None else None,
        revenue_growth_f2=cell_number(growth, f2_idx) if f2_idx is not None else None,
        gross_margin_latest=cell_number(gross_margin, latest_idx) if latest_idx is not None else None,
        gross_margin_f1=cell_number(gross_margin, f1_idx) if f1_idx is not None else None,
        gross_margin_f2=cell_number(gross_margin, f2_idx) if f2_idx is not None else None,
        eps_growth_latest=cell_number(eps_growth, latest_idx) if latest_idx is not None else None,
        eps_growth_f1=cell_number(eps_growth, f1_idx) if f1_idx is not None else None,
        eps_growth_f2=cell_number(eps_growth, f2_idx) if f2_idx is not None else None,
        fcf_latest=cell_number(fcf, latest_idx) if latest_idx is not None else None,
        fcf_per_share_latest=cell_number(fcf_per_share, cf_latest_idx) if cf_latest_idx is not None else None,
        price_to_fcf_latest=cell_number(price_to_fcf, cf_latest_idx) if cf_latest_idx is not None else None,
        eps_f1=cell_number(eps, f1_idx) if f1_idx is not None else None,
        eps_f2=cell_number(eps, f2_idx) if f2_idx is not None else None,
        current_price=prices.get("current_price") if isinstance(prices.get("current_price"), float) else None,
        current_price_source=prices.get("current_price_source") if isinstance(prices.get("current_price_source"), str) else None,
        current_price_currency=prices.get("current_price_currency") if isinstance(prices.get("current_price_currency"), str) else None,
        target_price=prices.get("target_price") if isinstance(prices.get("target_price"), float) else None,
        target_price_source=prices.get("target_price_source") if isinstance(prices.get("target_price_source"), str) else None,
        target_price_currency=prices.get("target_price_currency") if isinstance(prices.get("target_price_currency"), str) else None,
        overseas_revenue_latest=cell_number(overseas, location_latest_idx) if location_latest_idx is not None else None,
        overseas_share_latest=cell_number(overseas_share, location_latest_idx) if location_latest_idx is not None else None,
        overseas_gpm_latest=cell_number(overseas_gpm, location_latest_idx) if location_latest_idx is not None else None,
        domestic_gpm_latest=cell_number(domestic_gpm, location_latest_idx) if location_latest_idx is not None else None,
    )
    return apply_evidence_patch(snapshot, documents)


def fmt_pct(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}%"


def fmt_bn(value: float | None) -> str:
    return "n/a" if value is None else f"RMB {value / 1000:.1f}bn"


def fmt_price(value: float | None, currency: str | None = "Rmb") -> str:
    if value is None:
        return "n/a"
    label = currency or "Rmb"
    if label == "USD":
        return f"USD {value:.2f}"
    if label == "HKD":
        return f"HKD {value:.2f}"
    if label == "Rmb":
        return f"Rmb{value:.2f}"
    return f"{label} {value:.2f}"


def fmt_upside(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.0%}"

def probability_from_points(points: int, max_points: int) -> tuple[str, float]:
    if max_points <= 0:
        return "Low", 0.25
    ratio = points / max_points
    if ratio >= 0.75:
        return "High", 0.80
    if ratio >= 0.55:
        return "Medium-high", 0.65
    if ratio >= 0.35:
        return "Medium", 0.50
    return "Low", 0.25


def probability_from_score(score: float) -> str:
    if score >= 0.75:
        return "High"
    if score >= 0.60:
        return "Medium-high"
    if score >= 0.45:
        return "Medium"
    return "Low"


def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def valuation_reconciliation(snapshot: FinancialSnapshot) -> ValuationReconciliation:
    recalculated_pfcf = safe_divide(snapshot.current_price, snapshot.fcf_per_share_latest)
    source_pfcf = snapshot.price_to_fcf_latest
    fcf_yield = safe_divide(1.0, recalculated_pfcf)
    pe_f1 = safe_divide(snapshot.current_price, snapshot.eps_f1)
    pe_f2 = safe_divide(snapshot.current_price, snapshot.eps_f2)
    target_upside = None
    if snapshot.current_price and snapshot.target_price:
        target_upside = snapshot.target_price / snapshot.current_price - 1

    mismatch_pct = None
    conflict = False
    note = "Valuation inputs reconcile or are insufficient for a conflict test."
    confidence_cap = "High"
    if source_pfcf is not None and recalculated_pfcf is not None:
        denominator = abs(source_pfcf) if source_pfcf else 1.0
        mismatch_pct = abs(source_pfcf - recalculated_pfcf) / denominator
        if mismatch_pct > 0.15:
            conflict = True
            confidence_cap = "Medium"
            note = (
                f"Valuation conflict: source-file P/FCF {source_pfcf:.1f}x vs "
                f"price/FCF-share recalculated {recalculated_pfcf:.1f}x "
                f"({mismatch_pct:.0%} mismatch)."
            )
        else:
            note = f"P/FCF reconciles within 15%: source {source_pfcf:.1f}x vs recalculated {recalculated_pfcf:.1f}x."
    elif recalculated_pfcf is None and source_pfcf is not None:
        confidence_cap = "Medium"
        note = "Source-file P/FCF exists, but current price or FCF/share is missing; valuation confidence is capped."
    elif recalculated_pfcf is not None and source_pfcf is None:
        confidence_cap = "Medium-high"
        note = f"Only recalculated P/FCF is available: {recalculated_pfcf:.1f}x."
    elif pe_f1 is not None or pe_f2 is not None:
        confidence_cap = "Medium-high"
        pe_value = pe_f2 if pe_f2 is not None else pe_f1
        note = f"P/FCF unavailable; using forward P/E sanity check at {pe_value:.1f}x."

    return ValuationReconciliation(
        source_pfcf=source_pfcf,
        recalculated_pfcf=recalculated_pfcf,
        pfcf_mismatch_pct=mismatch_pct,
        fcf_yield=fcf_yield,
        pe_f1=pe_f1,
        pe_f2=pe_f2,
        target_upside=target_upside,
        conflict=conflict,
        confidence_cap=confidence_cap,
        note=note,
    )


def cap_confidence(label: str, cap: str) -> str:
    order = {"Low": 0, "Medium-low": 1, "Medium": 2, "Medium-high": 3, "High": 4}
    reverse = {value: key for key, value in order.items()}
    return reverse[min(order.get(label, 2), order.get(cap, 4))]


def valuation_signal(snapshot: FinancialSnapshot) -> tuple[str, float]:
    reconciliation = valuation_reconciliation(snapshot)
    if reconciliation.conflict:
        return reconciliation.note, -0.05

    pfcf = reconciliation.recalculated_pfcf or snapshot.price_to_fcf_latest
    if pfcf is None:
        pe = reconciliation.pe_f2 or reconciliation.pe_f1
        if pe is None:
            return "valuation data insufficient", 0.0
        if pe <= 18:
            return f"forward P/E {pe:.1f}x; valuation looks reasonable", 0.10
        if pe <= 28:
            return f"forward P/E {pe:.1f}x; valuation needs growth delivery", 0.0
        return f"forward P/E {pe:.1f}x; valuation already prices in optimism", -0.20
    if pfcf <= 10:
        return f"P/FCF {pfcf:.1f}x; cash-flow valuation looks attractive", 0.25
    if pfcf <= 16:
        return f"P/FCF {pfcf:.1f}x; valuation is reasonable but needs growth delivery", 0.05
    if pfcf <= 25:
        return f"P/FCF {pfcf:.1f}x; valuation already embeds optimism", -0.15
    return f"P/FCF {pfcf:.1f}x; cash-flow valuation looks expensive", -0.35


def root_driver_assessment(snapshot: FinancialSnapshot) -> dict[str, str]:
    """Assess the root driver behind observed financial signals.

    This is deliberately compact: the MVP does not run an industry-specific
    model yet, but it should still avoid stopping at surface growth.
    """

    tests: list[str] = []
    score = 0
    max_score = 0

    overseas_material = False
    if snapshot.overseas_share_latest is not None:
        max_score += 2
        if snapshot.overseas_share_latest >= 30:
            score += 2
            overseas_material = True
            tests.append(f"overseas revenue share is group-material at {fmt_pct(snapshot.overseas_share_latest)}")
        elif snapshot.overseas_share_latest >= 15:
            score += 1
            tests.append(f"overseas revenue share is emerging but not yet dominant at {fmt_pct(snapshot.overseas_share_latest)}")
        else:
            tests.append(f"overseas revenue share is still small at {fmt_pct(snapshot.overseas_share_latest)}")

    margin_premium = None
    if snapshot.overseas_gpm_latest is not None and snapshot.domestic_gpm_latest is not None:
        max_score += 2
        margin_premium = snapshot.overseas_gpm_latest - snapshot.domestic_gpm_latest
        if margin_premium >= 3:
            score += 2
            tests.append(f"overseas GPM premium is {margin_premium:.1f}ppt")
        elif margin_premium > 0:
            score += 1
            tests.append(f"overseas GPM premium is positive but modest at {margin_premium:.1f}ppt")
        else:
            tests.append("overseas GPM does not exceed domestic GPM")
    elif snapshot.gross_margin_latest is not None and snapshot.gross_margin_f2 is not None:
        max_score += 2
        margin_delta = snapshot.gross_margin_f2 - snapshot.gross_margin_latest
        if margin_delta >= 1:
            score += 2
            tests.append(f"group gross margin is forecast to improve by {margin_delta:.1f}ppt")
        elif margin_delta > 0:
            score += 1
            tests.append(f"group gross margin improves only modestly by {margin_delta:.1f}ppt")
        else:
            tests.append("group gross margin does not improve")

    if snapshot.eps_growth_f1 is not None or snapshot.revenue_growth_f1 is not None:
        max_score += 2
        eps_growth = snapshot.eps_growth_f1 or 0
        revenue_growth = snapshot.revenue_growth_f1 or 0
        if eps_growth >= 10 and eps_growth >= revenue_growth:
            score += 2
            tests.append(f"EPS growth {fmt_pct(snapshot.eps_growth_f1)} is double-digit and reaches the profit line")
        elif max(eps_growth, revenue_growth) >= 10:
            score += 1
            tests.append("growth is visible, but profit transmission needs confirmation")
        else:
            tests.append("growth is not yet large enough to prove group-level earnings change")

    if snapshot.fcf_latest is not None:
        max_score += 1
        if snapshot.fcf_latest > 0:
            score += 1
            tests.append(f"FCF is positive at {fmt_bn(snapshot.fcf_latest)}")
        else:
            tests.append("FCF is negative; earnings quality is not proven")

    ratio = score / max_score if max_score else 0.0
    if ratio >= 0.70:
        strength = "Medium-high"
        fair_value_sensitivity = "15-25%"
    elif ratio >= 0.45:
        strength = "Medium"
        fair_value_sensitivity = "10-15%"
    else:
        strength = "Low"
        fair_value_sensitivity = "<10% or unproven"

    if overseas_material or snapshot.overseas_gpm_latest is not None:
        driver = "Overseas expansion changes group earnings quality only if it is large, margin-accretive, repeatable, and cash-generative."
        root_risk = "overseas margin strength proves cyclical or mix-driven rather than structural."
        failure = "overseas growth slows below domestic growth, margin premium narrows, channel inventory rises, or cash conversion weakens."
    elif snapshot.gross_margin_f2 is not None:
        driver = "Margin improvement changes fair value only if it reflects structural pricing, mix, or operating leverage rather than temporary cost relief."
        root_risk = "margin improvement proves temporary and does not convert into EPS or FCF."
        failure = "gross margin rolls over, EPS growth decelerates, or FCF fails to follow earnings."
    else:
        driver = "The root driver is whether growth can become material group-level earnings and FCF improvement."
        root_risk = "growth remains narrative rather than material profit and cash-flow transmission."
        failure = "revenue growth fails to reach EPS/FCF, or valuation expands without financial confirmation."

    return {
        "driver": driver,
        "strength": strength,
        "score": f"{score}/{max_score}" if max_score else "0/0",
        "fair_value_sensitivity": fair_value_sensitivity,
        "materiality_read": "; ".join(tests[:4]) if tests else "Root-driver materiality cannot be quantified from current sources.",
        "root_risk": root_risk,
        "failure": failure,
    }


def valuation_anchor(snapshot: FinancialSnapshot) -> dict[str, float | str | None]:
    reconciliation = valuation_reconciliation(snapshot)
    if snapshot.current_price is None:
        return {"metric": None, "financial": None, "multiple": None, "source": "current price missing"}
    if snapshot.fcf_per_share_latest is not None:
        multiple = reconciliation.recalculated_pfcf or safe_divide(snapshot.current_price, snapshot.fcf_per_share_latest)
        return {
            "metric": "P/FCF",
            "financial": snapshot.fcf_per_share_latest,
            "multiple": multiple,
            "source": "current price / FCF per share",
        }
    eps = snapshot.eps_f2 if snapshot.eps_f2 is not None else snapshot.eps_f1
    if eps is not None:
        multiple = safe_divide(snapshot.current_price, eps)
        period = snapshot.forecast_period_2 if snapshot.eps_f2 is not None else snapshot.forecast_period_1
        return {
            "metric": "P/E",
            "financial": eps,
            "multiple": multiple,
            "source": f"current price / {period} EPS",
        }
    return {"metric": None, "financial": None, "multiple": None, "source": "EPS/FCF missing"}


def justified_multiple_read(snapshot: FinancialSnapshot) -> str:
    anchor = valuation_anchor(snapshot)
    root = root_driver_assessment(snapshot)
    metric = anchor["metric"]
    multiple = anchor["multiple"]
    if not metric or not isinstance(multiple, (int, float)):
        return "No justified multiple range; current price and EPS/FCF anchor are missing."
    if root["strength"] == "Medium-high":
        return (
            f"Observed {metric} is {multiple:.1f}x. A 10-20% premium to the current anchor is only justified if the root driver remains "
            "material, profitable, repeatable, and cash-generative."
        )
    if root["strength"] == "Medium":
        return (
            f"Observed {metric} is {multiple:.1f}x. Keep the justified range near the current anchor until materiality and sustainability improve."
        )
    return (
        f"Observed {metric} is {multiple:.1f}x, but root-driver evidence is weak; a discount or No Rating is more appropriate than a premium."
    )


def valuation_case_rows(snapshot: FinancialSnapshot, view: dict[str, str]) -> list[dict[str, str]]:
    anchor = valuation_anchor(snapshot)
    root = root_driver_assessment(snapshot)
    current = snapshot.current_price
    financial = anchor["financial"]
    multiple = anchor["multiple"]
    metric = anchor["metric"]
    if current is None or not isinstance(financial, (int, float)) or not isinstance(multiple, (int, float)) or not metric:
        return [
            {
                "case": "Data gap",
                "driver": root["driver"],
                "financial": str(anchor["source"]),
                "multiple": "n/a",
                "implied": "No valuation range.",
                "read": "Refresh current price, EPS/FCF, share count, fiscal year, and peer/history range.",
            }
        ]

    if root["strength"] == "Medium-high":
        bear_financial, bull_financial = 0.85, 1.20
        bear_multiple, bull_multiple = 0.85, 1.20
    elif root["strength"] == "Medium":
        bear_financial, bull_financial = 0.90, 1.12
        bear_multiple, bull_multiple = 0.90, 1.10
    else:
        bear_financial, bull_financial = 0.90, 1.05
        bear_multiple, bull_multiple = 0.85, 1.00

    cases = [
        (
            "Bear",
            f"Root driver fails: {root['root_risk']}",
            financial * bear_financial,
            multiple * bear_multiple,
            "Downside case; rating confidence should fall.",
        ),
        (
            "Base",
            "Root driver partly works; current evidence is the best estimate.",
            financial,
            multiple,
            "Current anchor; rating depends on whether the expectation gap is real.",
        ),
        (
            "Bull",
            "Root driver proves structural and market quality perception improves.",
            financial * bull_financial,
            multiple * bull_multiple,
            "Upside case; requires evidence, not only narrative.",
        ),
    ]
    rows: list[dict[str, str]] = []
    for case, driver, case_financial, case_multiple, read in cases:
        implied_price = case_financial * case_multiple
        implied_return = implied_price / current - 1
        rows.append(
            {
                "case": case,
                "driver": driver,
                "financial": f"{metric} financial anchor {fmt_price(case_financial)}",
                "multiple": f"{case_multiple:.1f}x {metric}",
                "implied": f"{fmt_price(implied_price)} / {fmt_upside(implied_return)}",
                "read": read,
            }
        )
    return rows


def rating_view(
    snapshot: FinancialSnapshot,
    metrics: dict[str, list[EvidenceSnippet]],
    documents: list[SourceDocument] | None = None,
) -> dict[str, str]:
    price_target = metric_item(metrics, "price_target")
    reconciliation = valuation_reconciliation(snapshot)
    root = root_driver_assessment(snapshot)
    web_impact = web_evidence_impact(documents or [])
    condition_scores: list[float] = []
    reasons: list[str] = []
    risks: list[str] = []

    growth_points = 0
    if snapshot.revenue_growth_f1 is not None:
        if snapshot.revenue_growth_f1 >= 10 and (snapshot.revenue_growth_f2 is None or snapshot.revenue_growth_f2 >= 10):
            growth_points += 2 if snapshot.revenue_growth_f2 is not None else 1
            second = f"/{fmt_pct(snapshot.revenue_growth_f2)}" if snapshot.revenue_growth_f2 is not None else ""
            reasons.append(f"Revenue forecast remains near double-digit: {fmt_pct(snapshot.revenue_growth_f1)}{second}")
        elif snapshot.revenue_growth_f1 <= 3 or (snapshot.revenue_growth_f2 is not None and snapshot.revenue_growth_f2 <= 3):
            risks.append("Revenue forecast is close to stagnation")
    if snapshot.eps_growth_f1 is not None:
        if snapshot.eps_growth_f1 >= 10 and (snapshot.eps_growth_f2 is None or snapshot.eps_growth_f2 >= 10):
            growth_points += 2 if snapshot.eps_growth_f2 is not None else 1
            second = f"/{fmt_pct(snapshot.eps_growth_f2)}" if snapshot.eps_growth_f2 is not None else ""
            reasons.append(f"EPS forecast growth: {fmt_pct(snapshot.eps_growth_f1)}{second}")
        elif snapshot.eps_growth_f1 < 0 or (snapshot.eps_growth_f2 is not None and snapshot.eps_growth_f2 < 0):
            risks.append("EPS forecast is declining")
    _, growth_probability = probability_from_points(growth_points, 4)
    condition_scores.append(growth_probability)

    margin_points = 0
    if snapshot.gross_margin_latest is not None and snapshot.gross_margin_f2 is not None:
        if snapshot.gross_margin_f2 > snapshot.gross_margin_latest:
            margin_points += 1
            reasons.append(f"Gross margin forecast improves from {fmt_pct(snapshot.gross_margin_latest)} to {fmt_pct(snapshot.gross_margin_f2)}")
        else:
            risks.append("Gross margin forecast does not improve")
    if snapshot.overseas_share_latest is not None and snapshot.overseas_gpm_latest is not None:
        if snapshot.overseas_share_latest >= 50 and (
            snapshot.domestic_gpm_latest is None or snapshot.overseas_gpm_latest > snapshot.domestic_gpm_latest
        ):
            margin_points += 1
            reasons.append(f"Overseas revenue share near {fmt_pct(snapshot.overseas_share_latest)} with higher overseas GPM")
    _, margin_probability = probability_from_points(margin_points, 2)
    condition_scores.append(margin_probability)

    cash_points = 0
    if snapshot.fcf_latest is not None:
        if snapshot.fcf_latest > 0:
            cash_points += 1
            reasons.append(f"{snapshot.latest_period} FCF {fmt_bn(snapshot.fcf_latest)}")
        else:
            risks.append("FCF is negative")
    if snapshot.price_to_fcf_latest is not None:
        if snapshot.price_to_fcf_latest <= 12:
            cash_points += 1
        elif snapshot.price_to_fcf_latest >= 25:
            risks.append("Cash-flow valuation is expensive")
    _, cash_probability = probability_from_points(cash_points, 2)
    condition_scores.append(cash_probability)

    thesis_probability = sum(condition_scores) / len(condition_scores) if condition_scores else 0.0
    if root["strength"] == "Medium-high":
        thesis_probability = max(thesis_probability, 0.62)
        reasons.append(f"Root driver materiality: {root['materiality_read']}")
    elif root["strength"] == "Low":
        thesis_probability = min(thesis_probability, 0.45)
        risks.append(f"Root driver weak: {root['materiality_read']}")
    valuation_text, valuation_adjustment = valuation_signal(snapshot)
    if reconciliation.conflict:
        risks.append(reconciliation.note)
    expectation_bonus = 0.0
    if reconciliation.target_upside is not None:
        if reconciliation.target_upside >= 0.20:
            expectation_bonus = 0.08
        elif reconciliation.target_upside <= -0.10:
            expectation_bonus = -0.08
    expected_edge = thesis_probability + valuation_adjustment + expectation_bonus

    has_valuation_anchor = (
        snapshot.price_to_fcf_latest is not None
        or reconciliation.recalculated_pfcf is not None
        or reconciliation.pe_f1 is not None
        or reconciliation.pe_f2 is not None
    )
    if snapshot.source_name is None or not has_valuation_anchor:
        rating = "No Rating"
        conclusion = "Forecast or valuation inputs are insufficient for a reliable Buy/Neutral/Sell call."
    elif expected_edge >= 0.75 and root["strength"] in {"Medium-high", "High"} and not reconciliation.conflict:
        rating = "Buy / Overweight"
        conclusion = "Root-driver thesis, valuation gap, and input reliability support a positive rating."
    elif expected_edge >= 0.45:
        rating = "Neutral"
        conclusion = "The thesis has merit, but valuation gap, materiality, or evidence reliability is not strong enough for Buy."
    else:
        if reasons:
            rating = "Neutral"
            conclusion = "Positive evidence exists, but valuation or missing root-driver transmission blocks a positive call."
        else:
            rating = "Sell / Underweight"
            conclusion = "Probability-weighted upside is not attractive versus downside risk."

    if price_target:
        reasons.append(f"External target-price entry: {short_text(price_target.text, 70)}")
    reasons.append(valuation_text)
    reasons.append(justified_multiple_read(snapshot))
    has_actionable_upside_anchor = bool(price_target or reconciliation.target_upside is not None)
    has_expectation_context = bool(has_actionable_upside_anchor or web_impact.get("valuation_expectation"))
    if rating.startswith("Buy") and not has_actionable_upside_anchor:
        rating = "Neutral"
        conclusion = "Root-driver and valuation evidence are positive, but Buy requires a proven market expectation gap or actionable valuation upside."
        risks.append("Buy blocked: market expectation gap is not yet proven to be investable.")
    base_confidence = probability_from_score(thesis_probability)
    rating_confidence = cap_confidence(base_confidence, reconciliation.confidence_cap)
    if not has_expectation_context:
        rating_confidence = cap_confidence(rating_confidence, "Medium-high")
        risks.append("No external target, consensus, or peer valuation anchor; market expectation gap must be independently verified.")
    elif web_impact.get("valuation_expectation") and not has_actionable_upside_anchor:
        rating_confidence = cap_confidence(rating_confidence, "Medium-high")
        risks.append("Web valuation anchor exists, but it must be reconciled with estimates, peer set, and price date before Buy.")
    if root["strength"] == "Low":
        rating_confidence = cap_confidence(rating_confidence, "Medium")
    if rating.startswith("Buy") and not has_actionable_upside_anchor:
        rating_confidence = cap_confidence(rating_confidence, "Medium")
        risks.append("Buy confidence capped because market expectation gap lacks an external/consensus anchor.")

    return {
        "rating": rating,
        "thesis_probability": f"{thesis_probability:.2f}",
        "thesis_probability_label": base_confidence,
        "rating_confidence": rating_confidence,
        "confidence_cap": reconciliation.confidence_cap,
        "valuation_conflict": "yes" if reconciliation.conflict else "no",
        "valuation_reconciliation": reconciliation.note,
        "expected_edge": f"{expected_edge:.2f}",
        "valuation_signal": valuation_text,
        "root_driver": root["driver"],
        "root_driver_strength": root["strength"],
        "root_driver_score": root["score"],
        "root_driver_materiality": root["materiality_read"],
        "fair_value_sensitivity": root["fair_value_sensitivity"],
        "justified_multiple_read": justified_multiple_read(snapshot),
        "conclusion": conclusion,
        "reasons": "; ".join(reasons[:4]) if reasons else "Quantified financial or valuation evidence is limited.",
        "risks": "; ".join(risks[:3]) if risks else "Main risk is failure of forecast delivery.",
    }


def market_assumption_tags(analyst_items: list[EvidenceSnippet]) -> list[str]:
    text = " ".join(item.text.lower() for item in analyst_items)
    tags: list[str] = []
    for token, label in [
        ("overseas", "overseas/globalization"),
        ("going global", "overseas/globalization"),
        ("electrification", "electrification"),
        ("aftermarket", "aftermarket"),
        ("mining", "mining/high-end products"),
        ("margin", "margin improvement"),
        ("cash", "cash-flow quality"),
    ]:
        if token in text and label not in tags:
            tags.append(label)
    return tags[:4]
    return tags[:4]
def build_thesis_rows(
    documents: list[SourceDocument],
    evidence: list[EvidenceSnippet],
    metrics: dict[str, list[EvidenceSnippet]],
    snapshot: FinancialSnapshot,
    view: dict[str, str],
) -> list[dict[str, str]]:
    refs = source_index(documents)
    revenue = factual_metric_item(metrics, "revenue")
    profit = factual_metric_item(metrics, "profit")
    margin = factual_metric_item(metrics, "gross_margin")
    cash_flow = factual_metric_item(metrics, "cash_flow")
    price_target = metric_item(metrics, "price_target")
    segment = evidence_item(evidence, "segment_or_product_mix", "annual_report")

    evidence_quality = []
    for label, item in [("Revenue", revenue), ("Profit", profit), ("Gross margin", margin), ("Cash flow", cash_flow)]:
        if item:
            evidence_quality.append(f"{label}: {short_text(item.text, 60)} [{source_ref(item, refs)}]")
    if segment:
        evidence_quality.append(f"Segment/product: {short_text(segment.text, 60)} [{source_ref(segment, refs)}]")
    quality_evidence = "<br>".join(evidence_quality[:3]) or "Financial or segment evidence is limited."

    financial_ref = refs.get(snapshot.source_name or "", snapshot.source_name or "financial data")
    quantitative_basis: list[str] = []
    if snapshot.revenue_growth_f1 is not None and snapshot.revenue_growth_f2 is not None:
        quantitative_basis.append(f"Revenue forecast: {fmt_pct(snapshot.revenue_growth_f1)}/{fmt_pct(snapshot.revenue_growth_f2)}")
    if snapshot.eps_growth_f1 is not None and snapshot.eps_growth_f2 is not None:
        quantitative_basis.append(f"EPS forecast: {fmt_pct(snapshot.eps_growth_f1)}/{fmt_pct(snapshot.eps_growth_f2)}")
    if snapshot.gross_margin_latest is not None and snapshot.gross_margin_f2 is not None:
        quantitative_basis.append(f"Gross margin: {fmt_pct(snapshot.gross_margin_latest)}->{fmt_pct(snapshot.gross_margin_f2)}")
    if snapshot.fcf_latest is not None and snapshot.price_to_fcf_latest is not None:
        quantitative_basis.append(f"FCF/PFCF: {fmt_bn(snapshot.fcf_latest)} / {snapshot.price_to_fcf_latest:.1f}x")
    quant_text = f"{'; '.join(quantitative_basis)} [{financial_ref}]" if quantitative_basis else quality_evidence

    rows = [
        {
            "thesis": "Rating thesis: revenue/EPS growth, margin direction, and cash conversion must jointly support the rating.",
            "judgement": view["rating"],
            "basis": quant_text,
            "disprove": "Revenue or EPS forecasts are revised down, margins roll over, or FCF fails to follow earnings.",
            "confidence": "Medium" if snapshot.source_name else "Low",
        },
        {
            "thesis": "Quality thesis: segment/product mix must translate into better margin or cash-flow quality.",
            "judgement": "Supports rating" if view["rating"].startswith("Buy") else "Needs verification",
            "basis": quality_evidence,
            "disprove": "High-quality segments lose mix share or growth relies on low-quality price competition.",
            "confidence": "Medium" if segment or margin or cash_flow else "Low",
        },
    ]
    if price_target:
        rows.append(
            {
                "thesis": "Valuation thesis: market re-rating must be backed by better growth, cash flow, or lower risk, not target price alone.",
                "judgement": "Watch item",
                "basis": f"External target-price entry: {short_text(price_target.text, 80)} [{source_ref(price_target, refs)}]",
                "disprove": "The assumptions behind the target price cannot be verified in financial data.",
                "confidence": "Low-medium",
            }
        )
    return rows


def bottom_line(company: str, view: dict[str, str], status: str) -> str:
    if not status.startswith("enough"):
        return f"{company}: directional judgement is possible, but key assumptions still need verification."
    if view["rating"].startswith("Buy"):
        if view.get("valuation_conflict") == "yes":
            return f"{view['rating']}, {view['rating_confidence']} confidence: thesis is positive, but valuation conflict caps conviction."
        return f"{view['rating']}, {view['rating_confidence']} confidence: thesis probability is {view['thesis_probability_label']} and {view['valuation_signal']}."
    if view["rating"] == "Neutral":
        return f"Neutral: thesis probability is {view['thesis_probability_label']}, but valuation or execution evidence is not strong enough for Buy."
    if view["rating"] == "No Rating":
        return f"No Rating: {view['conclusion']}"
    return f"{view['rating']}: upside evidence is not attractive enough versus risk; key issue is {view['risks']}."


def probability_label(score: int) -> str:
    if score >= 3:
        return "High"
    if score >= 2:
        return "Medium-high"
    if score >= 1:
        return "Medium"
    return "Low"


def core_thesis(company: str, snapshot: FinancialSnapshot, view: dict[str, str]) -> str:
    reconciliation = valuation_reconciliation(snapshot)
    root = root_driver_assessment(snapshot)
    valuation_line = ""
    if reconciliation.conflict:
        valuation_line = " but valuation confidence is capped until P/FCF inputs reconcile"
    elif reconciliation.recalculated_pfcf is not None:
        valuation_line = f" while recalculated P/FCF is {reconciliation.recalculated_pfcf:.1f}x"

    if view["rating"].startswith("Buy"):
        return f"{company}: {root['driver']} The stock works only if this can move group-level fair value by {root['fair_value_sensitivity']}{valuation_line}."
    if view["rating"] == "Neutral":
        return f"{company}: {root['driver']} Current evidence is {root['strength'].lower()} and does not yet prove enough valuation asymmetry{valuation_line}."
    return f"{company}: root-driver, cash-flow, or valuation support is insufficient for a positive risk-reward call."


def condition_rows(snapshot: FinancialSnapshot, refs: dict[str, str]) -> list[dict[str, str]]:
    source = refs.get(snapshot.source_name or "", snapshot.source_name or "financial data")
    rows: list[dict[str, str]] = []
    root = root_driver_assessment(snapshot)

    rows.append(
        {
            "condition": "Root driver is group-material, not a surface growth story.",
            "probability": root["strength"],
            "evidence": f"{root['materiality_read']} [{source}]",
            "break": root["failure"],
        }
    )

    margin_evidence = []
    if snapshot.gross_margin_latest is not None and snapshot.gross_margin_f2 is not None:
        margin_evidence.append(f"Gross margin {fmt_pct(snapshot.gross_margin_latest)}->{fmt_pct(snapshot.gross_margin_f2)}")
    if snapshot.overseas_share_latest is not None and snapshot.overseas_gpm_latest is not None:
        margin_evidence.append(f"Overseas share {fmt_pct(snapshot.overseas_share_latest)}; overseas GPM {fmt_pct(snapshot.overseas_gpm_latest)}")
        if snapshot.domestic_gpm_latest is not None:
            margin_evidence.append(f"Domestic GPM {fmt_pct(snapshot.domestic_gpm_latest)}")
    rows.append(
        {
            "condition": "Profitability improves earnings quality, not only revenue.",
            "probability": "Medium-high" if root["strength"] == "Medium-high" and margin_evidence else "Medium" if margin_evidence else "Low",
            "evidence": f"{'; '.join(margin_evidence)} [{source}]" if margin_evidence else "Segment or margin data missing.",
            "break": "Margin premium narrows, price competition rises, or forecast margin improvement fails to reach EPS.",
        }
    )

    cash_evidence = []
    reconciliation = valuation_reconciliation(snapshot)
    if snapshot.fcf_latest is not None:
        cash_evidence.append(f"{snapshot.latest_period} FCF {fmt_bn(snapshot.fcf_latest)}")
    if snapshot.price_to_fcf_latest is not None:
        cash_evidence.append(f"P/FCF {snapshot.price_to_fcf_latest:.1f}x")
    elif reconciliation.pe_f2 is not None or reconciliation.pe_f1 is not None:
        pe = reconciliation.pe_f2 if reconciliation.pe_f2 is not None else reconciliation.pe_f1
        cash_evidence.append(f"Forward P/E {pe:.1f}x; FCF data missing")
    rows.append(
        {
            "condition": "Valuation range is supported by cash flow or earnings, not target price alone.",
            "probability": "Medium-high" if cash_evidence and not reconciliation.conflict else "Medium" if cash_evidence else "Low",
            "evidence": f"{'; '.join(cash_evidence)} [{source}]" if cash_evidence else "FCF or valuation multiple missing.",
            "break": "FCF deteriorates, working capital worsens, or the multiple rises without cash-flow support.",
        }
    )
    return rows


def render_condition_table(rows: list[dict[str, str]]) -> list[str]:
    lines = [
        "| Thesis condition | Probability | Key evidence | Failure trigger |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| {row['condition']} | {row['probability']} | {row['evidence']} | {row['break']} |")
    return lines


def render_evidence_chain(rows: list[dict[str, str]]) -> list[str]:
    lines = ["| Driver | Evidence | Decision test | Failure line |", "| --- | --- | --- | --- |"]
    for row in rows:
        lines.append(f"| {row['condition']} | {row['evidence']} | {row['probability']} | {row['break']} |")
    return lines


def valuation_bridge_rows(snapshot: FinancialSnapshot, view: dict[str, str]) -> list[dict[str, str]]:
    reconciliation = valuation_reconciliation(snapshot)
    root = root_driver_assessment(snapshot)
    current = snapshot.current_price
    fcf_per_share = snapshot.fcf_per_share_latest
    if current is None or fcf_per_share is None:
        pe = reconciliation.pe_f2 or reconciliation.pe_f1
        if current is not None and pe is not None:
            rows = [
                {
                    "check": "Current valuation",
                    "input": f"Current price {fmt_price(current, snapshot.current_price_currency)}; EPS input available.",
                    "calculation": f"Forward P/E = {pe:.1f}x.",
                    "decision": justified_multiple_read(snapshot),
                    "next": "Collect FCF/share or FCF plus share count to test cash-flow valuation.",
                }
            ]
            rows.extend(case_row_to_bridge(row) for row in valuation_case_rows(snapshot, view))
            return rows
        rows = [
            {
                "check": "Data gap",
                "input": (
                    f"Current price {fmt_price(current, snapshot.current_price_currency)} is available; FCF/share missing."
                    if current is not None
                    else "Current price and FCF/share missing."
                ),
                "calculation": "n/a",
                "decision": "No valuation conclusion.",
                "next": "Refresh quote, share count, FCF definition, and fiscal year.",
            }
        ]
        rows.extend(case_row_to_bridge(row) for row in valuation_case_rows(snapshot, view))
        return rows
    observed_pfcf = reconciliation.recalculated_pfcf or current / fcf_per_share
    rows: list[dict[str, str]] = []

    base_read = f"Observed current valuation: P/FCF {observed_pfcf:.1f}x; FCF yield {fmt_upside(reconciliation.fcf_yield)}."
    if reconciliation.conflict:
        base_read += f" {reconciliation.note} Confidence is capped at {reconciliation.confidence_cap}."
    rows.append(
        {
            "check": "Current valuation",
            "input": f"Current price {fmt_price(current, snapshot.current_price_currency)}; FCF/share {fmt_price(fcf_per_share)}.",
            "calculation": f"Price / FCF per share = {observed_pfcf:.1f}x.",
            "decision": f"{base_read} {justified_multiple_read(snapshot)}",
            "next": f"Materiality test: {root['materiality_read']}",
        }
    )

    if snapshot.price_to_fcf_latest is not None:
        rows.append(
            {
                "check": "Source multiple",
                "input": f"Source-file P/FCF {snapshot.price_to_fcf_latest:.1f}x.",
                "calculation": f"Mismatch vs recalculated P/FCF: {fmt_upside(reconciliation.pfcf_mismatch_pct)}." if reconciliation.pfcf_mismatch_pct is not None else "Recalculation unavailable.",
                "decision": "Valuation confidence capped." if reconciliation.conflict else "No major P/FCF mismatch.",
                "next": "Reconcile price date, fiscal year, FCF definition, and share count.",
            }
        )

    if snapshot.target_price:
        implied_pfcf = snapshot.target_price / fcf_per_share
        implied_pe = snapshot.target_price / snapshot.eps_f2 if snapshot.eps_f2 else None
        bull_read = f"External target implies P/FCF {implied_pfcf:.1f}x"
        if implied_pe:
            bull_read += f" and forward P/E {implied_pe:.1f}x"
        bull_read += "; this is a sell-side market-view anchor, not our DCF."
        rows.append(
            {
                "check": "External target",
                "input": f"{fmt_price(snapshot.target_price, snapshot.target_price_currency)} from {snapshot.target_price_source or 'analyst report'}.",
                "calculation": f"Target upside {fmt_upside(snapshot.target_price / current - 1)}.",
                "decision": bull_read,
                "next": "Reverse-engineer assumptions before treating it as upside.",
            }
        )
    rows.extend(case_row_to_bridge(row) for row in valuation_case_rows(snapshot, view))
    return rows


def case_row_to_bridge(row: dict[str, str]) -> dict[str, str]:
    return {
        "check": row["case"],
        "input": row["driver"],
        "calculation": f"{row['financial']}; {row['multiple']}; implied {row['implied']}",
        "decision": row["read"],
        "next": "Use as a disciplined range, not a precise target price.",
    }


def rating_change_triggers(snapshot: FinancialSnapshot, view: dict[str, str]) -> list[str]:
    triggers: list[str] = []
    reconciliation = valuation_reconciliation(snapshot)
    root = root_driver_assessment(snapshot)
    source = snapshot.source_name or "financial data"
    triggers.append(
        f"Downgrade - root-driver materiality < Medium or failure evidence appears ({root['failure']}); source: {source}; linked thesis: {root['driver']}"
    )
    if snapshot.revenue_growth_f1 is not None and snapshot.revenue_growth_f2 is not None:
        floor = max(5.0, min(snapshot.revenue_growth_f1, snapshot.revenue_growth_f2) - 5.0)
        triggers.append(f"Downgrade - revenue growth < {floor:.1f}% or loses double-digit profile; source: {source}; linked thesis: growth exceeds expectations.")
    else:
        triggers.append("Watch - revenue growth threshold unavailable; source gap: forecast table missing.")

    if snapshot.eps_growth_f1 is not None and snapshot.eps_growth_f2 is not None:
        triggers.append("Downgrade - EPS growth turns negative or low-single-digit in either forecast year; linked thesis: operating leverage reaches earnings.")

    if snapshot.gross_margin_latest is not None and snapshot.gross_margin_f2 is not None:
        margin_floor = min(snapshot.gross_margin_latest, snapshot.gross_margin_f2) - 1.0
        triggers.append(f"Downgrade - gross margin < {fmt_pct(margin_floor)} or no longer improves vs latest actual; linked thesis: mix lifts margin.")

    if snapshot.fcf_latest is not None:
        triggers.append("Downgrade - FCF turns negative or OCF fails to track net profit; linked thesis: earnings quality converts to cash.")

    pfcf_anchor = reconciliation.recalculated_pfcf or snapshot.price_to_fcf_latest
    if pfcf_anchor is not None:
        neutral_line = max(16.0, pfcf_anchor + 4.0)
        sell_line = max(25.0, pfcf_anchor + 8.0)
        triggers.append(f"Cut confidence - P/FCF inputs mismatch >15% or P/FCF > {neutral_line:.1f}x without forecast upgrades; Sell risk > {sell_line:.1f}x.")

    if reconciliation.target_upside is not None:
        triggers.append(f"Watch - external target upside is {fmt_upside(reconciliation.target_upside)}; reassess if price closes most of this gap without estimate upgrades.")

    return triggers[:5]


def market_data_line(snapshot: FinancialSnapshot) -> str:
    if snapshot.current_price:
        source = snapshot.current_price_source or "source file"
        freshness = "web/file price; check retrieval date" if "web" in source.lower() else "non-real-time source price"
        return f"Current price {fmt_price(snapshot.current_price, snapshot.current_price_currency)} (source: {source}; {freshness})"
    return "Current price missing; valuation bridge needs quote refresh or user data."


def render_web_evidence_impact(impact: dict[str, object]) -> list[str]:
    if not impact.get("accepted_cards"):
        return ["- No accepted web evidence entered the memo."]
    rows: list[str] = []
    brief_mode = str(impact.get("brief_mode") or "").strip()
    if brief_mode and brief_mode != "not_reported":
        rows.append(f"- Brief mode: {brief_mode}")
    for label, key in [
        ("Market snapshot", "market_snapshot"),
        ("Valuation / expectation", "valuation_expectation"),
        ("Official / news update", "official_or_news"),
        ("Risk check", "risk_check"),
    ]:
        values = impact.get(key)
        if isinstance(values, list) and values:
            rows.append(f"- {label}: {values[0]}")
    if not rows:
        other = impact.get("other")
        if isinstance(other, list) and other:
            rows.append(f"- Other accepted evidence: {other[0]}")
    read = impact.get("expectation_read")
    if isinstance(read, str) and read:
        rows.append(f"- Investment read: {read}")
    return rows[:5]


def render_valuation_bridge(rows: list[dict[str, str]]) -> list[str]:
    lines = ["| Check | Input | Calculation | Decision read | Next action |", "| --- | --- | --- | --- | --- |"]
    for row in rows:
        lines.append(f"| {row['check']} | {row['input']} | {row['calculation']} | {row['decision']} | {row['next']} |")
    return lines


def render_thesis_table(rows: list[dict[str, str]]) -> list[str]:
    lines = [
        "| Thesis | Judgement | Evidence | Disproof | Confidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| {row['thesis']} | {row['judgement']} | {row['basis']} | {row['disprove']} | {row['confidence']} |")
    return lines


def render_notes(
    company: str,
    ticker: str | None,
    documents: list[SourceDocument],
    evidence: list[EvidenceSnippet],
    metrics: dict[str, list[EvidenceSnippet]],
    missing: list[str],
    status: str,
) -> str:
    analyst_reasoning = collect_analyst_reasoning(evidence)
    source_map = build_source_map(documents)
    lines = [
        f"# {company} Source Notes",
        "",
        "## Sources",
        "",
    ]
    for document in documents:
        lines.append(f"- {document.path.name} ({document.category})")

    lines.extend(["", "## Source Map", ""])
    lines.extend(render_source_map(source_map))

    lines.extend(["", "## Key Data", ""])
    for metric in ("current_price", "revenue", "profit", "gross_margin", "cash_flow", "debt_or_liquidity", "rating", "price_target"):
        items = metrics.get(metric, [])
        lines.append(f"### {bucket_title(metric)}")
        lines.extend(render_evidence_list(items, limit=3))
        lines.append("")

    lines.extend(["## Decision Evidence", ""])
    for bucket in ("business_description", "segment_or_product_mix", "financial_direction", "market_context", "recent_events", "top_risks", "valuation_context"):
        lines.append(f"### {bucket_title(bucket)}")
        bucket_items = items_for_bucket(evidence, bucket)
        lines.extend(render_evidence_list(bucket_items, limit=3))
        lines.append("")

    lines.extend(["## External Thesis Samples", ""])
    lines.extend(render_evidence_list(analyst_reasoning, limit=6))

    lines.extend(["", "## Missing / Next", ""])
    if missing:
        lines.extend(f"- {item}" for item in missing)
    else:
        lines.append("- Refresh valuation, forecast table, segment margin, and disconfirming evidence.")
    lines.extend(["", f"Status: {status}", ""])
    return "\n".join(lines).replace("\n\n\n", "\n\n")

def render_memo(
    company: str,
    ticker: str | None,
    documents: list[SourceDocument],
    evidence: list[EvidenceSnippet],
    metrics: dict[str, list[EvidenceSnippet]],
    missing: list[str],
    status: str,
    language: str,
) -> str:
    label = ticker or company
    snapshot = extract_financial_snapshot(documents)
    view = rating_view(snapshot, metrics, documents)
    confidence = view.get("rating_confidence", "Medium") if status.startswith("enough") else "Medium-low"
    if len(missing) > 4:
        confidence = "Low"
    confidence = cap_confidence(confidence, view.get("confidence_cap", "High"))
    official_count = source_count(documents, "annual_report")
    financial_count = source_count(documents, "financial_data")
    analyst_count = source_count(documents, "analyst_report")
    web_count = source_count(documents, "web_research")
    patch_count = source_count(documents, "evidence_patch")
    refs = source_index(documents)
    headline = bottom_line(company, view, status)
    conditions = condition_rows(snapshot, refs)
    valuation_rows = valuation_bridge_rows(snapshot, view)
    trigger_lines = rating_change_triggers(snapshot, view)
    research_plan = autonomous_research_plan(documents, evidence, metrics, snapshot)
    sufficiency_gate = source_sufficiency_gate(status, missing, snapshot)
    expectation = market_expectation_gap(snapshot, evidence, documents)
    web_impact = web_evidence_impact(documents)
    dcf_gate = dcf_readiness_gate(snapshot, view, expectation)
    source_line = f"official {official_count}; financial data {financial_count}; external views {analyst_count}; web {web_count}; patches {patch_count}"
    next_actions: list[str] = []
    next_actions.append(str(research_plan["next_tasks"][0]))
    if web_impact.get("brief_mode") == "quote_only_fallback":
        next_actions.append("Quote-only fallback: collect official CN filings/results from cninfo.com.cn or sse.com.cn before trusting web context.")
    if web_impact.get("risk_check"):
        next_actions.append("Verify web risk evidence and quantify rating impact.")
    elif not web_impact.get("valuation_expectation"):
        next_actions.append("Use Qwen/OpenRouter to collect accepted consensus or peer valuation evidence.")
    if dcf_gate["status"] == "Ask user":
        next_actions.append("Offer DCF / Excel model as next step.")
    else:
        next_actions.append(f"DCF: {dcf_gate['status']} - {dcf_gate['reason']}")
    if missing:
        next_actions.extend(missing[:2])
    next_actions = list(dict.fromkeys(next_actions))[:4]
    lines = [
        f"# {company} Research Memo",
        "",
        "## Rating",
        "",
        f"{view['rating']} | Confidence: {confidence} | Horizon: 6-12 months.",
        "",
        "## Bottom Line",
        "",
        f"{headline} Sources: {source_line}. Market data: {market_data_line(snapshot)}",
        "",
        "## Core Thesis",
        "",
        core_thesis(company, snapshot, view),
        "",
        "## Market Expectation Gap",
        "",
        f"Expectation gap: {expectation['status']}. {expectation['gap']}",
        "",
        "## Web Evidence Impact",
        "",
        *render_web_evidence_impact(web_impact),
        "",
        "## Thesis Conditions",
        "",
        *render_evidence_chain(conditions),
        "",
        "## Pre-DCF Valuation",
        "",
        *render_valuation_bridge(valuation_rows),
        "",
        "## Rating Triggers",
        "",
        *[f"- {item}" for item in trigger_lines[:4]],
        "",
        "## Key Risks",
        "",
        f"- Root risk: {root_driver_assessment(snapshot)['root_risk']}",
        f"- Rating risk: {view['risks']}",
        "",
        "## Next Action",
        "",
        *[f"- {item}" for item in next_actions],
    ]
    lines.append("")
    return "\n".join(lines).replace("\n\n\n", "\n\n")


def internal_self_check(
    status: str,
    missing: list[str],
    snapshot: FinancialSnapshot,
    view: dict[str, str],
    conditions: list[dict[str, str]],
    triggers: list[str],
) -> dict[str, object]:
    reconciliation = valuation_reconciliation(snapshot)
    root = root_driver_assessment(snapshot)
    thesis_gate_pass = all(
        row["evidence"] and "missing" not in row["evidence"].lower() and row["break"]
        for row in conditions
    )
    trigger_gate_pass = all(
        (" - " in item and ("<" in item or "turns" in item or "mismatch" in item or "upside" in item or "narrows" in item or "weakens" in item))
        for item in triggers
    )
    return {
        "status": status,
        "missing": missing,
        "root_driver": {
            "driver": root["driver"],
            "strength": root["strength"],
            "score": root["score"],
            "materiality_read": root["materiality_read"],
            "fair_value_sensitivity": root["fair_value_sensitivity"],
            "root_risk": root["root_risk"],
        },
        "valuation": {
            "source_pfcf": reconciliation.source_pfcf,
            "recalculated_pfcf": reconciliation.recalculated_pfcf,
            "pfcf_mismatch_pct": reconciliation.pfcf_mismatch_pct,
            "conflict": reconciliation.conflict,
            "confidence_cap": reconciliation.confidence_cap,
            "note": reconciliation.note,
        },
        "gates": {
            "valuation_reconciliation": not reconciliation.conflict,
            "thesis_transmission": thesis_gate_pass,
            "observable_triggers": trigger_gate_pass,
            "english_memo_only": True,
        },
        "decision": {
            "rating": view["rating"],
            "rating_confidence": view["rating_confidence"],
            "thesis_probability": view["thesis_probability_label"],
        },
    }


def render_summary_json(
    company: str,
    ticker: str | None,
    documents: list[SourceDocument],
    evidence: list[EvidenceSnippet],
    metrics: dict[str, list[EvidenceSnippet]],
    missing: list[str],
    status: str,
    market: str | None = None,
    web_mode: str = "auto",
    research_provider: str = "search",
    web_status: str | None = None,
) -> str:
    snapshot = extract_financial_snapshot(documents)
    view = rating_view(snapshot, metrics, documents)
    refs = source_index(documents)
    conditions = condition_rows(snapshot, refs)
    triggers = rating_change_triggers(snapshot, view)
    research_plan = autonomous_research_plan(documents, evidence, metrics, snapshot)
    sufficiency_gate = source_sufficiency_gate(status, missing, snapshot)
    expectation = market_expectation_gap(snapshot, evidence, documents)
    web_impact = web_evidence_impact(documents)
    dcf_gate = dcf_readiness_gate(snapshot, view, expectation)
    root = root_driver_assessment(snapshot)
    summary = {
        "request_contract": {
            "company": company,
            "ticker": ticker,
            "market": market,
            "source_files": [document.path.name for document in documents if document.category != "reference_sample"],
            "optional_user_request": True,
            "web_mode": web_mode,
            "research_provider": research_provider,
            "web_status": web_status,
            "output_depth": "standard",
        },
        "outputs": {
            "markdown_memo": f"{slugify(ticker or company)}-research-memo.md",
            "extracted_evidence_notes": f"{slugify(ticker or company)}-source-notes.md",
            "structured_json_summary": f"{slugify(ticker or company)}-summary.json",
            "internal_self_check_included": True,
        },
        "memo_summary": {
            "company": company,
            "ticker": ticker,
            "rating": view["rating"],
            "rating_confidence": view["rating_confidence"],
            "thesis_probability": view["thesis_probability_label"],
            "bottom_line": bottom_line(company, view, status),
            "market_snapshot": {
                "current_price": snapshot.current_price,
                "current_price_currency": snapshot.current_price_currency,
                "current_price_source": snapshot.current_price_source,
                "target_price": snapshot.target_price,
                "target_price_currency": snapshot.target_price_currency,
                "target_price_source": snapshot.target_price_source,
            },
            "core_thesis": core_thesis(company, snapshot, view),
            "root_driver": root,
            "valuation_cases": valuation_case_rows(snapshot, view),
            "research_plan": research_plan,
            "source_sufficiency_gate": sufficiency_gate,
            "market_expectation_gap": expectation,
            "web_evidence_impact": web_impact,
            "dcf_readiness": dcf_gate,
            "triggers": triggers,
        },
        "self_check": internal_self_check(status, missing, snapshot, view, conditions, triggers),
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


def needs_web_context(documents: list[SourceDocument], ticker: str | None) -> bool:
    if not ticker:
        return False
    if source_count(documents, "web_research") > 0:
        return False
    return True


def maybe_add_web_research(
    documents: list[SourceDocument],
    company: str,
    ticker: str | None,
    market: str | None,
    output_dir: Path,
    output_stem: str,
    web_mode: str,
    evidence_tasks: list[str] | None = None,
    research_provider: str = "search",
    timeout_seconds: int = 25,
) -> tuple[list[SourceDocument], str | None]:
    if web_mode == "off" or not needs_web_context(documents, ticker):
        return documents, None

    assert ticker is not None
    if web_mode == "auto":
        log_path = output_dir / f"{output_stem}-web-search-log.md"
        log_path.write_text(web_research_brief.render_query_plan(company, ticker, market, evidence_tasks), encoding="utf-8")
        return documents, f"web search log generated: {log_path.name}; not added to memo inputs"

    if web_mode != "online":
        return documents, f"unknown web mode ignored: {web_mode}"

    brief_path = output_dir / f"{output_stem}-web-research.md"
    try:
        web_research_brief.set_timeout_seconds(timeout_seconds)
        provider = research_provider
        if provider == "auto":
            provider = "llm" if web_research_brief.configured_llm_provider() else "search"
        if provider == "llm":
            cards, diagnostics = web_research_brief.collect_llm_evidence_cards(company, ticker, market, evidence_tasks or [])
            usable_cards = [card for card in cards if card.gate_status in {"accepted", "watch"}]
            if not usable_cards:
                quote = web_research_brief.fetch_market_snapshot(ticker, market)
                results = web_research_brief.collect_search_results(company, ticker, market, per_query=2, max_queries=2)
                if quote.price is None and not results:
                    fallback_path = output_dir / f"{output_stem}-web-search-log.md"
                    fallback_path.write_text(web_research_brief.render_query_plan(company, ticker, market, evidence_tasks), encoding="utf-8")
                    return documents, f"llm web brief had no valid evidence cards and quote/search fallback failed; search log generated: {fallback_path.name}; diagnostics={'; '.join(diagnostics[:2])}; quote_status={quote.status}"
                brief = web_research_brief.render_brief(
                    company,
                    ticker,
                    market,
                    quote,
                    results,
                    network_enabled=True,
                )
                diagnostics_text = "; ".join(diagnostics[:2])
                if diagnostics_text:
                    brief += f"\n## LLM Fallback Note\n\n- LLM evidence-card provider returned no usable cards; deterministic quote/search fallback used. Diagnostics: {diagnostics_text}\n"
            else:
                brief = web_research_brief.render_llm_brief(company, ticker, market, cards, diagnostics, evidence_tasks or [])
        else:
            quote = web_research_brief.fetch_market_snapshot(ticker, market)
            results = web_research_brief.collect_search_results(company, ticker, market, per_query=2, max_queries=2)
            if quote.price is None and not results:
                fallback_path = output_dir / f"{output_stem}-web-search-log.md"
                fallback_path.write_text(web_research_brief.render_query_plan(company, ticker, market, evidence_tasks), encoding="utf-8")
                return documents, f"web brief had no usable online facts; search log generated: {fallback_path.name}; quote_status={quote.status}"
            brief = web_research_brief.render_brief(
                company,
                ticker,
                market,
                quote,
                results,
                network_enabled=True,
            )
    except Exception as exc:  # noqa: BLE001
            fallback_path = output_dir / f"{output_stem}-web-search-log.md"
            fallback_path.write_text(web_research_brief.render_query_plan(company, ticker, market, evidence_tasks), encoding="utf-8")
            return documents, f"web brief failed; search log generated: {fallback_path.name}; error={exc}"

    brief_path.write_text(brief, encoding="utf-8")
    web_document = SourceDocument(
        path=brief_path,
        text=brief,
        source_type="md",
        category="web_research",
    )
    return [*documents, web_document], f"web research brief added to memo inputs: {brief_path.name}"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate MVP equity research notes and memo from a company source package."
    )
    parser.add_argument("--request", help="Natural-language request. MVP output is English-only.")
    parser.add_argument("--input", help="Path to a source file or a directory of source files. Defaults to inputs/.")
    parser.add_argument("--company", help="Company name. If omitted, the script tries a simple inference.")
    parser.add_argument("--ticker", help="Ticker or short company label for output filenames.")
    parser.add_argument("--market", help="Market hint for web context, e.g. US, CN, HK.")
    parser.add_argument("--language", default="EN", help="Report language label. MVP output is English-only.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for Markdown outputs.")
    parser.add_argument(
        "--market-provider",
        choices=("auto", "yahoo", "yfinance"),
        default="auto",
        help="Market data provider for online web mode. yfinance is optional and must already be installed locally.",
    )
    parser.add_argument(
        "--research-provider",
        choices=("search", "llm", "auto"),
        default="search",
        help="Online research provider: search=quote plus search leads, llm=privacy-gated evidence cards, auto=llm if configured else search.",
    )
    parser.add_argument(
        "--web-mode",
        choices=("off", "auto", "online"),
        default="auto",
        help="off=no web branch; auto=generate search log only when web context is missing; online=generate compact web brief and add it to the memo inputs.",
    )
    parser.add_argument(
        "--web-timeout-seconds",
        type=int,
        default=25,
        help="Timeout per web or LLM request. LLM web search providers may need longer than quote-only requests.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    inferred = infer_request_fields(args.request)
    input_value = args.input or str(DEFAULT_INPUT_DIR)
    input_path = Path(input_value).expanduser()
    if not input_path.is_absolute():
        input_path = (PROJECT_ROOT / input_path).resolve()
    if not input_path.exists():
        print(f"Input path not found: {input_path}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = (PROJECT_ROOT / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    documents = load_sources(input_path)
    company = args.company or inferred.get("company") or infer_company_name(documents, input_path.stem)
    ticker = args.ticker or inferred.get("ticker")
    language = "EN"
    output_stem = slugify(ticker or company)
    initial_evidence = collect_evidence(documents)
    initial_metrics = collect_metric_mentions(documents)
    initial_snapshot = extract_financial_snapshot(documents)
    initial_plan = autonomous_research_plan(documents, initial_evidence, initial_metrics, initial_snapshot)
    evidence_tasks = [str(item) for item in initial_plan.get("next_tasks", [])]
    web_research_brief.set_market_provider(args.market_provider)
    documents, web_status = maybe_add_web_research(
        documents,
        company,
        ticker,
        args.market,
        output_dir,
        output_stem,
        args.web_mode,
        evidence_tasks,
        args.research_provider,
        args.web_timeout_seconds,
    )

    evidence = collect_evidence(documents)
    metrics = collect_metric_mentions(documents)
    status, missing = sufficiency(documents, evidence, metrics)

    notes = render_notes(company, ticker, documents, evidence, metrics, missing, status)
    memo = render_memo(company, ticker, documents, evidence, metrics, missing, status, language)
    summary = render_summary_json(
        company,
        ticker,
        documents,
        evidence,
        metrics,
        missing,
        status,
        args.market,
        args.web_mode,
        args.research_provider,
        web_status,
    )
    quality = evaluate_quality(memo, json.loads(summary))

    notes_path = output_dir / f"{output_stem}-source-notes.md"
    memo_path = output_dir / f"{output_stem}-research-memo.md"
    summary_path = output_dir / f"{output_stem}-summary.json"
    quality_path = output_dir / f"{output_stem}-quality-score.json"
    notes_path.write_text(notes, encoding="utf-8")
    memo_path.write_text(memo, encoding="utf-8")
    summary_path.write_text(summary, encoding="utf-8")
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {notes_path}")
    print(f"Wrote {memo_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {quality_path}")
    if web_status:
        print(f"Web: {web_status}")
    print(f"Sources read: {len(documents)}")
    print(f"Sufficiency: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
