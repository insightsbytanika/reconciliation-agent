"""
Reconciliation Agent
This is where AI actually comes in - but only for reasoning, never for numbers.
For every exception the matching engine couldn't resolve (mismatch, missing,
duplicate), this agent:
    1. Looks up extra context about the transaction (using "tools")
    2. Asks an LLM to reason about WHY the exception happened
    3. Gets back a confidence score + a cited reason
    4. Decides: auto-resolve it, or send it to a human for review

Routing rule:
    Auto-resolve only if:
        - confidence is high (>= 80)
        - amount is below a risk threshold (so big-money cases always get a
          second look, even if the AI feels confident)
        -the AI actually cited a concrete reason (not a random guess)
    Otherwise -> flagged for human review.
"""

import os
import json
import time
import requests
import pandas as pd
from dotenv import load_dotenv


# Step 1: Load the API key from .env (never hardcoded in the file)

load_dotenv()  # reads the .env file and loads its variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found. Check your .env file.")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

def call_llm(prompt, retries=3):
    """Sends a prompt to Groq's chat completion API (OpenAI-compatible format).
    Retries automatically if we hit a rate limit (HTTP 429)."""
    for attempt in range(retries):
        response = requests.post(
            GROQ_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
            json={
                "model": "openai/gpt-oss-20b",
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        if response.status_code == 429:
            wait_time = 10 * (attempt + 1)  # wait longer each retry: 10s, 20s, 30s
            print(f"  Rate limited, waiting {wait_time}s before retry...")
            time.sleep(wait_time)
            continue
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    raise RuntimeError("Failed after multiple retries due to rate limiting.")


# Step2: tools that the agent can use



def fetch_transaction_details(transaction_id, bank_df, company_df):

    bank_row = bank_df[bank_df["transaction_id"] == transaction_id]
    company_row = company_df[company_df["transaction_id"] == transaction_id]
    return {
        "bank": bank_row.to_dict(orient="records"),
        "company": company_row.to_dict(orient="records"),
    }

def check_payment_status(row):
    if pd.isna(row.get("amount_bank")) or pd.isna(row.get("amount_company")):
        return "incomplete_record"
    diff = abs(row["amount_bank"] - row["amount_company"])
    if diff == 0:
        return "settled_clean"
    elif diff < 50:
        return "small_discrepancy"
    else:
        return "large_discrepancy"

# Step 3: The core reasoning call to the ai

def investigate_exception(row, context, status):
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
    response_text = call_llm(prompt)

    
    text = response_text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # If parsing fails, treat it as a low-confidence, unexplainable case
        # rather than crashing the whole pipeline.
        result = {"likely_reason": "Could not parse AI response", "confidence": 0, "cited_rule": "none"}

    return result

 
# Step 4: Routing decision 

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


# Step 5: Main pipeline

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

        time.sleep(2.5)  

    results_df = pd.DataFrame(results)
    results_df.to_csv("../outputs/agent_results.csv", index=False)

    print("\n=== Routing Summary ===")
    print(results_df["routing"].value_counts())
    print("\nSaved to outputs/agent_results.csv")

if __name__ == "__main__":
    main()