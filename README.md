# Reconciliation Agent

AI Finance Controller track
An AI-powered financial reconciliation system that matches transactions across two data sources, reasons about why exceptions happen, and decides which ones it can safely resolve on its own versus which ones need a human. Built with Python, pandas, an AI agent for exception handling and reasoning (Groq API, LLM inference), confidence-scored decision routing, and a Streamlit dashboard.

I built this the way I'd build anything meant to touch real money: keep the parts that can silently fail on numbers deterministic, and only let AI make judgment calls that can actually be checked.

Core idea: the AI proposes, deterministic code disposes. The model never touches a number, no matching, no totals, no amount comparisons. It only answers "why did this happen, and how sure am I." Matching and arithmetic are 100% plain, auditable pandas code. If an AI label is wrong, it's obvious on review. If an AI-computed number is wrong, it can sit quietly in a ledger for months. So the model stays away from numbers entirely.

## Results: with AI vs. without AI

Tested on 102 synthetic transactions (63 clean matches, 39 exceptions).

| Metric | Without AI (matching only) | With AI (agent + routing) |
|---|---|---|
| Overall automation rate | 61.8% | 99.0% |
| Exceptions auto-resolved | 0 of 39 (0%) | 38 of 39 (97.4%) |
| Exceptions needing human review | 39 of 39 (100%) | 1 of 39 (2.6%) |

That's a 37.3 percentage point gain in automation, and a direct, measured accuracy improvement from adding AI reasoning on top of deterministic matching.

Without AI, the matching engine can tell you that something's wrong, but not why, and not whether it's safe to resolve without a person looking. With the agent reasoning over each exception, 38 of 39 cases were confidently and safely auto-resolved. The one that wasn't, a ₹48,000 mismatch, was correctly routed to a human, because it failed two of the three safety checks (moderate confidence, and an amount above the risk threshold) even though the agent had a plausible explanation for it.

## Problem taste

Reconciliation, matching transactions between two systems that are supposed to agree and usually don't, is one of the most repetitive, error-prone jobs in finance operations. It doesn't scale by hiring more analysts, it scales by shrinking what actually needs one. The problem here isn't "detect mismatches," plain code already does that. It's figuring out, safely and measurably, which mismatches can be resolved without a human, and proving that number instead of just asserting it.

## Build quality

Every stage is its own module: data generation, deterministic matching, agent reasoning, routing, summary reporting, AI-impact comparison, and a dashboard. Not one script doing everything.

Every stage writes a plain CSV to `outputs/`, so any step can be inspected, re-run, or debugged on its own.

No hardcoded secrets. The API key lives in `.env`, which is gitignored, and I checked it never made it into version control.

The full pipeline runs end to end, unattended, on synthetic data: five commands, no manual steps in between.

Rate limiting and transient API failures are handled with retry-with-backoff instead of being left to crash the run.

## AI judgment

AI does exactly one job here: reason about why a flagged exception happened, and how confident that reasoning is. It's never used for matching, totals, or arithmetic of any kind. That stays in deterministic pandas code on purpose, because a wrong AI-computed number is a silent failure, while a wrong AI reason gets caught the moment someone reads it.

Even within its one job, the model doesn't get the final say. A case only auto-resolves if all three of these hold:

| Check | Threshold | Why it's there |
|---|---|---|
| Confidence | 80 or above | The model has to actually stand behind its own explanation |
| Transaction amount | Under ₹5,000 | A ₹15 rounding gap and a ₹40,000 gap aren't the same risk, even at equal confidence |
| Cited reason | Must be concrete, not "none" | If the model can't point to something specific, it doesn't get to act alone |

Fail any one of those and the case goes to human review instead, no exceptions. This mirrors how reconciliation automation actually runs in production at scale (HighRadius, Numeric): automate the confident majority, keep a human in the loop for anything genuinely uncertain or high-stakes.

## Failure recovery

The finished pipeline runs cleanly end to end now, but it didn't start that way. Four real problems came up along the way, two in the design and two in the infrastructure.

The routing logic almost shipped with a single point of failure. My first pass just checked one thing: was the model confident or not. That's an easy bug to miss, because a model can sound just as sure about a ₹15 rounding difference as it does about a ₹40,000 discrepancy. Confidence tells you how sure the reasoning is, not how expensive it would be if that reasoning is wrong. So I split the check into three: confidence, transaction size, and whether the model actually cited something concrete. All three have to clear before anything auto-resolves; otherwise it goes to a person.

