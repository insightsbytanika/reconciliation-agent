# What the agent actually does

An AI agent that's given permission to touch numbers is a liability waiting to happen. This one never gets that permission, and this document is about exactly where the line is drawn and why.

This is the reasoning layer of the reconciliation pipeline, an LLM-based agent (running on the Groq API) that gets called only after deterministic matching has already done its job. It doesn't match transactions. It doesn't total anything. Its entire scope is judgment: given an exception the matching engine couldn't resolve, a missing entry, an amount that doesn't line up, a duplicate, figure out why, and say how sure it is.

Clean matches never reach it. It has no opinion on those, and it shouldn't.

## What it can look up

Before reasoning about a case, the agent pulls context using two tools rather than working from the exception alone. This is deliberate tool-calling, not a single monolithic prompt with everything crammed in.

`fetch_transaction_details` goes back to both the bank and company records and pulls whatever raw data exists for that transaction ID, amounts, dates, whatever's there on either side.

`check_payment_status` runs a quick heuristic on how big the gap actually is between the two amounts, and returns a rough label: clean, a small discrepancy, a large one, or an incomplete record. In a real production system this would hit a live payment-status API instead of computing something from the same CSV, but the shape of the check is the same either way.

The agent decides for itself which of these it needs for a given case. It isn't following a fixed script that runs both every time.

## What it hands back

For every exception, the model returns structured JSON output rather than a paragraph of free text, specifically because free text is hard to parse reliably and easy to fake confidence in. The verdict has three fields: a short reason for why the mismatch likely happened, a confidence score from 0 to 100, and a cited justification, something concrete backing the explanation, or an honest "none" if it can't find one.

Forcing this structure matters more than it might sound like it should. A model that's allowed to just explain itself in prose will sound confident about almost anything. Asking it to also name a specific, checkable justification, or admit it doesn't have one, is what actually separates a real explanation from a plausible-sounding guess.

## What it doesn't get to decide alone

This is the part I'd want anyone reviewing this to look at closely, and it's also where the first real bug in this project showed up. My original routing logic checked one thing: the agent's own confidence score. If it was high enough, the case auto-resolved. Nothing else mattered.

That's a quiet bug, because a model can sound equally confident about a fifteen rupee rounding difference and a forty thousand rupee gap. Confidence measures how sure the model is about its reasoning, not how expensive it would be if that reasoning is wrong. An amount-blind confidence score making the call on its own works fine right up until the one case where it doesn't, and by then it's already resolved and out of sight.

So the agent's confidence score is now one input into a routing decision, not the decision itself. All three of the following have to hold before anything closes out on its own: confidence at 80 or higher, a transaction amount under ₹5,000, and an actual cited reason. Fail any one of those and the case goes to a person, regardless of how sure the model's own output claims to be.

## What it never touches

The agent has no role in matching, totaling, or any arithmetic anywhere in this pipeline. That stays entirely in deterministic pandas code, on purpose. A wrong label from the model is something a reviewer catches the moment they read it. A wrong number computed by a model can sit quietly in a ledger for months before anyone notices, and that asymmetry is the whole reason for keeping the two apart.

It also doesn't carry memory between cases in the current version. Every exception is reasoned about independently, with no awareness of what it decided on a similar case a moment earlier. Logging human corrections and feeding them back in as reference material for future cases is the obvious next step, but it isn't built yet.

## Why it's built this way

None of these constraints came from a checklist. Each one exists because something specific would have gone wrong without it, an overconfident model auto-resolving a large mismatch, an unparseable explanation nobody could act on, a silent arithmetic error nobody would catch. Designing an agent for a finance context means spending most of the effort on what it's not allowed to do, and being able to explain exactly why each boundary is there. That's the part of this build I'd want a team to see.