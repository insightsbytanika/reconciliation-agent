"""
Reconciliation Agent Dashboard
Run with: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Reconciliation Agent", layout="wide")

st.title("AI Reconciliation Agent - Results Dashboard")
st.caption("Deterministic matching + AI-driven exception reasoning, with human-in-the-loop safety routing")

# load data
matched = pd.read_csv("../outputs/matched_results.csv")
agent_results = pd.read_csv("../outputs/agent_results.csv")

total = len(matched)
perfect_matches = len(matched[matched["category"] == "Perfect Match"])
total_exceptions = len(agent_results)
auto_resolved = len(agent_results[agent_results["routing"] == "Auto-Resolved"])
human_review = len(agent_results[agent_results["routing"] == "Needs Human Review"])
automation_rate = (perfect_matches + auto_resolved) / total * 100


col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Transactions", total)
col2.metric("Perfect Matches", perfect_matches, f"{perfect_matches/total*100:.1f}%")
col3.metric("Auto-Resolved by AI", auto_resolved, f"{auto_resolved/total_exceptions*100:.1f}% of exceptions")
col4.metric("Overall Automation Rate", f"{automation_rate:.1f}%")

st.divider()

# With vs Without AI comparison

st.subheader("Why AI? - With vs. Without AI")

without_ai_rate = perfect_matches / total * 100
comparison_df = pd.DataFrame({
    "Scenario": ["Without AI", "With AI"],
    "Automation Rate (%)": [without_ai_rate, automation_rate]
})
st.bar_chart(comparison_df.set_index("Scenario"))
st.caption(
    f"Without AI, only clean matches are handled automatically ({without_ai_rate:.1f}%). "
    f"With AI reasoning on exceptions, that rises to {automation_rate:.1f}%  "
    f"a +{automation_rate - without_ai_rate:.1f} point improvement."
)

st.divider()


# Breakdown by category

st.subheader("Transaction Breakdown")
category_counts = matched["category"].value_counts()
st.bar_chart(category_counts)

st.divider()


# Honest exception list
st.subheader("Exception Handling Detail")

tab1, tab2 = st.tabs(["Auto-Resolved by AI", "Flagged for Human Review"])

with tab1:
    auto_df = agent_results[agent_results["routing"] == "Auto-Resolved"]
    st.dataframe(
        auto_df[["transaction_id", "category", "amount_bank", "amount_company", "likely_reason", "confidence"]],
        use_container_width=True
    )

with tab2:
    flagged_df = agent_results[agent_results["routing"] == "Needs Human Review"]
    if len(flagged_df) == 0:
        st.info("No cases were flagged for human review.")
    else:
        st.dataframe(
            flagged_df[["transaction_id", "category", "amount_bank", "amount_company", "likely_reason", "confidence"]],
            use_container_width=True
        )
        st.caption("These cases were intentionally NOT auto-resolved either confidence was low, the amount was large, or no concrete reason could be cited.")