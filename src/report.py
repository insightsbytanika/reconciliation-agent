"""
Final Summary Report
Combines the matching results and agent results into one clear report:
    -Overall stats (match rate, exception rate)
    -How many exceptions were auto-resolved vs sent for human review
    -An honest and readable exception list (what happened, why, how confident)
"""

import pandas as pd

matched = pd.read_csv("../outputs/matched_results.csv")
agent_results = pd.read_csv("../outputs/agent_results.csv")

total = len(matched)
perfect_matches = len(matched[matched["category"] == "Perfect Match"])
total_exceptions = len(agent_results)

auto_resolved = len(agent_results[agent_results["routing"] == "Auto-Resolved"])
human_review = len(agent_results[agent_results["routing"] == "Needs Human Review"])

print("=" * 50)
print("RECONCILIATION SUMMARY REPORT")
print("=" * 50)

print(f"\nTotal transactions processed: {total}")
print(f"Perfect matches (no AI needed): {perfect_matches} ({perfect_matches/total*100:.1f}%)")
print(f"Exceptions found: {total_exceptions} ({total_exceptions/total*100:.1f}%)")

print(f"\nOf the {total_exceptions} exceptions:")
print(f"  Auto-resolved by AI: {auto_resolved} ({auto_resolved/total_exceptions*100:.1f}%)")
print(f"  Flagged for human review: {human_review} ({human_review/total_exceptions*100:.1f}%)")

overall_automation_rate = (perfect_matches + auto_resolved) / total * 100
print(f"\nOverall automation rate (no human touch needed): {overall_automation_rate:.1f}%")


# The honest exception list - cases that genuinely need a human

print("\n" + "=" * 50)
print("CASES FLAGGED FOR HUMAN REVIEW (Honest Exception List)")
print("=" * 50)

flagged = agent_results[agent_results["routing"] == "Needs Human Review"]

if len(flagged) == 0:
    print("\nNone - every exception was resolved with high confidence.")
else:
    for _, row in flagged.iterrows():
        print(f"\nTransaction: {row['transaction_id']}")
        print(f"  Category: {row['category']}")
        print(f"  Bank amount: {row['amount_bank']} | Company amount: {row['amount_company']}")
        print(f"  AI's reasoning: {row['likely_reason']}")
        print(f"  Confidence: {row['confidence']}")
        print(f"  Why flagged: ", end="")
        reasons = []
        if row['confidence'] < 80:
            reasons.append("low confidence")
        amount = row['amount_bank'] if pd.notna(row['amount_bank']) else row['amount_company']
        if amount >= 5000:
            reasons.append("large transaction amount")
        if str(row['cited_rule']).lower() == "none":
            reasons.append("no concrete rule cited")
        print(", ".join(reasons))


# Save a clean version of the report to a file too

with open("../outputs/summary_report.txt", "w") as f:
    f.write(f"Total transactions: {total}\n")
    f.write(f"Perfect matches: {perfect_matches} ({perfect_matches/total*100:.1f}%)\n")
    f.write(f"Exceptions: {total_exceptions} ({total_exceptions/total*100:.1f}%)\n")
    f.write(f"Auto-resolved: {auto_resolved} ({auto_resolved/total_exceptions*100:.1f}%)\n")
    f.write(f"Needs human review: {human_review} ({human_review/total_exceptions*100:.1f}%)\n")
    f.write(f"Overall automation rate: {overall_automation_rate:.1f}%\n")

print("\n\nSaved summary to outputs/summary_report.txt")