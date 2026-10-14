"""Scoring for the Ch05 eval: deterministic checks against ES|QL ground truth, plus an LLM judge.

Ground truth is computed from the Precision Labs indices at scoring time (S02 depends on
today's date: "renewing in the next 60 days"). Each check returns a dict with pass/fail,
a 0-1 score and the evidence, so a learner can see exactly why a run passed or failed.

Judge: an EIS completion endpoint called through the Elasticsearch _inference API, so the
same judge runs in every sandbox with no extra credentials. It is a different model family
from the agents (Gemini), and it is given the ground truth (reference-guided judging).
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

from common import Env

JUDGE_ENDPOINT = ".anthropic-claude-5-sonnet-completion"

CATEGORY_WORDS = {
    "bug": ["bug"],
    "integration": ["integration"],
    "api": ["api"],
    "performance": ["performance", "latency", "slow"],
    "billing": ["billing", "invoice"],
    "onboarding": ["onboarding"],
    "feature_request": ["feature request", "feature_request"],
    "data_quality": ["data quality", "data_quality"],
}


def _q(s: str) -> str:
    return '"' + s.replace('"', '\\"') + '"'


def _mentioned(answer: str, accounts: list[dict]) -> list[str]:
    """Accounts named in the answer, by customer_id or exact company name."""
    low = answer.lower()
    hits = []
    for a in accounts:
        if a["customer_id"].lower() in low or a["company_name"].lower() in low:
            hits.append(f'{a["company_name"]} ({a["customer_id"]})')
    return hits


def _categories_mentioned(answer: str, cats: list[str]) -> list[str]:
    low = answer.lower()
    return [c for c in cats if any(re.search(rf"\b{re.escape(w)}", low) for w in CATEGORY_WORDS.get(c, [c]))]


def _kb_mentioned(answer: str, kb: list[dict]) -> list[str]:
    low = answer.lower()
    return [k["article_id"] for k in kb
            if k["article_id"].lower() in low or k["title"].lower() in low]


def _with_ties(rows: list[dict], k: int, field: str) -> list[dict]:
    """Top k rows by `field`, extended to include anything tied with the k-th value."""
    if len(rows) <= k:
        return rows
    cut = rows[k - 1][field]
    return [r for r in rows if r[field] >= cut - 1e-6]


class GroundTruth:
    def __init__(self, env: Env, today: date | None = None):
        self.env = env
        self.today = today or date.today()
        self._kb = None

    def kb(self) -> list[dict]:
        if self._kb is None:
            self._kb = self.env.esql("FROM precision-kb-articles | KEEP article_id, title, category | LIMIT 1000")
        return self._kb

    def facts(self, scenario: str) -> dict:
        return getattr(self, f"_facts_{scenario}")()

    # S01: highest-churn Enterprise accounts + what they call about
    def _facts_s01(self) -> dict:
        ent = self.env.esql(
            'FROM precision-crm-accounts | WHERE account_tier == "Enterprise" '
            "| SORT churn_risk_score DESC | KEEP customer_id, company_name, churn_risk_score | LIMIT 50")
        top = _with_ties(ent, 5, "churn_risk_score")

        def cats_for(accts):
            ids = ", ".join(_q(a["customer_id"]) for a in accts)
            return self.env.esql(
                f"FROM precision-support-tickets | WHERE account_id IN ({ids}) "
                "| STATS n = COUNT(*) BY category | SORT n DESC")
        cats = cats_for(top)
        return {"note": "The question does not fix how many accounts to list; any top-N (3-15) that follows "
                        "the churn ranking is acceptable. Category counts depend on N; judge the ranking, not exact counts.",
                "top_accounts": top, "ranking_top15": ent[:15],
                "top_categories": [c["category"] for c in cats[:3]],
                "category_counts_top5_with_ties": cats, "category_counts_top10": cats_for(ent[:10])}

    # S02: Enterprise renewing in 60 days with open P1 (critical) tickets + KB coverage
    def _facts_s02(self) -> dict:
        start, end = self.today.isoformat(), (self.today + timedelta(days=60)).isoformat()
        accts = self.env.esql(
            'FROM precision-crm-accounts | WHERE account_tier == "Enterprise" '
            f'AND renewal_date >= "{start}" AND renewal_date <= "{end}" '
            "| KEEP customer_id, company_name, renewal_date, churn_risk_score | LIMIT 500")
        if not accts:
            return {"window": [start, end], "accounts": [], "ticket_categories": []}
        ids = ", ".join(_q(a["customer_id"]) for a in accts)
        tix = self.env.esql(
            f'FROM precision-support-tickets | WHERE account_id IN ({ids}) AND priority == "critical" '
            'AND status IN ("open", "in_progress") '
            "| KEEP account_id, status, category, ticket_id | LIMIT 1000")
        strict_ids = {t["account_id"] for t in tix if t["status"] == "open"}
        loose_ids = {t["account_id"] for t in tix}
        by_acct = {}
        for t in tix:
            by_acct.setdefault(t["account_id"], set()).add(f'{t["category"]} ({t["status"]})')
        return {"note": "'Open P1' = priority critical. Strict reading: status open; a broader reading also "
                        "counts in_progress. Either reading is acceptable if applied consistently.",
                "window": [start, end],
                "open_p1_categories_by_account": {k: sorted(v) for k, v in by_acct.items()},
                "kb_catalogue": self.kb(),
                "accounts": [a for a in accts if a["customer_id"] in strict_ids],
                "accounts_incl_in_progress": [a for a in accts if a["customer_id"] in loose_ids],
                "ticket_categories": sorted({t["category"] for t in tix if t["status"] == "open"})}

    # S03: accounts with open P1 tickets and high churn risk
    def _facts_s03(self) -> dict:
        open_p1 = self.env.esql(
            'FROM precision-support-tickets | WHERE priority == "critical" AND status == "open" '
            "| STATS n = COUNT(*) BY account_id | LIMIT 1000")
        ids = ", ".join(_q(r["account_id"]) for r in open_p1)
        accts = self.env.esql(
            f"FROM precision-crm-accounts | WHERE customer_id IN ({ids}) "
            "| SORT churn_risk_score DESC | KEEP customer_id, company_name, churn_risk_score, account_tier | LIMIT 500")
        ip = self.env.esql(
            'FROM precision-support-tickets | WHERE priority == "critical" AND status IN ("open", "in_progress") '
            "| STATS n = COUNT(*) BY account_id | LIMIT 1000")
        ip_ids = ", ".join(_q(r["account_id"]) for r in ip)
        accts_ip = self.env.esql(
            f"FROM precision-crm-accounts | WHERE customer_id IN ({ip_ids}) AND churn_risk_score >= 0.6 "
            "| SORT churn_risk_score DESC | KEEP customer_id, company_name, churn_risk_score | LIMIT 500")
        return {"accounts_with_open_or_in_progress_p1_churn_ge_0_6": accts_ip,
                "note": "'High churn risk' has no fixed threshold; an answer may pick a cutoff (e.g. >=0.7 or >=0.8) "
                        "but must not skip accounts above its own cutoff. 'Open' may or may not include in_progress.",
                "top_accounts": _with_ties(accts, 5, "churn_risk_score"),
                "all_accounts_with_open_p1_ranked": accts, "n_accounts_with_open_p1": len(accts)}

    # S04: what the KB says about the top ticket categories
    def _facts_s04(self) -> dict:
        cats = self.env.esql("FROM precision-support-tickets | STATS n = COUNT(*) BY category | SORT n DESC")
        kbc = self.env.esql("FROM precision-kb-articles | STATS n = COUNT(*) BY category | SORT n DESC")
        return {"top_categories": [c["category"] for c in cats[:3]], "ticket_category_counts": cats,
                "kb_category_counts": kbc, "kb_catalogue": self.kb(),
                "note": "KB categories do not map 1:1 to ticket categories (e.g. there is no 'bug' KB category). "
                        "Saying a category has thin or no KB coverage is correct, not a failure."}

    # S05 (single-index control): top Enterprise accounts by ARR + their owners
    def _facts_s05(self) -> dict:
        ent = self.env.esql(
            'FROM precision-crm-accounts | WHERE account_tier == "Enterprise" | SORT arr DESC '
            "| KEEP customer_id, company_name, arr, account_owner | LIMIT 15")
        return {"note": "Single-index question: only precision-crm-accounts is needed. arr is annual recurring "
                        "revenue in USD. Any top-N (3-15) that follows the ARR ranking is acceptable.",
                "top_accounts": _with_ties(ent, 5, "arr"), "ranking_top15": ent}

    # ── deterministic checks ────────────────────────────────────────────────
    def check(self, scenario: str, answer: str, facts: dict) -> dict:
        checks = []
        if scenario == "s01":
            hits = _mentioned(answer, facts["top_accounts"])
            checks.append({"name": "names >=3 of the top-5 churn Enterprise accounts (ties incl.)",
                           "pass": len(hits) >= 3, "evidence": hits})
            cats = _categories_mentioned(answer, facts["top_categories"])
            checks.append({"name": f"names >=2 of their top-3 ticket categories {facts['top_categories']}",
                           "pass": len(cats) >= 2, "evidence": cats})
        elif scenario == "s02":
            gold = facts["accounts"]
            hits = _mentioned(answer, facts.get("accounts_incl_in_progress", gold))
            need = max(1, (len(gold) + 1) // 2)
            checks.append({"name": f"names >=half of the {len(gold)} renewing accounts with open P1s",
                           "pass": len(hits) >= need if gold else True, "evidence": hits})
            kb = _kb_mentioned(answer, self.kb())
            checks.append({"name": "cites >=1 real KB article (id or exact title)",
                           "pass": len(kb) >= 1, "evidence": kb[:10]})
        elif scenario == "s03":
            hits = _mentioned(answer, facts["top_accounts"])
            checks.append({"name": "names >=3 of the top-5 churn accounts with open P1s (ties incl.)",
                           "pass": len(hits) >= 3, "evidence": hits})
        elif scenario == "s05":
            hits = _mentioned(answer, facts["top_accounts"])
            checks.append({"name": "names >=3 of the top-5 Enterprise accounts by ARR (ties incl.)",
                           "pass": len(hits) >= 3, "evidence": hits})
            owners = sorted({a["account_owner"] for a in facts["top_accounts"]
                             if a["account_owner"].lower() in answer.lower()})
            checks.append({"name": "names the owner of at least 1 of them", "pass": len(owners) >= 1,
                           "evidence": owners})
        elif scenario == "s04":
            cats = _categories_mentioned(answer, facts["top_categories"])
            checks.append({"name": f"names >=2 of the top-3 ticket categories {facts['top_categories']}",
                           "pass": len(cats) >= 2, "evidence": cats})
            kb = _kb_mentioned(answer, self.kb())
            low = answer.lower()
            kb_cats = sorted({k["category"] for k in self.kb() if re.search(rf"\b{re.escape(k['category'])}", low)})
            checks.append({"name": "grounds the answer in the KB: >=1 real article or >=2 real KB categories",
                           "pass": len(kb) >= 1 or len(kb_cats) >= 2, "evidence": kb[:10] + kb_cats})
        passed = sum(c["pass"] for c in checks)
        return {"checks": checks, "score": round(passed / len(checks), 2), "pass": passed == len(checks)}


JUDGE_PROMPT = """You are grading an AI agent's answer to a business question about Precision Labs customer-success data.
You are given the question, the agent's answer, and GROUND TRUTH computed directly from the data with ES|QL.
Judge only against the ground truth and the question. Do not reward length or formatting.
Rules:
- Penalize statements that CONTRADICT the ground truth (wrong accounts, wrong ranking, invented KB article ids/titles).
- Do NOT penalize details the ground truth cannot confirm or deny (e.g. what a KB article says); treat them as neutral.
- Do NOT penalize count differences that follow from a reasonable interpretation described in the ground truth notes.
- The deterministic checks below already verified which accounts, categories and KB ids the answer names.

