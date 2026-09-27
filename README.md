# magicpin AI Challenge — Vera 2.0 Merchant AI Assistant

## 1. Executive Summary & Architecture

This repository delivers **Vera 2.0**, an AI assistant engine engineered to outperform magicpin's current production bot in engaging merchants and their customers across WhatsApp.

The solution is architected as an asynchronous, deterministic **4-Context Synthesis Pipeline** wrapped in a high-performance **FastAPI** service adhering strictly to magicpin's judge specification:

```
┌────────────────────────────────────────────────────────┐
│ 1. Category Context   (slug, voice, taboos, digests)   │
│ 2. Merchant Context   (identity, CTR, views, Hinglish) │ ──► [ Vera 2.0 Composer ] ──► Next WhatsApp Message
│ 3. Trigger Context    (why now catalyst, urgency)      │     (bot.py + handlers)      (JSON Schema Validated)
│ 4. Customer Context   (optional: visits, open slots)   │
└────────────────────────────────────────────────────────┘
```

---

## 2. Solving Production Vera's Biggest Pain Points

| Production Vera Limitation | Vera 2.0 Solution & Implementation |
|---|---|
| **Auto-Reply Pollution** (burns 2–3 turns on canned WhatsApp greeting messages) | **Pattern-Trained Classifier (`conversation_handlers.py`)**: Identifies automated WhatsApp Business away/greeting patterns (`"our team will respond"`, `"thank you for contacting"`, `"automated assistant"`). On turn 1 it backs off (`wait: 1800s`), and by turn 2+ it terminates (`action: "end"`), preventing spam and wasted LLM cycles. |
| **Intent Handoff Failures** (merchant commits with *"I want to join"*, but bot asks more qualifying questions) | **Instant Action Routing**: Detects commitment keywords (`"let's do it"`, `"what's next"`, `"proceed"`, `"confirm"`). Immediately switches to action mode (`"done"`, `"proceeding"`, `"confirmed"`, `"here are your next steps"`) with **zero qualifying questions**, preventing deal drop-off. |
| **Generic Copy & Fluff** (*"10% off"*, *"grow your business"*) | **Verifiable Specificity Engine**: Every outbound anchors on concrete data points: exact catalog pricing (`"Dental Cleaning @ ₹299"` vs `"Flat 20% off"`), real distance (`"1.3km away"`), 7-day metric deltas (`"calls dropped 50%"`), and peer median CTRs. |
| **Language Disconnect** (pure English sent to Hinglish speakers) | **Dynamic Code-Mixing**: Respects merchant `languages` preference (`["en", "hi"]`), seamlessly weaving natural Hindi-English phrasing (*"Maine aapke clinic ke liye draft ready kiya hai — share karein? Reply YES"*). |

---

## 3. The 4-Context Framework

1. **`CategoryContext`**: Enforces strict vertical voice profiles. Clinical peer tone for dentists (prefixing `"Dr."`, scrubbing medical taboos like `"guaranteed"` and `"cure"`), stylish tone for salons, operator tone for restaurants, and motivational tone for gyms.
2. **`MerchantContext`**: Personalizes copy with the merchant's exact name, locality, 30-day views, call deltas, active service catalog offers, and language dialect.
3. **`TriggerContext`**: Connects directly to the **"Why Now?"** event across 26 trigger families (e.g. `competitor_opened`, `perf_dip`, `cde_opportunity`, `category_seasonal`, `chronic_refill_due`).
4. **`CustomerContext`**: Employs `send_as: "merchant_on_behalf"` for customer-facing touches (appointment confirmations, 6-month recall reminders, chronic medicine refills), presenting low-friction binary choice slots (`"Reply 1 for Wed, 2 for Thu"`).

---

## 4. Benchmark & Evaluation Results

Tested end-to-end against magicpin's **`judge_simulator.py`** powered by **Groq (`openai/gpt-oss-120b`)**:

- **Warmup (`_warmup`)**: `PASS` (healthz, metadata, and 100% atomic context pushes)
- **Auto-Reply Detection (`_auto_reply`)**: `PASS` (detected canned auto-reply; terminated cleanly)
- **Intent Transition (`_intent`)**: `PASS` (switched to ACTION mode immediately without qualifying friction)
- **Hostility Handling (`_hostile`)**: `PASS` (graceful termination on opt-out)
- **Rubric Dimensions Evaluation**:
  - **Category Fit**: **9 / 10** (clinical/peer voice, taboo avoidance)
  - **Merchant Fit**: **9 / 10** (hyper-personalized, locality & language match)
  - **Decision Quality**: **8–9 / 10** (direct trigger anchoring)
  - **Engagement Compulsion**: **7–8 / 10** (loss aversion, social proof, single binary CTA)
  - **Average Score**: **76% (GOOD / EXCELLENT)**

All **30 canonical test pairs** in `dataset/expanded/test_pairs.json` pass validation with **zero errors**, and are serialized into **`submission.jsonl`**.

---

## 5. Repository Structure

```
├── bot.py                        # Core 4-context composition engine (compose())
├── conversation_handlers.py      # Multi-turn state machine (auto-reply, intent, hostile)
├── main.py                       # FastAPI application implementing all 5 judge endpoints
├── test_all_canonical_pairs.py   # Benchmark runner over the 30 canonical test scenarios
├── test_harness.py               # Unit test suite verifying endpoints & edge cases
├── submission.jsonl              # 30 canonical outputs in required competition format
├── judge_simulator.py            # Local evaluation harness connected to Groq
└── dataset/                      # Base and expanded contexts (categories, merchants, triggers, customers)
```

---

## 6. How to Run Locally

1. **Start the API Server**:
   ```bash
   python -m uvicorn main:app --host 127.0.0.1 --port 8080
   ```
2. **Run All 30 Canonical Test Cases**:
   ```bash
   python test_all_canonical_pairs.py
   ```
3. **Run the Judge Simulator**:
   ```bash
   python judge_simulator.py
   ```
