"""
test_harness.py — Verification script for Phase 1 endpoints
Tests the exact scenarios that judge_simulator.py runs:
- Warmup (healthz, metadata, context push)
- Auto-reply detection
- Intent transition
- Hostility / Opt-out
- Tick composition
"""

import json
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8080"

def get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8")), resp.status

def post(path, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8")), e.code

def run_tests():
    print("=== 1. WARMUP ===")
    data, code = get("/v1/healthz")
    assert code == 200, f"healthz failed: {code}"
    print(f"[PASS] GET /v1/healthz: {data}")

    data, code = get("/v1/metadata")
    assert code == 200, f"metadata failed: {code}"
    print(f"[PASS] GET /v1/metadata: Team={data.get('team_name')}")

    print("\n=== 2. CONTEXT PUSH ===")
    cat_path = Path("dataset/categories/dentists.json")
    if cat_path.exists():
        cat_data = json.loads(cat_path.read_text(encoding="utf-8"))
        res, code = post("/v1/context", {
            "scope": "category",
            "context_id": "dentists",
            "version": 1,
            "payload": cat_data
        })
        assert code == 200 and res.get("accepted"), f"Push category failed: {res}"
        print(f"[PASS] Push category/dentists: {res.get('ack_id')}")

    m_data = {
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "category_slug": "dentists",
        "identity": {"name": "Dr. Meera's Dental Clinic", "owner_first_name": "Meera", "locality": "Lajpat Nagar", "city": "Delhi", "languages": ["en", "hi"]},
        "performance": {"views": 2410, "calls": 18, "ctr": 0.021, "delta_7d": {"views_pct": 0.18, "calls_pct": -0.05}},
        "offers": [{"id": "den_001", "title": "Dental Cleaning @ ₹299", "status": "active"}]
    }
    res, code = post("/v1/context", {
        "scope": "merchant",
        "context_id": "m_001_drmeera_dentist_delhi",
        "version": 1,
        "payload": m_data
    })
    assert code == 200 and res.get("accepted"), f"Push merchant failed: {res}"
    print(f"[PASS] Push merchant/m_001: {res.get('ack_id')}")

    # Test stale version rejection (409)
    res, code = post("/v1/context", {
        "scope": "merchant",
        "context_id": "m_001_drmeera_dentist_delhi",
        "version": 0,
        "payload": m_data
    })
    assert code == 409 and not res.get("accepted"), f"Expected 409 for stale version, got: {code}"
    print(f"[PASS] Stale version correctly rejected with 409: {res.get('reason')}")

    print("\n=== 3. AUTO-REPLY DETECTION ===")
    auto_reply_msg = "Thank you for contacting us! Our team will respond shortly."
    for turn in [1, 2]:
        res, code = post("/v1/reply", {
            "conversation_id": "conv_auto_test",
            "merchant_id": "m_001_drmeera_dentist_delhi",
            "customer_id": None,
            "from_role": "merchant",
            "message": auto_reply_msg,
            "turn_number": turn
        })
        print(f"  Turn {turn} auto-reply response: action={res.get('action')}, rationale={res.get('rationale')}")
        if turn == 2:
            assert res.get("action") in ["end", "wait"], f"Auto-reply turn 2 must end or wait: {res}"
            print("[PASS] Auto-reply successfully ended on turn 2!")

    print("\n=== 4. INTENT TRANSITION ===")
    intent_msg = "Ok lets do it. Whats next?"
    res, code = post("/v1/reply", {
        "conversation_id": "conv_intent_test",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": None,
        "from_role": "merchant",
        "message": intent_msg,
        "turn_number": 2
    })
    body = res.get("body", "")
    print(f"  Intent response: action={res.get('action')}")
    print(f"  Body: \"{body}\"")
    actioning = ["done", "sending", "draft", "here", "confirm", "proceed", "next"]
    qualifying = ["would you", "do you", "can you tell", "what if", "how about"]
    assert res.get("action") == "send", f"Expected send, got {res.get('action')}"
    assert any(w in body.lower() for w in actioning), "Missing action words in intent response"
    assert not any(w in body.lower() for w in qualifying), "Qualifying words forbidden in intent response"
    print("[PASS] Intent transition correctly entered action mode without qualifying questions!")

    print("\n=== 5. HOSTILE / OPT-OUT ===")
    hostile_msg = "Stop messaging me. This is useless spam."
    res, code = post("/v1/reply", {
        "conversation_id": "conv_hostile_test",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": None,
        "from_role": "merchant",
        "message": hostile_msg,
        "turn_number": 2
    })
    print(f"  Hostile response: action={res.get('action')}")
    assert res.get("action") == "end", f"Expected end on hostility, got {res.get('action')}"
    print("[PASS] Hostile opt-out correctly terminated conversation!")

    print("\n=== 6. TICK COMPOSITION ===")
    trg_data = {
        "id": "trg_001_research_digest_dentists",
        "scope": "merchant",
        "kind": "research_digest",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "payload": {
            "category": "dentists",
            "top_item_id": "d_2026W17_jida_fluoride",
            "top_item": {
                "title": "3-month fluoride recall cuts caries 38% better",
                "source": "JIDA Oct 2026, p.14",
                "trial_n": 2100
            }
        },
        "urgency": 2,
        "suppression_key": "research:dentists:2026-W17"
    }
    post("/v1/context", {
        "scope": "trigger",
        "context_id": "trg_001_research_digest_dentists",
        "version": 1,
        "payload": trg_data
    })
    res, code = post("/v1/tick", {
        "available_triggers": ["trg_001_research_digest_dentists"]
    })
    assert code == 200, f"Tick failed: {code}"
    actions = res.get("actions", [])
    assert len(actions) == 1, f"Expected 1 action, got {len(actions)}"
    action = actions[0]
    print(f"  Composed message body ({len(action['body'])} chars):")
    print(f"  \"{action['body']}\"")
    print(f"  CTA: {action['cta']}")
    print(f"  Send As: {action['send_as']}")
    print(f"  Rationale: {action['rationale']}")
    assert "JIDA" in action["body"] or "2100" in action["body"]
    print("[PASS] Tick successfully composed high-specificity action!")

    print("\n==========================================")
    print("ALL PHASE 1 BACKEND TESTS PASSED (100%)!")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
