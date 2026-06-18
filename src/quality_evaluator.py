"""Deterministic quality evaluator for MVP research memo outputs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def section_count(memo: str) -> int:
    return len(re.findall(r"^## ", memo, flags=re.MULTILINE))


def bullet_count(memo: str) -> int:
    return len(re.findall(r"^- ", memo, flags=re.MULTILINE))


def score_less_is_more(memo: str) -> tuple[int, list[str]]:
    issues: list[str] = []
    words = len(re.findall(r"\b\w+\b", memo))
    sections = section_count(memo)
    bullets = bullet_count(memo)
    score = 5
    if words > 900:
        score -= 1
        issues.append(f"Memo is long for MVP: {words} words.")
    if sections > 10:
        score -= 1
        issues.append(f"Too many sections for Less is More: {sections}.")
    if bullets > 18:
        score -= 1
        issues.append(f"Too many bullets: {bullets}.")
    repeated = len(re.findall(r"valuation conflict", memo, flags=re.I))
    if repeated > 4:
        score -= 1
        issues.append("Valuation conflict is repeated too often.")
    return max(score, 1), issues


def score_thesis_transmission(summary: dict[str, Any]) -> tuple[int, list[str]]:
    issues: list[str] = []
    gates = summary.get("self_check", {}).get("gates", {})
    memo_summary = summary.get("memo_summary", {})
    core = memo_summary.get("core_thesis", "")
    root = memo_summary.get("root_driver", {})
    score = 5
    if not gates.get("thesis_transmission"):
        score -= 2
        issues.append("Thesis transmission gate failed.")
    required = {
        "cash/earnings": ["fcf", "cash", "eps", "earnings"],
        "profitability": ["margin", "gpm", "profit", "earnings quality"],
        "valuation": ["valuation", "p/fcf", "pfcf", "multiple", "fair value"],
    }
    lower_core = f"{core} {json.dumps(root, ensure_ascii=False)}".lower()
    for label, tokens in required.items():
        if not any(token in lower_core for token in tokens):
            score -= 1
            issues.append(f"Core thesis lacks {label}.")
    if not root or root.get("strength") in {None, "Low"}:
        score -= 1
        issues.append("Root driver materiality is weak or missing.")
    gap = memo_summary.get("market_expectation_gap", {}).get("status", "")
    if not gap or "not proven" in gap.lower():
        score -= 1
        issues.append("Market expectation gap is weak or unproven.")
    return max(score, 1), issues


def score_valuation_discipline(summary: dict[str, Any], memo: str) -> tuple[int, list[str]]:
    issues: list[str] = []
    valuation = summary.get("self_check", {}).get("valuation", {})
    confidence = summary.get("memo_summary", {}).get("rating_confidence")
    dcf = summary.get("memo_summary", {}).get("dcf_readiness", {})
    valuation_cases = summary.get("memo_summary", {}).get("valuation_cases", [])
    score = 5
    if valuation.get("conflict") and confidence not in {"Medium", "Medium-low", "Low"}:
        score -= 3
        issues.append("Valuation conflict did not cap confidence.")
    if ("Bear |" in memo or "Base |" in memo or "Bull |" in memo) and not valuation_cases:
        score -= 2
        issues.append("Memo uses valuation cases without structured case support.")
    if "Pre-DCF Valuation" not in memo:
        score -= 1
        issues.append("Pre-DCF valuation section missing.")
    if dcf.get("status") == "Ask user" and valuation.get("conflict"):
        score -= 2
        issues.append("DCF readiness triggered despite valuation conflict.")
    return max(score, 1), issues


def score_trigger_quality(summary: dict[str, Any]) -> tuple[int, list[str]]:
    issues: list[str] = []
    triggers = summary.get("memo_summary", {}).get("triggers", [])
    score = 5
    if len(triggers) < 3:
        score -= 2
        issues.append("Too few rating triggers.")
    for trigger in triggers:
        lower = trigger.lower()
        has_action = any(action in lower for action in ["downgrade", "cut confidence", "watch", "upgrade"])
        has_threshold = any(token in trigger for token in ["<", ">", "%", "turns", "mismatch", "upside"])
        if not has_action or not has_threshold:
            score -= 1
            issues.append(f"Weak trigger: {trigger[:90]}")
    return max(score, 1), issues[:5]


def score_research_autonomy(summary: dict[str, Any]) -> tuple[int, list[str]]:
    issues: list[str] = []
    memo_summary = summary.get("memo_summary", {})
    plan = memo_summary.get("research_plan", {})
    sufficiency = memo_summary.get("source_sufficiency_gate", {})
    dcf = memo_summary.get("dcf_readiness", {})
    score = 5
    if not plan.get("next_tasks"):
        score -= 2
        issues.append("No next evidence task.")
    if "can_issue_rating" not in sufficiency:
        score -= 1
        issues.append("Source sufficiency gate missing.")
    if not dcf.get("status"):
        score -= 1
        issues.append("DCF readiness gate missing.")
    return max(score, 1), issues


def evaluate(memo_text: str, summary: dict[str, Any]) -> dict[str, Any]:
    categories = {
        "less_is_more": score_less_is_more(memo_text),
        "thesis_transmission": score_thesis_transmission(summary),
        "valuation_discipline": score_valuation_discipline(summary, memo_text),
        "trigger_quality": score_trigger_quality(summary),
        "research_autonomy": score_research_autonomy(summary),
    }
    scores = {name: result[0] for name, result in categories.items()}
    issues = {name: result[1] for name, result in categories.items() if result[1]}
    total = sum(scores.values())
    max_total = len(scores) * 5
    if total >= 23:
        verdict = "pass"
    elif total >= 18:
        verdict = "pass_with_watch_items"
    else:
        verdict = "fail"
    return {
        "verdict": verdict,
        "score": total,
        "max_score": max_total,
        "category_scores": scores,
        "failed_or_watch_items": issues,
        "next_improvement_target": next_improvement_target(scores, issues),
    }


def next_improvement_target(scores: dict[str, int], issues: dict[str, list[str]]) -> str:
    weakest = sorted(scores.items(), key=lambda item: item[1])[0][0]
    if weakest in issues and issues[weakest]:
        return issues[weakest][0]
    return f"Improve {weakest.replace('_', ' ')}."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate MVP research memo quality.")
    parser.add_argument("--memo", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    memo_path = Path(args.memo)
    summary_path = Path(args.summary)
    output_path = Path(args.output)
    result = evaluate(memo_path.read_text(encoding="utf-8"), load_json(summary_path))
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"Verdict: {result['verdict']} ({result['score']}/{result['max_score']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
