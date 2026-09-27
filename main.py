"""
main.py — FastAPI Application Implementing magicpin Challenge Judge API Spec
Exposes:
- GET  /v1/healthz
- GET  /v1/metadata
- POST /v1/context
- POST /v1/tick
- POST /v1/reply
"""

import os
import time
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import bot
import conversation_handlers

app = FastAPI(title="magicpin Vera AI Assistant", version="1.0.0")
START_TIME = time.time()

# Thread-safe in-memory stores for contexts and active conversations
# key: (scope, context_id) -> {"version": int, "payload": dict}
contexts: Dict[tuple, Dict[str, Any]] = {}
# key: conversation_id -> list of turn dicts
conversations: Dict[str, List[Dict[str, Any]]] = {}

# Paths for dataset fallbacks
BASE_DIR = Path(__file__).parent
DATASET_DIR = BASE_DIR / "dataset"
EXPANDED_DIR = DATASET_DIR / "expanded"

def load_fallback_context(scope: str, context_id: str) -> Optional[Dict[str, Any]]:
    """Fallback loader for offline execution or cold start tests."""
    if not context_id:
        return None
    # Check expanded directory first
    if EXPANDED_DIR.exists():
        if scope == "category":
            p = EXPANDED_DIR / "categories" / f"{context_id}.json"
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        elif scope == "merchant":
            p = EXPANDED_DIR / "merchants" / f"{context_id}.json"
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        elif scope == "customer":
            p = EXPANDED_DIR / "customers" / f"{context_id}.json"
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        elif scope == "trigger":
            p = EXPANDED_DIR / "triggers" / f"{context_id}.json"
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))

    # Fallback to seed files
    if scope == "category":
        p = DATASET_DIR / "categories" / f"{context_id}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    elif scope == "merchant":
        seed_p = DATASET_DIR / "merchants_seed.json"
        if seed_p.exists():
            d = json.loads(seed_p.read_text(encoding="utf-8"))
            for m in d.get("merchants", []):
                if m.get("merchant_id") == context_id:
                    return m
    elif scope == "customer":
        seed_p = DATASET_DIR / "customers_seed.json"
        if seed_p.exists():
            d = json.loads(seed_p.read_text(encoding="utf-8"))
            for c in d.get("customers", []):
                if c.get("customer_id") == context_id:
                    return c
    elif scope == "trigger":
        seed_p = DATASET_DIR / "triggers_seed.json"
        if seed_p.exists():
            d = json.loads(seed_p.read_text(encoding="utf-8"))
            for t in d.get("triggers", []):
                if t.get("id") == context_id:
                    return t

    return None


# =============================================================================
# 1. GET /v1/healthz
# =============================================================================
@app.get("/v1/healthz")
async def healthz():
    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    for (scope, _), _ in contexts.items():
        if scope in counts:
            counts[scope] += 1
    uptime = int(time.time() - START_TIME)
    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "contexts_loaded": counts
    }


# =============================================================================
# 2. GET /v1/metadata
# =============================================================================
@app.get("/v1/metadata")
async def metadata():
    return {
        "team_name": "Vera AI Candidate",
        "team_members": ["magicpin Participant"],
        "model": "4-context-hybrid-composer",
        "approach": "Hyper-personalized 4-context composition with Hinglish code-mix, automated away-reply classifier, and instantaneous intent transition",
        "contact_email": "candidate@magicpin.com",
        "version": "1.0.0",
        "submitted_at": datetime.now(timezone.utc).isoformat()
    }


# =============================================================================
# 3. POST /v1/context
# =============================================================================
class ContextRequest(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: Optional[str] = None

@app.post("/v1/context")
async def push_context(body: ContextRequest):
    key = (body.scope, body.context_id)
    cur = contexts.get(key)
    
    # Check for stale version conflict
    if cur and cur.get("version", 0) > body.version:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "accepted": False,
                "reason": "stale_version",
                "current_version": cur["version"]
            }
        )

    # Store or update context atomically
    contexts[key] = {
        "version": body.version,
        "payload": body.payload
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "accepted": True,
        "ack_id": f"ack_{body.context_id}_v{body.version}",
        "stored_at": now_iso
    }


# =============================================================================
# 4. POST /v1/tick
# =============================================================================
class TickRequest(BaseModel):
    now: Optional[str] = None
    available_triggers: List[str] = Field(default_factory=list)

@app.post("/v1/tick")
async def tick(body: TickRequest):
    actions = []

    for trg_id in body.available_triggers:
        # Retrieve trigger
        trg_ctx = contexts.get(("trigger", trg_id))
        trg = trg_ctx["payload"] if trg_ctx else load_fallback_context("trigger", trg_id)
        if not trg:
            continue

        merchant_id = trg.get("merchant_id")
        customer_id = trg.get("customer_id")

        # Retrieve merchant
        m_ctx = contexts.get(("merchant", merchant_id))
        merchant = m_ctx["payload"] if m_ctx else load_fallback_context("merchant", merchant_id)
        if not merchant:
            continue

        # Retrieve category
        cat_slug = merchant.get("category_slug") or trg.get("payload", {}).get("category", "dentists")
        cat_ctx = contexts.get(("category", cat_slug))
        category = cat_ctx["payload"] if cat_ctx else load_fallback_context("category", cat_slug)
        if not category:
            continue

        # Retrieve customer if scoped
        customer = None
        if customer_id:
            c_ctx = contexts.get(("customer", customer_id))
            customer = c_ctx["payload"] if c_ctx else load_fallback_context("customer", customer_id)

        # Compose using 4-context engine
        composed = bot.compose(category, merchant, trg, customer)

        m_name = merchant.get("identity", {}).get("name", "Merchant")
        actions.append({
            "conversation_id": f"conv_{merchant_id}_{trg_id}",
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": composed.get("send_as", "vera"),
            "trigger_id": trg_id,
            "template_name": f"vera_{trg.get('kind', 'generic')}_v1",
            "template_params": [m_name, trg.get("kind", ""), "update"],
            "body": composed.get("body", ""),
            "cta": composed.get("cta", "open_ended"),
            "suppression_key": composed.get("suppression_key", trg.get("suppression_key", "")),
            "rationale": composed.get("rationale", "")
        })

    return {"actions": actions}


# =============================================================================
# 5. POST /v1/reply
# =============================================================================
class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    from_role: str = "merchant"
    message: str
    received_at: Optional[str] = None
    turn_number: int = 1

@app.post("/v1/reply")
async def reply(body: ReplyRequest):
    # Record incoming turn
    history = conversations.setdefault(body.conversation_id, [])
    history.append({
        "role": body.from_role,
        "message": body.message,
        "turn": body.turn_number,
        "ts": body.received_at or datetime.now(timezone.utc).isoformat()
    })

    # Retrieve merchant context
    m_ctx = contexts.get(("merchant", body.merchant_id))
    merchant = m_ctx["payload"] if m_ctx else load_fallback_context("merchant", body.merchant_id)

    # Process reply with edge case intelligence
    response = conversation_handlers.handle_reply(
        conversation_id=body.conversation_id,
        merchant_id=body.merchant_id,
        customer_id=body.customer_id,
        from_role=body.from_role,
        message=body.message,
        turn_number=body.turn_number,
        history=history,
        merchant_context=merchant
    )

    # Record bot response
    history.append({
        "role": "bot",
        "action": response.get("action"),
        "body": response.get("body"),
        "ts": datetime.now(timezone.utc).isoformat()
    })

    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=False)
