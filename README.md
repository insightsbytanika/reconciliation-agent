# Reconciliation Agent

Razorpay AI Buildathon 2026 — AI Finance Controller track.

A small, runnable system that reconciles transactions between two data sources (e.g. bank records vs. internal company records), figures out *why* mismatches happen, and routes only genuinely uncertain cases to a human.

It's built around one rule:

> **The AI proposes; deterministic code disposes.** The model only ever makes *judgments* — why did this mismatch happen, how confident is that reasoning. Every *number* — matching, totals, amount comparisons — is plain, auditable pandas code. A wrong AI reason is easy to catch on review; a wrong AI-computed number can silently sit in the books for months. So numbers never go near the model.

This is a Buildathon submission, not a finished product — the goal is to show how a small piece of this problem gets solved end-to-end, including the part most demos skip: actually measuring whether the output is correct.

---

## Quickstart

```bash
pip install -r requirements.txt

python src/generate_data.py   # synthesize bank + company records with deliberate mismatches
python src/matching.py        # deterministic matching pass — no AI involved
python src/agent.py           # AI investigates exceptions, assigns confidence + routing
python src/evaluate.py        # accuracy + human-review rate
```

No API key needed to explore the repo — the matching stage runs fully offline. The agent stage uses a free-tier LLM API; add your key to a `.env` file (see `.env.example`) to run it live.

---

## Architecture

```
Inputs                     Deterministic layer            Agent layer (judgment)       Outputs
──────                     ────────────────────            ───────────────────────      ───────
bank_records.csv     ┌──►  Matching engine            ┌──►  Reasoning agent        ┌──►  resolved matches
company_records.csv ─┤     (exact-id + amount          │     (LLM, confidence      │     + audit trail
                      │      matching, no LLM,          │      score, may abstain)   ├──►  human-review queue
                      │      fully reproducible)        │            ▲              │     (low confidence /
                      └──►  exceptions only ────────────┘     tools: fetch txn,      │      large amount /
                                                                check status          │      no clear reason)
                                                                                       └──►  summary report
```

Only exceptions — missing entries, amount mismatches, duplicates — reach the agent. Clean matches never touch the model.

| File | Role |
|---|---|
| `src/generate_data.py` | Synthesizes bank + company records with deliberate, realistic mismatches (fees, delays, duplicates, partial refunds) |
| `src/matching.py` | Deterministic matching engine — classifies every transaction, no AI involved |
| `src/agent.py` | The reasoning agent — investigates exceptions using tools, cites a reason, assigns confidence |
| `src/router.py` | Decides auto-resolve vs. human review, based on confidence, amount, and whether a reason was found |
| `src/evaluate.py` | Measures match accuracy, human-review rate, and agent reasoning accuracy |

---

## Why route on more than just confidence

A model can be confident and still wrong, and some mistakes are more expensive than others. A case only auto-resolves if **all** of the following hold — otherwise it's queued for a human:

| Check | Why it's there |
|---|---|
| High confidence | The agent has to actually believe its own explanation |
| Amount below a risk threshold | A ₹20 rounding difference and a ₹40,000 gap aren't the same risk, even at equal confidence |
| A concrete reason was found | If the agent can't point to *something* specific, it doesn't get to act alone |

This isn't a novel idea — it's the same shape production reconciliation systems use at scale: automate the clear majority, keep a human in the loop for anything genuinely uncertain or high-stakes.

---

## What the evaluation shows

`python src/evaluate.py` reports, against known synthetic ground truth:

- **Matching accuracy** — the deterministic layer, so this is a correctness check, not a probability.
- **Agent reasoning accuracy** — how often the agent's stated reason for a mismatch was actually correct.
- **Auto-resolve rate** — what fraction of exceptions the agent could safely close on its own, vs. how many went to human review.

*(Results table gets filled in once the agent + evaluation stages are built.)*

---

## Status

Data generation and matching engine are done. Agent + routing layer in progress.