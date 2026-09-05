# What the agent actually does

This is the part of the system most people would call "the AI," so it's worth being precise about what that actually means here, and what it deliberately doesn't mean.

The agent only ever sees a transaction after the deterministic matching engine has already decided it can't resolve it on its own, a missing entry, an amount that doesn't line up, a duplicate. Clean matches never reach the agent at all. It has no opinion on those, and it shouldn't.

## What it can look up

Before reasoning about a case, the agent pulls context using two tools rather than working from the exception alone.

`fetch_transaction_details` goes back to both the bank and company records and pulls whatever raw data exists for that transaction ID, amounts, dates, whatever's there on either side.

`check_payment_status` runs a quick heuristic on how big the gap actually is between the two amounts, and returns a rough label: clean, a small discrepancy, a large one, or an incomplete record. In a real production system this would hit a live payment-status API instead of computing something from the same CSV, but the shape of the check is the same either way.

The agent decides for itself which of these it needs for a given case. It isn't following a fixed script that runs both every time.

## What it hands back

For every exception, the model returns a structured verdict rather than a paragraph of free text, specifically because free text is hard to act on reliably. The verdict has three parts: a short reason for why the mismatch likely happened, a confidence score from 0 to 100, and a cited justification, something concrete backing the explanation, or an honest "none" if it can't find one.

Forcing this structure matters more than it might sound like it should. A model that's allowed to just explain itself in prose will sound confident about almost anything. Asking it to also name a specific, checkable justification, or admit it doesn't have one, is what actually separates a real explanation from a plausible-sounding guess.

## What it doesn't get to decide alone

This is the part I'd want anyone reviewing this to look at closely. The agent's own confidence score is not the final word on whether a case gets auto-resolved. It's one input into a routing decision that also checks the transaction amount and whether a real justification was cited. All three have to hold before anything closes out on its own: confidence at 80 or higher, an amount under ₹5,000, and an actual cited reason. Fail any one of those and the case goes to a person, regardless of how sure the model's own output claims to be.

The reasoning behind that split is simple: a model can sound equally confident about a fifteen rupee rounding difference and a forty thousand rupee gap, because confidence measures how sure it is about its reasoning, not how much is at stake if that reasoning is wrong. Letting an amount-blind confidence score make the call on its own is exactly the kind of thing that works fine until the one time it doesn't.

## What it never touches

The agent has no role in matching, totaling, or any arithmetic anywhere in this pipeline. That's handled entirely by deterministic pandas code, on purpose. A wrong label from the model is something a reviewer catches the moment they read it. A wrong number computed by a model can sit quietly in a ledger for months before anyone notices, and that asymmetry is the whole reason for keeping the two apart.

It also doesn't carry memory between cases in the current version. Every exception is reasoned about independently, with no awareness of what it decided on a similar case a moment earlier. Logging human corrections and feeding them back in as reference material for future cases is the obvious next step, but it isn't built yet.