Then there was a number that looked wrong but wasn't. I'd built the dataset to land around 75% clean matches, and the first full run came back at 61.8%. For a few minutes I assumed the matching logic had a bug. It didn't. About a dozen of the transactions were hand-built edge cases, deliberately skewed toward messy scenarios because their whole point was stress-testing specific failure types, not being a representative sample. Once I accounted for that, the number made sense. Nothing needed fixing except my assumption about what "correct" should look like.

The auto-resolve rate came back suspiciously high too. Thirty-eight of thirty-nine exceptions got auto-resolved, which is either a system working as intended or a system quietly rubber-stamping everything. I couldn't tell from the summary stats alone, so I went and checked the one case I'd specifically built to be risky, a ₹48,000 mismatch, by hand. It came back correctly routed to human review, and for the right reason. That one manual check is what turned "this looks fine" into "this is actually working."

The rest of the failures were plain infrastructure pain. `google-generativeai` hung forever on import under Python 3.14, somewhere down its dependency chain through grpc and protobuf, so I dropped the SDK and hit the REST endpoint directly with `requests` instead. That fixed the hang, but every call then came back `404`, which turned out to be two separate issues stacked together: a June 2026 key format change on Google's end, and a model version that had already been deprecated. After patching both and still hitting dead ends, I gave up on Gemini and moved to Groq, which uses a plainer, more stable API. Groq then rate-limited me 37 calls into a 39-call batch, so I added a short delay between requests and a retry with backoff for anything that came back `429`. None of these were interesting problems on their own, they were just the ordinary cost of building against real APIs instead of a spec sheet.

## Architecture

```
Inputs                     Deterministic layer            Agent layer (judgment)       Outputs
bank_records.csv     -->   Matching engine            -->  Reasoning agent        -->   resolved matches
company_records.csv        (exact-id + amount              (LLM, confidence             + audit trail
                             matching, no LLM,               score, may abstain)    -->   human-review queue
                             fully reproducible)                    ^                     (low confidence,
                        --> exceptions only ---------------  tools: fetch txn,            large amount, or
                                                              check status                 no clear reason)
                                                                                      -->   summary report
```

Only exceptions, missing entries, amount mismatches, duplicates, ever reach the agent. Clean matches never touch the model.

| File | Role |
|---|---|
| `src/generate_data.py` | Synthesizes bank and company records (100+ transactions) with deliberate, realistic mismatches: fee deductions, settlement delays, duplicates, partial refunds, rounding noise |
| `src/matching.py` | Deterministic matching engine (pandas merge). Classifies every transaction as a perfect match, missing entry, amount mismatch, or duplicate. No AI involved. |
| `src/agent.py` | The reasoning agent. Uses tool calls to fetch transaction details and check payment status, prompts an LLM for a structured JSON verdict (reason, confidence, cited rule), and applies the three-factor routing decision |
| `src/report.py` | Generates the summary report and an honest, itemized exception list |
| `src/compare_ai.py` | Produces the with-AI vs. without-AI automation rate comparison |
| `src/dashboard.py` | Streamlit dashboard with live metrics, the AI-impact chart, and a browsable breakdown of every auto-resolved and flagged case |

## Quickstart

```bash
pip install -r requirements.txt

python src/generate_data.py
python src/matching.py
python src/agent.py
python src/report.py
python src/compare_ai.py
streamlit run src/dashboard.py
```

Matching and reporting run fully offline. The agent step calls an LLM API, add `GROQ_API_KEY=...` to a `.env` file to run it live.

Tech stack: Python, pandas, Groq API for LLM inference, REST calls via `requests`, Streamlit, python-dotenv. Techniques used: deterministic rule-based matching, LLM-based reasoning with structured JSON output, tool-calling, confidence scoring, multi-factor human-in-the-loop routing, retry-with-backoff for rate limit resilience.

## Status

End to end pipeline complete and verified. Data generation, deterministic matching, AI-driven exception reasoning, confidence-based routing, reporting, AI-impact measurement, and dashboard visualization are all working, tested, and reproducible from a clean environment.