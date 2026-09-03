# Reconciliation Agent

Built for the Razorpay AI Buildathon 2026 — AI Finance Controller track.

A small, runnable system that reconciles transactions between two data sources (bank records vs. internal company records), figures out *why* mismatches happen, and routes only genuinely uncertain cases to a human.

It's built around one rule:

> **The AI proposes; deterministic code disposes.** The model only ever makes *judgments* — why did this mismatch happen, how confident is that reasoning. Every *number* — matching, totals, amount comparisons — is plain, auditable pandas code. A wrong AI reason is easy to catch on review; a wrong AI-computed number can silently sit in the books for months. So numbers never go near the model.

Results

On 102 synthetic transactions (63 clean matches, 39 exceptions):

| Metric | Without AI | With AI |
|---|---|---|
| Overall automation rate | 61.8% | **99.0%** |
| Exceptions auto-resolved | 0 / 39 | 38 / 39 |

Without AI, the matching engine can only detect that something's wrong — every exception needs full manual investigation. With the agent reasoning about each exception, 38 of 39 were confidently and safely auto-resolved. The one exception that wasn't (a ₹48,000 mismatch) was correctly routed to human review — both because confidence was moderate and because the amount was large enough to warrant a second look regardless.

Quickstart

```bash
pip install -r requirements.txt

python src/generate_data.py   # synthesize bank + company records with deliberate mismatches
python src/matching.py        # deterministic matching pass — no AI involved
python src/agent.py           # AI investigates exceptions, assigns confidence + routing
python src/report.py          # summary report + honest exception list
python src/compare_ai.py      # with-AI vs without-AI comparison
```

Then, to view the results visually:
```bash
streamlit run src/dashboard.py
```

The matching and report stages run fully offline. The agent stage calls an LLM API — add your key to a `.env` file (`GROQ_API_KEY=...`) to run it live.

Architecture

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
| `src/agent.py` | The reasoning agent — investigates exceptions using tools, cites a reason, assigns confidence, and routes to auto-resolve or human review |
| `src/report.py` | Summary report and honest exception list |
| `src/compare_ai.py` | With-AI vs. without-AI comparison |
| `src/dashboard.py` | Streamlit dashboard for viewing results visually |

Why route on more than just confidence

A model can be confident and still wrong, and some mistakes are more expensive than others. A case only auto-resolves if **all** of the following hold — otherwise it's queued for a human:

| Check | Why it's there |
|---|---|
| High confidence (≥80) | The agent has to actually believe its own explanation |
| Amount below ₹5,000 | A small rounding difference and a large gap aren't the same risk, even at equal confidence |
| A concrete reason was found | If the agent can't point to *something* specific, it doesn't get to act alone |

This isn't a novel idea — it's the same shape production reconciliation systems use at scale (e.g. HighRadius, Numeric): automate the clear majority, keep a human in the loop for anything genuinely uncertain or high-stakes.


What Broke (Technical and Otherwise)

The finished pipeline looks clean. Getting there wasn't.

The design almost shipped with a single point of failure: confidence alone

The first version of the routing logic was simple — if the model says it's confident, auto-resolve it; if not, send it to a human. That's the obvious version, and it's wrong in a way that doesn't show up until you think about what "confident" actually protects against.

A model can be highly confident about a ₹15 rounding difference and equally confident about a ₹40,000 discrepancy — confidence measures how sure the model is about its *reasoning*, not how much is at stake if that reasoning is wrong. Auto-resolving both cases the same way means a single overconfident call on a large transaction sails through with no second look. That's the kind of bug that doesn't fail loudly; it fails quietly, once, on the transaction where it mattered most.

The fix was to stop treating "should this auto-resolve" as a single number and split it into three independent checks — confidence, transaction size, and whether the model could point to something concrete backing its answer. All three have to clear before anything resolves on its own. Anything else queues for a human. It's a small change in the code and a real change in what the system is allowed to get away with.

The match rate came out lower than expected, and that was almost treated as a bug

The synthetic dataset was built to be 75% clean matches by design. The first full run reported a 61.8% match rate. For a few minutes that looked like a bug in the matching logic — until the actual cause turned out to be simpler: the dataset is a mix of randomly generated volume (which *does* land near 75% clean) and a dozen hand-built edge cases that were deliberately skewed toward messy scenarios, because the point of hand-building them was to stress-test specific failure modes, not to be representative of the whole. The aggregate number was correct; the assumption about what it should look like was the thing that needed correcting.

Worth flagging on its own, because it's an easy trap: a number that doesn't match expectations isn't automatically a bug. Sometimes the expectation was measuring the wrong thing.

A 97.4% auto-resolve rate looked too good to trust

Once the agent was routing 38 of 39 exceptions to auto-resolve, the honest reaction wasn't relief — it was suspicion. A system that resolves almost everything on its own either means the routing logic is genuinely working, or it means the safety checks aren't actually doing anything and everything is quietly getting rubber-stamped.

The way to tell the difference was to go find the one case specifically engineered to be risky — a large-amount mismatch built into the dataset for exactly this reason — and check it by hand. It came back correctly flagged for human review, with the right stated reason (moderate confidence, amount over the risk threshold). That one check was the difference between "the number looks fine" and "the number is actually earned."

The infrastructure fought back on the way to a working API call

- **`google-generativeai` hung on import** on Python 3.14 — its dependency chain through `grpc` and `protobuf` never resolved, no error, just an indefinite hang. Dropped the SDK, called the REST endpoint directly with `requests` instead.
- **Every Gemini call 404'd**, even with a valid key — two compounding issues: Google's June 2026 key migration (`AIzaSy...` → `AQ.Ab...`) needed a different auth header, and separately, `gemini-2.0-flash` had been deprecated on June 1, 2026. Fixing the header and swapping models still didn't hold up, so the API was dropped mid-build in favor of Groq's more stable, OpenAI-compatible endpoint.
- **Groq's free tier rate-limited the run** 37 calls into a 39-call batch. Added a 2.5-second delay between calls and a 10s/20s/30s retry backoff on repeated 429s, so a burst of traffic slows the pipeline down instead of taking it out.

None of these were exotic problems. They were the ordinary tax of building against real APIs and real assumptions — the kind of thing that doesn't show up in a design doc, only in the process of actually running the thing.

Status
End-to-end pipeline complete: data generation, matching, agent reasoning, routing, reporting, comparison, and dashboard are all working.