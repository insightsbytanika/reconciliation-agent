# Reconciliation Agent

AI Finance Controller track.

Most reconciliation tools can tell you that two numbers don't match. Almost none of them can tell you why, or whether it's safe to fix that mismatch without a person looking at it first. That gap is what this project is actually about, and this README walks through how it got built, what it does well, and exactly where it broke along the way.

This is an AI agent that reconciles transactions between a bank's records and a company's internal ledger, figures out why the two disagree when they do, and decides, with real safety checks, which cases it can resolve on its own versus which ones need a human. It's built with Python, pandas, an LLM-based agent running on the Groq API, confidence-scored routing, and a Streamlit dashboard on top.

I built it around one rule I kept coming back to: the AI proposes, deterministic code disposes. The model never touches a number. No matching. No totals. No amount comparisons. Its only job is judgment: why did this happen, and how sure am I about that. If it gets a reason wrong, I catch that in the time it takes to read it. A wrong number is different. That mistake could sit quietly in a ledger for months before anyone noticed.

## The results

I tested this on 102 synthetic transactions, 63 that matched cleanly and 39 that didn't.

| Metric | Without AI | With AI |
|---|---|---|
| Overall automation rate | 61.8% | 99.0% |
| Exceptions auto-resolved | 0 of 39 | 38 of 39 |
| Exceptions sent for human review | 39 of 39 | 1 of 39 |

That's a 37.3 point jump in automation, and it's a measured number, not a guess. Without AI, the matching engine tells you something's wrong and stops there. Every one of those 39 cases would need a person to dig in manually. With the agent reasoning over each one, 38 got resolved with a stated, checkable reason. The one that didn't was a ₹48,000 mismatch, correctly held back for human review. Not because the model was confused, but because the amount alone was enough to warrant a second look regardless of how confident it sounded.

## Why this problem

Reconciliation doesn't scale by adding more analysts, it scales by shrinking what actually needs one. The interesting problem here was never "detect the mismatch," plain code has always been able to do that. It was figuring out which mismatches are actually safe to close out without a human, and proving that number instead of just asserting it.

## How it's built

The pipeline is split into stages that each do one job and don't overlap:

`generate_data.py` builds the synthetic bank and company records, about a hundred transactions with deliberate, realistic mismatches worked in, fee deductions, settlement delays, duplicate entries, partial refunds, rounding noise.

`matching.py` is the deterministic layer. Plain pandas, exact ID and amount matching, no model involved anywhere in it. It classifies every transaction as a clean match, a missing entry, an amount mismatch, or a duplicate.

`agent.py` is where the AI comes in, and only for the exceptions the matcher couldn't close on its own. It calls tools to pull transaction context and check payment status, asks the model to reason about the likely cause, and gets back a structured verdict: a reason, a confidence score, and a cited justification. That output feeds a routing decision, not a final one, more on that below.

`report.py` and `compare_ai.py` generate the summary numbers and the with-AI-versus-without-AI comparison above.

`dashboard.py` is a Streamlit app for browsing all of this visually instead of reading raw CSVs.

Full breakdown of the agent's tools and exactly what it is and isn't allowed to decide is in `AGENT.md`.

## Why the agent doesn't get the final say

A model can sound just as confident about a ₹15 rounding error as it can about a ₹40,000 discrepancy, confidence measures how sure the reasoning is, not how expensive it would be if that reasoning turns out wrong. So a case only auto-resolves here if three separate things hold at once: confidence at 80 or above, a transaction amount under ₹5,000, and an actual cited reason rather than a shrug. Miss any one of those and it goes to a person instead, no exceptions carved out for a model that "seems sure." This is the same shape reconciliation automation runs at in production at real scale, automate the confident majority, keep a human for anything genuinely uncertain or expensive to get wrong.

## What actually broke

The pipeline runs clean now. It didn't start that way.

The routing logic almost shipped with exactly the flaw described above, a single confidence check deciding everything. I caught it before it mattered, but only because I stopped to ask what "confident" was actually protecting against, and realized the answer was "not much, on its own."

Then the numbers themselves threw me off for a bit. I'd built the synthetic dataset to land around 75% clean matches, and the first full run came back at 61.8% instead. For a few minutes I assumed the matching code had a bug. It didn't. About a dozen of the transactions were hand-built edge cases I'd deliberately skewed toward messy scenarios, because the point of building them by hand was to stress specific failure types rather than represent the whole set fairly. Once I remembered that, the number made complete sense. My assumption about what "correct" should have looked like was the thing that needed fixing, not the code.

The auto-resolve rate made me suspicious too, for the opposite reason. Thirty-eight out of thirty-nine sounds like either a system working exactly as intended, or one quietly rubber-stamping everything and calling it confidence. I didn't trust the summary stats enough to just accept the number, so I went and checked the one case I'd built specifically to be risky by hand, the ₹48,000 one, and confirmed it landed in human review for the right stated reason. That single manual check is the difference between a number that looks good and one that's actually earned.

The rest was ordinary infrastructure pain. `google-generativeai` hung forever on import under Python 3.14, somewhere in its dependency chain through grpc and protobuf, so I dropped the SDK entirely and called the REST endpoint directly instead. That fixed the hang, but every request then came back with a 404, which turned out to be two separate problems stacked on top of each other, a key format migration Google had rolled out in June, and a model version that had already been deprecated underneath me. After patching both and still hitting dead ends, I moved off Gemini entirely and switched to Groq, which uses a plainer, more stable API surface. Groq then rate-limited me partway through a batch of calls, so I added a short delay between requests and a retry with backoff for anything that came back 429. None of these were interesting problems in isolation, they were just the normal cost of building against real APIs instead of a spec sheet.

## Running it

```bash
pip install -r requirements.txt

python src/generate_data.py
python src/matching.py
python src/agent.py
python src/report.py
python src/compare_ai.py
streamlit run src/dashboard.py
```

Matching and reporting run fully offline, no API needed. The agent step calls an LLM, add `GROQ_API_KEY=...` to a `.env` file to run it live.

Stack: Python, pandas, Groq for LLM inference, plain REST calls via `requests`, Streamlit, python-dotenv. Techniques: deterministic rule-based matching, LLM reasoning with structured JSON output, tool-calling, confidence scoring, multi-factor human-in-the-loop routing, retry-with-backoff for rate limit handling.

## Where things stand

Everything above is built, tested, and reproducible from a clean environment: data generation, deterministic matching, the reasoning agent, confidence-based routing, reporting, the AI-impact comparison, and the dashboard. See `AGENT.md` for the detailed breakdown of what the agent can and can't decide on its own.

Back to where this started: the gap wasn't in detecting mismatches, that part was never hard. It was in getting a system to explain itself well enough that a human doesn't have to double-check everything anyway. The 99% automation number is what that gap actually closing looks like, measured, not assumed.