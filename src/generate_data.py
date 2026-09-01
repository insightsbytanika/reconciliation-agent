"""
Synthetic Data Generator for Reconciliation Agent
---------------------------------------------------
Generates two datasets: bank_records.csv and company_records.csv

Approach: Hybrid
  - 12 hand designed "tricky" cases (so we can explain each one specifically)
  - 88 randomly generated records (for volume / scale)
  Total: 100 transactions
"""

import pandas as pd
import random

# Fixed seed = every time we run this, we get the same random data
# Interview flag to know: without this, our results would change every run,
# making it impossible to reliably demo or debug. This is standard practice.
random.seed(42)

bank_records = []
company_records = []

# -------------------------------------------------------------------
# PART 1: Hardcoded tricky cases (designed on purpose, one by one)
# -------------------------------------------------------------------

# Case 1: Perfect match
bank_records.append({"transaction_id": "T1001", "amount": 1000, "date": "2026-01-01"})
company_records.append({"transaction_id": "T1001", "amount": 1000, "date": "2026-01-01"})

# Case 2: Missing from company records (bank has it, company doesn't)
bank_records.append({"transaction_id": "T1002", "amount": 500, "date": "2026-01-01"})
# (intentionally NOT added to company_records)

# Case 3: Missing from bank records (company has it, bank doesn't)
company_records.append({"transaction_id": "T1003", "amount": 750, "date": "2026-01-02"})
# (intentionally NOT added to bank_records)

# Case 4: Fee deduction mismatch (small, explainable difference)
bank_records.append({"transaction_id": "T1004", "amount": 980, "date": "2026-01-02"})
company_records.append({"transaction_id": "T1004", "amount": 1000, "date": "2026-01-02"})
# Bank shows 980 because a 20 rupee processing fee was deducted before settlement.

# Case 5: Unexplained large mismatch (genuine problem, should flag for review)
bank_records.append({"transaction_id": "T1005", "amount": 200, "date": "2026-01-03"})
company_records.append({"transaction_id": "T1005", "amount": 1000, "date": "2026-01-03"})

# Case 6: Duplicate transaction ID in company records (data entry error)
company_records.append({"transaction_id": "T1006", "amount": 300, "date": "2026-01-03"})
company_records.append({"transaction_id": "T1006", "amount": 300, "date": "2026-01-03"})
bank_records.append({"transaction_id": "T1006", "amount": 300, "date": "2026-01-03"})

# Case 7: Date mismatch (same id/amount, different date = delayed settlement)
bank_records.append({"transaction_id": "T1007", "amount": 450, "date": "2026-01-05"})
company_records.append({"transaction_id": "T1007", "amount": 450, "date": "2026-01-03"})

# Case 8: Rounding difference (very small, should auto-resolve)
bank_records.append({"transaction_id": "T1008", "amount": 999.99, "date": "2026-01-04"})
company_records.append({"transaction_id": "T1008", "amount": 1000, "date": "2026-01-04"})

# Case 9: Large amount mismatch (tests amount-based risk gating)
bank_records.append({"transaction_id": "T1009", "amount": 48000, "date": "2026-01-04"})
company_records.append({"transaction_id": "T1009", "amount": 50000, "date": "2026-01-04"})

# Case 10: Partial refund scenario
bank_records.append({"transaction_id": "T1010", "amount": 700, "date": "2026-01-05"})
company_records.append({"transaction_id": "T1010", "amount": 1000, "date": "2026-01-05"})
# 300 was refunded, so bank shows the net amount

# Case 11: Currency-style rounding (paisa-level noise)
bank_records.append({"transaction_id": "T1011", "amount": 250.50, "date": "2026-01-06"})
company_records.append({"transaction_id": "T1011", "amount": 250.45, "date": "2026-01-06"})

# Case 12: Duplicate in bank records this time (reverse of case 6)
bank_records.append({"transaction_id": "T1012", "amount": 600, "date": "2026-01-06"})
bank_records.append({"transaction_id": "T1012", "amount": 600, "date": "2026-01-06"})
company_records.append({"transaction_id": "T1012", "amount": 600, "date": "2026-01-06"})

# -------------------------------------------------------------------
# PART 2: Randomly generated records (for volume / scale)
# -------------------------------------------------------------------

next_id = 2000  # start IDs from T2000 onward to avoid clashing with hardcoded ones

for i in range(88):
    txn_id = f"T{next_id + i}"
    base_amount = round(random.uniform(100, 5000), 2)
    date = f"2026-01-{random.randint(1, 28):02d}"

    # Decide what "type" of record this will be (weighted probabilities)
    outcome = random.choices(
        population=["clean_match", "small_fee_mismatch", "missing_one_side"],
        weights=[0.75, 0.15, 0.10],   # 75% clean, 15% small mismatch, 10% missing
        k=1
    )[0]

    if outcome == "clean_match":
        bank_records.append({"transaction_id": txn_id, "amount": base_amount, "date": date})
        company_records.append({"transaction_id": txn_id, "amount": base_amount, "date": date})

    elif outcome == "small_fee_mismatch":
        fee = round(random.uniform(1, 20), 2)
        bank_records.append({"transaction_id": txn_id, "amount": round(base_amount - fee, 2), "date": date})
        company_records.append({"transaction_id": txn_id, "amount": base_amount, "date": date})

    elif outcome == "missing_one_side":
        # randomly decide which side is missing
        if random.random() < 0.5:
            bank_records.append({"transaction_id": txn_id, "amount": base_amount, "date": date})
        else:
            company_records.append({"transaction_id": txn_id, "amount": base_amount, "date": date})

# -------------------------------------------------------------------
# Save to CSV
# -------------------------------------------------------------------

bank_df = pd.DataFrame(bank_records)
company_df = pd.DataFrame(company_records)

bank_df.to_csv("../data/bank_records.csv", index=False)
company_df.to_csv("../data/company_records.csv", index=False)

print(f"Bank records: {len(bank_df)} rows")
print(f"Company records: {len(company_df)} rows")
print("\nSample bank records:")
print(bank_df.head(15))
print("\nSample company records:")
print(company_df.head(15))
