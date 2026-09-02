"""
with ai  vs. wothout ai comparison
answer for  "why ai helps here"
without ai: matching engine alone can only detect that something
is wrong (mismatch/missing/duplicate). It cannot explain why, or judge
whether it's safe to resolve automatically. So every single exception
needs a human to manually investigate it - 0% automation on exceptions.
with ai: The agent investigates each exception reasons about the likely
cause and safely auto resolves the ones it's confident and safe about.
"""

import pandas as pd

matched = pd.read_csv("../outputs/matched_results.csv")
agent_results = pd.read_csv("../outputs/agent_results.csv")

total = len(matched)
perfect_matches = len(matched[matched["category"] == "Perfect Match"])
total_exceptions = len(agent_results)

# without ai matching alone finds perfect matches but every exception needs a human
without_ai_auto_resolved = 0
without_ai_human_needed = total_exceptions
without_ai_automation_rate = perfect_matches / total * 100

# with ai
with_ai_auto_resolved = len(agent_results[agent_results["routing"] == "Auto-Resolved"])
with_ai_human_needed = len(agent_results[agent_results["routing"] == "Needs Human Review"])
with_ai_automation_rate = (perfect_matches + with_ai_auto_resolved) / total * 100

print("=" * 60)
print("WITH AI vs WITHOUT AI - Comparison")
print("=" * 60)

print(f"\nTotal transactions: {total}")
print(f"Perfect matches (handled the same either way): {perfect_matches}")
print(f"Exceptions requiring investigation: {total_exceptions}")

print("\n--- WITHOUT AI (matching engine alone) ---")
print(f"Exceptions auto-resolved: {without_ai_auto_resolved} (0.0%)")
print(f"Exceptions needing full manual investigation: {without_ai_human_needed} (100.0%)")
print(f"Overall automation rate: {without_ai_automation_rate:.1f}%")

print("\n--- WITH AI (our agent) ---")
print(f"Exceptions auto-resolved: {with_ai_auto_resolved} ({with_ai_auto_resolved/total_exceptions*100:.1f}%)")
print(f"Exceptions needing human review: {with_ai_human_needed} ({with_ai_human_needed/total_exceptions*100:.1f}%)")
print(f"Overall automation rate: {with_ai_automation_rate:.1f}%")

improvement = with_ai_automation_rate - without_ai_automation_rate
print(f"\n>>> Improvement in overall automation rate: +{improvement:.1f} percentage points")
print(f">>> Of the {total_exceptions} exceptions that used to need full manual work,")
print(f">>> AI now safely resolves {with_ai_auto_resolved} of them on its own.")


with open("../outputs/ai_comparison.txt", "w") as f:
    f.write("WITH AI vs WITHOUT AI Comparison\n")
    f.write("=" * 40 + "\n")
    f.write(f"Without AI - overall automation rate: {without_ai_automation_rate:.1f}%\n")
    f.write(f"With AI - overall automation rate: {with_ai_automation_rate:.1f}%\n")
    f.write(f"Improvement: +{improvement:.1f} percentage points\n")
    f.write(f"Exceptions auto-resolved by AI: {with_ai_auto_resolved} out of {total_exceptions}\n")

print("\nSaved to outputs/ai_comparison.txt")