QUESTION:
{question}

GROUND TRUTH (JSON):
{facts}

DETERMINISTIC CHECKS (JSON):
{checks}

AGENT ANSWER:
{answer}

Score:
- correctness (1-5): are the facts in the answer consistent with the ground truth? Penalize wrong accounts, wrong numbers, invented KB articles.
- completeness (1-5): does it answer every part of the question?
Return ONLY a JSON object, no prose, no code fence:
{{"correctness": <1-5>, "completeness": <1-5>, "reason": "<one sentence>"}}"""

JUDGE_VERSION = "v3"


def judge(env: Env, question: str, answer: str, facts: dict, checks: list | None = None,
          endpoint: str = JUDGE_ENDPOINT) -> dict:
    prompt = JUDGE_PROMPT.format(question=question, facts=json.dumps(facts, default=str)[:24000],
                                 checks=json.dumps(checks or [], default=str), answer=answer[:8000])
    r = env.es_("POST", f"/_inference/completion/{endpoint}", {"input": prompt}, timeout=180)
    text = r["completion"][0]["result"]
    m = re.search(r"\{.*\}", text, re.S)
    try:
        out = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        out = {}
    out["judge_model"] = endpoint
    out["judge_version"] = JUDGE_VERSION
    try:
        # verdict is derived from the scores, not left to the model: pass = correctness >=4 and completeness >=3
        out["verdict"] = "pass" if int(out["correctness"]) >= 4 and int(out["completeness"]) >= 3 else "fail"
    except (KeyError, TypeError, ValueError):
        out.update({"verdict": "error", "reason": text[:300]})
    return out


# ── How each question is scored (shown on the dashboard; keep in sync with GroundTruth) ──
QUESTIONS_INDEX = "ce-eval-questions"
JUDGE_RUBRIC = ("LLM judge (Claude Sonnet 5 via the Elasticsearch _inference API) reads the question, the answer, "
                "the ground-truth rows and the check results. It scores correctness and completeness 1-5 and only "
                "penalizes statements that contradict the ground truth. Correct = all checks pass AND "
                "correctness >= 4 AND completeness >= 3.")
SCORING_EXPLAINED = {
    "s01": {
        "truth_esql": 'FROM precision-crm-accounts\n| WHERE account_tier == "Enterprise"\n| SORT churn_risk_score DESC\n'
                      '| KEEP customer_id, company_name, churn_risk_score\n| LIMIT 10\n\n'
                      '// then, for the top 5 (ties included):\nFROM precision-support-tickets\n'
                      '| WHERE account_id IN (<top accounts>)\n| STATS tickets = COUNT(*) BY category\n| SORT tickets DESC',
        "checks": ["Names at least 3 of the top-5 churn-risk Enterprise accounts (ties included)",
                   "Names at least 2 of those accounts' top-3 ticket categories"],
        "notes": "How many accounts to list is not fixed; any top-N that follows the churn ranking is accepted."},
    "s02": {
        "truth_esql": 'FROM precision-crm-accounts\n| WHERE account_tier == "Enterprise"\n'
                      '  AND renewal_date >= NOW() AND renewal_date <= NOW() + 60 days\n'
                      '| KEEP customer_id, company_name, renewal_date\n\n'
                      '// then:\nFROM precision-support-tickets\n| WHERE account_id IN (<renewing accounts>)\n'
                      '  AND priority == "critical" AND status == "open"\n| STATS open_p1 = COUNT(*) BY account_id, category',
        "checks": ["Names at least half of the renewing Enterprise accounts that have open P1 (critical) tickets",
                   "Cites at least 1 real KB article (id or exact title)"],
        "notes": "Computed at scoring time (depends on today's date). Counting in_progress tickets as open is also accepted."},
    "s03": {
        "truth_esql": 'FROM precision-support-tickets\n| WHERE priority == "critical" AND status == "open"\n'
                      '| STATS open_p1 = COUNT(*) BY account_id\n\n'
                      '// then:\nFROM precision-crm-accounts\n| WHERE customer_id IN (<accounts with open P1s>)\n'
                      '| SORT churn_risk_score DESC\n| KEEP customer_id, company_name, churn_risk_score\n| LIMIT 5',
        "checks": ["Names at least 3 of the top-5 churn-risk accounts that have open P1 tickets (ties included)"],
        "notes": "'High churn risk' has no fixed threshold; an answer may pick one but must not skip accounts above it."},
    "s04": {
        "truth_esql": 'FROM precision-support-tickets\n| STATS tickets = COUNT(*) BY category\n| SORT tickets DESC\n| LIMIT 3\n\n'
                      '// and the KB side:\nFROM precision-kb-articles\n| STATS articles = COUNT(*) BY category',
        "checks": ["Names at least 2 of the top-3 ticket categories",
                   "Grounds the answer in the KB: at least 1 real article, or 2 real KB categories"],
        "notes": "KB categories do not map 1:1 to ticket categories (there is no 'bug' KB category); saying so is correct."},
    "s05": {
        "truth_esql": 'FROM precision-crm-accounts\n| WHERE account_tier == "Enterprise"\n| SORT arr DESC\n'
                      '| KEEP customer_id, company_name, arr, account_owner\n| LIMIT 5',
        "checks": ["Names at least 3 of the top-5 Enterprise accounts by ARR (ties included)",
                   "Names the owner of at least 1 of them"],
        "notes": "Single-index control question: one index, no join. Compare its cut with the cross-index questions."},
}


def write_question_docs(env: Env, scenarios: dict):
    """scenarios: {sid: (label, question)}; writes one explainer doc per question."""
    try:
        env.es_("PUT", f"/{QUESTIONS_INDEX}", {"mappings": {"properties": {
            "scenario": {"type": "keyword"}, "label": {"type": "keyword"}, "question": {"type": "keyword"},
            "truth_esql": {"type": "keyword", "ignore_above": 8000}, "checks": {"type": "keyword"},
            "notes": {"type": "keyword"}, "judge": {"type": "keyword", "ignore_above": 2000},
            "kind": {"type": "keyword"}}}})
    except RuntimeError as e:
        if "resource_already_exists" not in str(e):
            raise
    for sid, (label, question) in scenarios.items():
        x = SCORING_EXPLAINED[sid]
        env.es_("PUT", f"/{QUESTIONS_INDEX}/_doc/{sid}", {
            "scenario": sid, "label": label, "question": question, "truth_esql": x["truth_esql"],
            "checks": x["checks"], "notes": x["notes"], "judge": JUDGE_RUBRIC, "kind": "eval"})
    env.es_("POST", f"/{QUESTIONS_INDEX}/_refresh")
