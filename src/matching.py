"""
Matching Engine for Reconciliation Agent

It compares bank_records.csv and company_records.csv and classifies every
transaction into one of 4 categories
    1. Perfect Match     -> same id, same amount, in both files
    2. Missing            -> id exists in only one file
    3. Amount Mismatch    -> same id, but different amount
    4. Duplicate          -> same id appears more than once in a single file
This is 100% deterministic (plain pandas) - no AI/LLM is used here
This is intentional:matching numbers should never depend on an AI's guess
"""

import pandas as pd
# Load the data

bank_df = pd.read_csv("../data/bank_records.csv")
company_df = pd.read_csv("../data/company_records.csv")
print(f"Loaded {len(bank_df)} bank records and {len(company_df)} company records.\n")

# Step2 = detect duplicates(before merging)

# 
bank_duplicates = bank_df[bank_df.duplicated(subset="transaction_id", keep=False)]
company_duplicates = company_df[company_df.duplicated(subset="transaction_id", keep=False)]


# Step3 =Merge the two tables on transaction_id

merged = pd.merge(
    bank_df,
    company_df,
    on="transaction_id",
    how="outer",
    suffixes=("_bank", "_company"),  # renames overlapping columns (amount, date)
    indicator=True                   # adds the _merge column:both/left_only /right_only
)


# Step 4 : classify each row into 1 of our 4 categories

def classify(row):
    # id only exists in bank records
    if row["_merge"] == "left_only":
        return "Missing in Company"

    # id only exists in company records
    if row["_merge"] == "right_only":
        return "Missing in Bank"

    # id exists in both - check if amounts match
    # round() avoids flagging tiny floating point noise (e.g. 999.990000001) as a mismatch
    if round(row["amount_bank"], 2) == round(row["amount_company"], 2):
        return "Perfect Match"
    else:
        return "Amount Mismatch"

merged["category"] = merged.apply(classify, axis=1)


# steEp5= also tag rows that are part of a duplicate

duplicate_ids = set(bank_duplicates["transaction_id"]).union(set(company_duplicates["transaction_id"]))
merged.loc[merged["transaction_id"].isin(duplicate_ids), "category"] = "Duplicate"

# step 6: Summary report
summary = merged["category"].value_counts()

print("=== Reconciliation Summary ===")
print(summary)
print(f"\nTotal unique transaction IDs processed: {len(merged)}")

match_rate = (summary.get("Perfect Match", 0) / len(merged)) * 100
print(f"Perfect match rate: {match_rate:.1f}%")


#step7 = save all the detailed results for the next stage(the AI agent)

merged.to_csv("../outputs/matched_results.csv", index=False)
print("\nDetailed results saved to outputs/matched_results.csv")

# show preview for every category
print("\n=== Sample of each category ===")
for cat in merged["category"].unique():
    print(f"\n--- {cat} ---")
    print(merged[merged["category"] == cat][["transaction_id", "amount_bank", "amount_company", "category"]].head(3))