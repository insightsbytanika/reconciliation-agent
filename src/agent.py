"""
Reconciliation Agent
This is where AI actually comes in - but ONLY for reasoning, never for numbers.

For every exception the matching engine couldn't resolve (mismatch, missing,
duplicate), this agent:
    1. Looks up extra context about the transaction (using "tools")
    2. Asks Gemini to reason about WHY the exception happened
    3. Gets back a confidence score + a cited reason
    4. Decides: auto-resolve it, or send it to a human for review

Routing rule (multi-factor, not just confidence):
    Auto-resolve ONLY if:
        - confidence is high (>= 80)
        - amount is below a risk threshold (so big-money cases always get a
          second look, even if the AI feels confident)
        - the AI actually cited a concrete reason (not a vague guess)
    Otherwise -> flagged for human review.
"""

import os
import json
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv

# -------------------------------------------------------------------
# Step 1: Load the API key from .env (never hardcoded in the file)
# -------------------------------------------------------------------
load_dotenv()  # reads the .env file and loads its variables
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found. Check your .env file.")

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash")

# -------------------------------------------------------------------
# Step 2: "Tools" the agent can use
# -------------------------------------------------------------------
# In a real system these would call actual databases/APIs. Here, since we're
# working with synthetic data, they simply look up extra info from our own
# CSVs - but structurally, this is exactly how a real tool-calling agent
# would be wired up.

def fetch_transaction_details(transaction_id, bank_df, company_df):
    """Tool 1: pulls whatever info exists for this id from both sources."""
    bank_row = bank_df[bank_df["transaction_id"] == transaction_id]
    company_row = company_df[company_df["transaction_id"] == transaction_id]
    return {
        "bank": bank_row.to_dict(orient="records"),
        "company": company_row.to_dict(orient="records"),
    }

def check_payment_status(row):
    """Tool 2: a simple heuristic status check based on the data we have.
    (In a real system, this would call a live payment-status API.)"""
    if pd.isna(row.get("amount_bank")) or pd.isna(row.get("amount_company")):
        return "incomplete_record"
    diff = abs(row["amount_bank"] - row["amount_company"])
    if diff == 0:
        return "settled_clean"
    elif diff < 50:
        return "small_discrepancy"
    else:
        return "large_discrepancy"

# -------------------------------------------------------------------
# Step 3: The core reasoning call to the AI
# -------------------------------------------------------------------
def investigate_exception(row, context, status):
    """
    Sends the case details to Gemini and asks it to reason about the
    mismatch. We explicitly ask for structured JSON output so we can
    parse it reliably (rather than free-form text).
    """
    prompt = f"""
You are a financial reconciliation assistant. Analyze this transaction exception
and explain the most likely reason for it.

Transaction ID: {row['transaction_id']}
Category flagged by matching engine: {row['category']}
Bank amount: {row.get('amount_bank', 'N/A')}
Company amount: {row.get('amount_company', 'N/A')}
Payment status check: {status}
Raw context: {json.dumps(context)}

Respond ONLY with valid JSON in this exact format, no extra text:
{{
  "likely_reason": "short explanation of why this mismatch happened",
  "confidence": <integer 0-100>,
  "cited_rule": "the specific logic/rule backing this conclusion, or 'none' if you cannot cite one"
}}
"""
    response = model.generate_content(prompt)

    # Clean up response in case Gemini wraps it in markdown code fences
    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # If parsing fails, treat it as a low-confidence, unexplainable case
        # rather than crashing the whole pipeline.
        result = {"likely_reason": "Could not parse AI response", "confidence": 0, "cited_rule": "none"}

    return result

# -------------------------------------------------------------------
# Step 4: Routing decision (multi-factor, discussed earlier)
# -------------------------------------------------------------------
AMOUNT_RISK_THRESHOLD = 5000   # transactions above this always get a human look
CONFIDENCE_THRESHOLD = 80

def decide_routing(ai_result, row):
    confidence = ai_result.get("confidence", 0)
    cited_rule = ai_result.get("cited_rule", "none")

    amount = row.get("amount_bank")
    if pd.isna(amount):
        amount = row.get("amount_company", 0)

    high_confidence = confidence >= CONFIDENCE_THRESHOLD
    low_risk_amount = amount < AMOUNT_RISK_THRESHOLD
    has_citation = cited_rule.lower() != "none"

    if high_confidence and low_risk_amount and has_citation:
        return "Auto-Resolved"
    else:
        return "Needs Human Review"

# -------------------------------------------------------------------
# Step 5: Main pipeline
# -------------------------------------------------------------------
def main():
    bank_df = pd.read_csv("../data/bank_records.csv")
    company_df = pd.read_csv("../data/company_records.csv")
    matched = pd.read_csv("../outputs/matched_results.csv")

    exceptions = matched[matched["category"] != "Perfect Match"].copy()
    print(f"Found {len(exceptions)} exceptions out of {len(matched)} total transactions.\n")

    results = []
    for _, row in exceptions.iterrows():
        context = fetch_transaction_details(row["transaction_id"], bank_df, company_df)
        status = check_payment_status(row)
        ai_result = investigate_exception(row, context, status)
        routing = decide_routing(ai_result, row)

        results.append({
            "transaction_id": row["transaction_id"],
            "category": row["category"],
            "amount_bank": row.get("amount_bank"),
            "amount_company": row.get("amount_company"),
            "likely_reason": ai_result.get("likely_reason"),
            "confidence": ai_result.get("confidence"),
            "cited_rule": ai_result.get("cited_rule"),
            "routing": routing,
        })
        print(f"{row['transaction_id']} | {row['category']} | confidence={ai_result.get('confidence')} | -> {routing}")

    results_df = pd.DataFrame(results)
    results_df.to_csv("../outputs/agent_results.csv", index=False)

    print("\n=== Routing Summary ===")
    print(results_df["routing"].value_counts())
    print("\nSaved to outputs/agent_results.csv")

if __name__ == "__main__":
    main()