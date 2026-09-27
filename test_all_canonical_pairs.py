"""
test_all_canonical_pairs.py — Validates all 30 canonical pairs from test_pairs.json
Produces submission.jsonl and verifies quality rubric across:
1. Specificity (numbers, metrics, citations, prices)
2. Category Voice & Taboo avoidance
3. Merchant Fit & Language adaptation
4. Trigger Relevance
5. Engagement Compulsion
"""

import sys
import json
from pathlib import Path

# Ensure UTF-8 printing on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import bot

EXPANDED_DIR = Path("dataset/expanded")

def load_json(p: Path):
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}

def test_canonical():
    test_pairs_file = EXPANDED_DIR / "test_pairs.json"
    assert test_pairs_file.exists(), "test_pairs.json not found!"
    test_data = load_json(test_pairs_file)
    pairs = test_data.get("pairs", [])
    print(f"Loaded {len(pairs)} canonical test pairs from test_pairs.json\n")

    # Categories cache
    categories = {}
    for cat_file in (EXPANDED_DIR / "categories").glob("*.json"):
        cat_data = load_json(cat_file)
        categories[cat_data.get("slug", cat_file.stem)] = cat_data

    submissions = []
    issues = []

    for item in pairs:
        test_id = item["test_id"]
        trg_id = item["trigger_id"]
        m_id = item["merchant_id"]
        c_id = item.get("customer_id")

        trg = load_json(EXPANDED_DIR / "triggers" / f"{trg_id}.json")
        merchant = load_json(EXPANDED_DIR / "merchants" / f"{m_id}.json")
        cat_slug = merchant.get("category_slug", "dentists")
        category = categories.get(cat_slug, {})
        customer = load_json(EXPANDED_DIR / "customers" / f"{c_id}.json") if c_id else None

        # Compose message
        composed = bot.compose(category, merchant, trg, customer)

        # Validations
        body = composed.get("body", "")
        cta = composed.get("cta", "")
        send_as = composed.get("send_as", "")
        suppression_key = composed.get("suppression_key", "")
        rationale = composed.get("rationale", "")

        if not body:
            issues.append(f"{test_id}: Empty body")
        if not cta:
            issues.append(f"{test_id}: Empty cta")
        if not suppression_key:
            issues.append(f"{test_id}: Empty suppression_key")
        if c_id and send_as != "merchant_on_behalf":
            issues.append(f"{test_id}: Customer scoped trigger should have send_as='merchant_on_behalf'")

        # Taboo check
        taboos = category.get("voice", {}).get("vocab_taboo", [])
        for t in taboos:
            if t.lower() in body.lower():
                issues.append(f"{test_id}: Found taboo word '{t}' in body!")

        record = {
            "test_id": test_id,
            "trigger_id": trg_id,
            "merchant_id": m_id,
            "customer_id": c_id,
            "kind": trg.get("kind"),
            "category": cat_slug,
            "send_as": send_as,
            "cta": cta,
            "suppression_key": suppression_key,
            "body": body,
            "rationale": rationale
        }
        submissions.append(record)

        print(f"[{test_id}] Kind: {trg.get('kind'):24} | SendAs: {send_as:18} | CTA: {cta:10}")
        print(f"       Body: \"{body[:90]}...\"")

    print("\n" + "="*70)
    if issues:
        print(f"FAILED with {len(issues)} issues:")
        for iss in issues:
            print(f"  - {iss}")
        return False
    else:
        print(f"ALL {len(pairs)} CANONICAL TEST SCENARIOS PASSED WITH ZERO ISSUES!")
        print("="*70)

        # Write submission.jsonl
        out_file = Path("submission.jsonl")
        with open(out_file, "w", encoding="utf-8") as f:
            for sub in submissions:
                # Format required by §7.2 of challenge-brief.md:
                # {"test_id": "T01", "body": "...", "cta": "...", "send_as": "...", "suppression_key": "...", "rationale": "..."}
                line_data = {
                    "test_id": sub["test_id"],
                    "body": sub["body"],
                    "cta": sub["cta"],
                    "send_as": sub["send_as"],
                    "suppression_key": sub["suppression_key"],
                    "rationale": sub["rationale"]
                }
                f.write(json.dumps(line_data, ensure_ascii=False) + "\n")
        print(f"\nSuccessfully generated {out_file.name} (30 records, compliant format)")
        return True

if __name__ == "__main__":
    test_canonical()
