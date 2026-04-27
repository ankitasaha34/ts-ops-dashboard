import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import anthropic
import os
import json
from dotenv import load_dotenv
from datetime import timedelta

# ── Setup ─────────────────────────────────────────────────────────
load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

st.set_page_config(
    page_title="T&S Ops Dashboard",
    page_icon="🛡️",
    layout="wide"
)

# ── Load Data ─────────────────────────────────────────────────────
@st.cache_data
def load_data():
    DATA_PATH = r"C:\Users\91986\OneDrive\Desktop\UIUC\Projects\ts-ops-dashboard\data"
    df_flags = pd.read_csv(os.path.join(DATA_PATH, "flags.csv"), parse_dates=["date"])
    df_reviewers = pd.read_csv(os.path.join(DATA_PATH, "reviewers.csv"))
    df_attacks = pd.read_csv(os.path.join(DATA_PATH, "attacks.csv"))
    return df_flags, df_reviewers, df_attacks

df_flags, df_reviewers, df_attacks = load_data()

# ── Sidebar ───────────────────────────────────────────────────────
st.sidebar.title("🛡️ T&S Ops Dashboard")
st.sidebar.markdown("**Platform Safety Monitoring**")
st.sidebar.markdown("---")

# Date filter
min_date = df_flags["date"].min().date()
max_date = df_flags["date"].max().date()

date_range = st.sidebar.date_input(
    "Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Category filter
all_categories = df_flags["category"].unique().tolist()
selected_categories = st.sidebar.multiselect(
    "Policy Categories",
    options=all_categories,
    default=all_categories
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Total flags:** {len(df_flags):,}")
st.sidebar.markdown(f"**Date range:** {min_date} to {max_date}")
st.sidebar.markdown(f"**Reviewers:** 20")

# Apply filters
if len(date_range) == 2:
    start, end = date_range
    df_filtered = df_flags[
        (df_flags["date"].dt.date >= start) &
        (df_flags["date"].dt.date <= end) &
        (df_flags["category"].isin(selected_categories))
    ]
else:
    df_filtered = df_flags[df_flags["category"].isin(selected_categories)]

# ── Header ────────────────────────────────────────────────────────
st.title("🛡️ Trust & Safety Ops Monitoring Dashboard")
st.markdown("Real-time platform safety monitoring across 6 policy categories — 90 day view")
st.markdown("---")

# ── Key Metrics Row ───────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Flags", f"{len(df_filtered):,}")
col2.metric("Auto Blocked", f"{len(df_filtered[df_filtered['action']=='auto_block']):,}")
col3.metric("Human Review", f"{len(df_filtered[df_filtered['action']=='human_review']):,}")

high_crit = df_filtered[df_filtered["severity"].isin(["high","critical"])]
sla_breach = high_crit[high_crit["resolution_hrs"] > 24]
sla_rate = len(sla_breach)/len(high_crit)*100 if len(high_crit) > 0 else 0
col4.metric("SLA Breach Rate", f"{sla_rate:.1f}%")

coord_rate = df_filtered["coordinated_flag"].mean()*100
col5.metric("Coordinated Flags", f"{coord_rate:.1f}%")

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Flag Volume & Trends",
    "🤖 Classifier Health",
    "👥 Reviewer Queue",
    "🚨 Attack Detection & Summary"
])

with tab1:
    st.subheader("📈 Daily Flag Volume by Category")

    daily_cat = (
        df_filtered.groupby(["date", "category"])
        .size()
        .reset_index(name="count")
    )

    fig1 = px.line(
        daily_cat, x="date", y="count", color="category",
        title="Daily Flag Volume by Policy Category (90 days)",
        labels={"count": "Flags", "date": "Date", "category": "Category"},
        color_discrete_map={
            "harassment": "#e74c3c",
            "hate_speech": "#8e44ad",
            "spam": "#e67e22",
            "sexual_content": "#e91e63",
            "self_harm": "#f39c12",
            "fraud": "#2980b9"
        }
    )
    fig1.update_layout(hovermode="x unified", height=400)
    st.plotly_chart(fig1, use_container_width=True)

    st.markdown("---")
    st.subheader("📊 Week-over-Week Category Trends")

    df_filtered["week"] = df_filtered["date"].dt.isocalendar().week
    weekly = df_filtered.groupby(["week", "category"]).size().reset_index(name="count")
    weekly_pivot = weekly.pivot(index="week", columns="category", values="count").fillna(0)
    pct_change = weekly_pivot.pct_change().iloc[-1] * 100

    col1, col2, col3 = st.columns(3)
    cols = [col1, col2, col3]
    for i, (cat, val) in enumerate(pct_change.items()):
        cols[i % 3].metric(
            label=cat,
            value=f"{weekly_pivot[cat].iloc[-1]:.0f} flags",
            delta=f"{val:+.1f}% vs last week"
        )

    st.markdown("---")
    st.subheader("📈 Escalation Rate Over Time")

    daily_esc = (
        df_filtered.groupby("date")
        .apply(lambda x: (x["severity"].isin(["high", "critical"])).mean() * 100)
        .reset_index(name="escalation_rate")
    )
    daily_esc["rolling_7d"] = daily_esc["escalation_rate"].rolling(7, min_periods=3).mean()

    fig_esc = go.Figure()
    fig_esc.add_trace(go.Scatter(
        x=daily_esc["date"], y=daily_esc["escalation_rate"],
        mode="lines", name="Daily Escalation Rate",
        line=dict(color="orange", width=1), opacity=0.6
    ))
    fig_esc.add_trace(go.Scatter(
        x=daily_esc["date"], y=daily_esc["rolling_7d"],
        mode="lines", name="7-day Rolling Avg",
        line=dict(color="red", width=2.5)
    ))
    fig_esc.update_layout(
        title="Escalation Rate Over Time (% High/Critical)",
        xaxis_title="Date", yaxis_title="Escalation Rate %",
        height=350, hovermode="x unified"
    )
    st.plotly_chart(fig_esc, use_container_width=True)

    st.markdown("---")
    st.subheader("🥧 Flag Distribution by Severity")

    col1, col2 = st.columns(2)
    with col1:
        sev_counts = df_filtered["severity"].value_counts()
        fig2 = px.pie(
            values=sev_counts.values,
            names=sev_counts.index,
            title="Severity Distribution",
            color=sev_counts.index,
            color_discrete_map={
                "low": "#27ae60",
                "medium": "#f39c12",
                "high": "#e67e22",
                "critical": "#e74c3c"
            }
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        action_counts = df_filtered["action"].value_counts()
        fig3 = px.bar(
            x=action_counts.index,
            y=action_counts.values,
            title="Moderation Actions Distribution",
            labels={"x": "Action", "y": "Count"},
            color=action_counts.index,
            color_discrete_map={
                "allow": "#27ae60",
                "downrank": "#f39c12",
                "human_review": "#e67e22",
                "auto_block": "#e74c3c"
            }
        )
        st.plotly_chart(fig3, use_container_width=True)

with tab2:
    st.subheader("🤖 Classifier Drift — ML Score Over Time")

    daily_ml = (
        df_filtered.groupby("date")["ml_score"]
        .mean()
        .reset_index()
    )
    daily_ml["rolling_7d"] = daily_ml["ml_score"].rolling(7, min_periods=3).mean()

    fig_drift = go.Figure()
    fig_drift.add_trace(go.Scatter(
        x=daily_ml["date"], y=daily_ml["ml_score"],
        mode="lines", name="Daily ML Score",
        line=dict(color="lightblue", width=1), opacity=0.6
    ))
    fig_drift.add_trace(go.Scatter(
        x=daily_ml["date"], y=daily_ml["rolling_7d"],
        mode="lines", name="7-day Rolling Avg",
        line=dict(color="steelblue", width=2.5)
    ))
    fig_drift.add_hline(y=0.86, line_dash="dash", line_color="green",
                        annotation_text="Baseline (0.86)")
    fig_drift.add_hline(y=0.78, line_dash="dash", line_color="red",
                        annotation_text="Drift threshold (0.78)")
    fig_drift.update_layout(
        title="Classifier Drift — ML Score Degrading Over Time",
        xaxis_title="Date", yaxis_title="Average ML Score",
        yaxis=dict(range=[0.70, 0.92]),
        height=400, hovermode="x unified"
    )
    st.plotly_chart(fig_drift, use_container_width=True)

    # Drift alert
    recent_score = daily_ml["rolling_7d"].iloc[-1]
    if recent_score < 0.80:
        st.error(f"🚨 **Drift Alert** — Current 7-day avg ML score is {recent_score:.3f}, below 0.80 threshold. Model retraining recommended.")
    elif recent_score < 0.83:
        st.warning(f"⚠️ **Drift Warning** — Current 7-day avg ML score is {recent_score:.3f}. Monitor closely.")
    else:
        st.success(f"✅ ML score healthy at {recent_score:.3f}")

    st.markdown("---")
    st.subheader("📊 ML Score Distribution by Category")

    fig_box = px.box(
        df_filtered, x="category", y="ml_score",
        color="category",
        title="ML Score Distribution by Policy Category",
        color_discrete_map={
            "harassment": "#e74c3c",
            "hate_speech": "#8e44ad",
            "spam": "#e67e22",
            "sexual_content": "#e91e63",
            "self_harm": "#f39c12",
            "fraud": "#2980b9"
        }
    )
    fig_box.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig_box, use_container_width=True)

    st.markdown("---")
    st.subheader("📈 ML Score vs Severity — Is the Model Calibrated?")

    severity_ml = df_filtered.groupby("severity")["ml_score"].mean().reindex(
        ["low", "medium", "high", "critical"]
    )
    fig_cal = px.bar(
        x=severity_ml.index, y=severity_ml.values,
        title="Average ML Score by Severity Level",
        labels={"x": "Severity", "y": "Avg ML Score"},
        color=severity_ml.index,
        color_discrete_map={
            "low": "#27ae60", "medium": "#f39c12",
            "high": "#e67e22", "critical": "#e74c3c"
        }
    )
    fig_cal.update_layout(height=350, showlegend=False)
    st.plotly_chart(fig_cal, use_container_width=True)

with tab3:
    st.subheader("👥 Reviewer Queue Load")

    # Current backlog by severity
    backlog = df_filtered[df_filtered["action"] == "human_review"]
    backlog_by_sev = backlog["severity"].value_counts().reindex(
        ["critical", "high", "medium", "low"], fill_value=0
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🔴 Critical", f"{backlog_by_sev['critical']:,}")
    col2.metric("🟠 High", f"{backlog_by_sev['high']:,}")
    col3.metric("🟡 Medium", f"{backlog_by_sev['medium']:,}")
    col4.metric("🟢 Low", f"{backlog_by_sev['low']:,}")

    st.markdown("---")

    # Daily review queue over time
    daily_queue = (
        df_filtered[df_filtered["action"] == "human_review"]
        .groupby(["date", "severity"])
        .size()
        .reset_index(name="count")
    )

    fig_queue = px.bar(
        daily_queue, x="date", y="count", color="severity",
        title="Daily Human Review Queue by Severity",
        color_discrete_map={
            "low": "#27ae60", "medium": "#f39c12",
            "high": "#e67e22", "critical": "#e74c3c"
        },
        labels={"count": "Cases", "date": "Date"}
    )
    fig_queue.update_layout(height=400, hovermode="x unified", barmode="stack")
    st.plotly_chart(fig_queue, use_container_width=True)

    st.markdown("---")
    st.subheader("👤 Reviewer Utilization")

    # Cases per reviewer
    reviewer_load = (
        df_filtered[df_filtered["action"] == "human_review"]
        .groupby("reviewer_id")
        .size()
        .reset_index(name="total_cases")
        .merge(df_reviewers, on="reviewer_id")
    )

    # Utilization = total cases / (capacity * days)
    n_days = (df_filtered["date"].max() - df_filtered["date"].min()).days + 1
    reviewer_load["utilization"] = (
        reviewer_load["total_cases"] / (reviewer_load["capacity_per_day"] * n_days) * 100
    ).round(1)

    reviewer_load = reviewer_load.sort_values("utilization", ascending=True)

    fig_util = px.bar(
        reviewer_load, x="utilization", y="reviewer_id",
        orientation="h",
        title="Reviewer Utilization % (cases / capacity)",
        color="utilization",
        color_continuous_scale=["green", "yellow", "red"],
        range_color=[0, 150],
        labels={"utilization": "Utilization %", "reviewer_id": "Reviewer"}
    )
    fig_util.add_vline(x=100, line_dash="dash", line_color="red",
                       annotation_text="100% capacity")
    fig_util.update_layout(height=500)
    st.plotly_chart(fig_util, use_container_width=True)

    st.markdown("---")
    st.subheader("⏱️ SLA Risk — High/Critical Cases")

    high_crit_q = df_filtered[
        df_filtered["severity"].isin(["high", "critical"]) &
        (df_filtered["action"] == "human_review")
    ].copy()

    sla_breach_q = high_crit_q[high_crit_q["resolution_hrs"] > 24]
    sla_ok_q = high_crit_q[high_crit_q["resolution_hrs"] <= 24]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total High/Critical in Queue", f"{len(high_crit_q):,}")
    col2.metric("SLA Breaches (>24hr)", f"{len(sla_breach_q):,}")
    col3.metric("SLA Breach Rate", f"{len(sla_breach_q)/len(high_crit_q)*100:.1f}%")

    fig_sla = px.histogram(
        high_crit_q, x="resolution_hrs", color="severity",
        title="Resolution Time Distribution — High & Critical Cases",
        color_discrete_map={"high": "#e67e22", "critical": "#e74c3c"},
        nbins=50, labels={"resolution_hrs": "Resolution Time (hrs)"}
    )
    fig_sla.add_vline(x=24, line_dash="dash", line_color="red",
                      annotation_text="24hr SLA")
    fig_sla.update_layout(height=350)
    st.plotly_chart(fig_sla, use_container_width=True)

with tab4:
    st.subheader("🚨 Coordinated Attack Detection")

    # Z-score spike detection
    daily_total = (
        df_filtered.groupby("date")
        .size()
        .reset_index(name="total_flags")
    )
    daily_total["rolling_mean"] = daily_total["total_flags"].rolling(7, min_periods=3).mean()
    daily_total["rolling_std"] = daily_total["total_flags"].rolling(7, min_periods=3).std()
    daily_total["z_score"] = (
        (daily_total["total_flags"] - daily_total["rolling_mean"]) /
        daily_total["rolling_std"]
    ).fillna(0)

    Z_THRESHOLD = 1.5
    daily_total["detected_spike"] = daily_total["z_score"] >= Z_THRESHOLD

    # Ground truth attack dates
    attack_dates = set()
    for _, atk in df_attacks.iterrows():
        start = pd.to_datetime(atk["start_date"])
        for d in range(int(atk["duration_days"])):
            attack_dates.add((start + pd.Timedelta(days=d)).date())

    daily_total["is_real_attack"] = daily_total["date"].dt.date.isin(attack_dates)

    # Detection metrics
    real_attacks = daily_total[daily_total["is_real_attack"]]
    detected = daily_total[daily_total["detected_spike"]]
    true_positives = daily_total[daily_total["is_real_attack"] & daily_total["detected_spike"]]
    false_positives = daily_total[~daily_total["is_real_attack"] & daily_total["detected_spike"]]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Real Attack Days", len(real_attacks))
    col2.metric("Detected by Z-score", len(detected))
    col3.metric("True Positives", len(true_positives))
    col4.metric("False Positives", len(false_positives))

    detection_rate = len(true_positives) / len(real_attacks) * 100 if len(real_attacks) > 0 else 0
    if detection_rate >= 80:
        st.success(f"✅ Detector caught {len(true_positives)} of {len(real_attacks)} real attack days ({detection_rate:.0f}% detection rate)")
    else:
        st.warning(f"⚠️ Detector caught {len(true_positives)} of {len(real_attacks)} real attack days ({detection_rate:.0f}% detection rate)")

    # Spike chart
    fig_spike = go.Figure()
    fig_spike.add_trace(go.Scatter(
        x=daily_total["date"], y=daily_total["total_flags"],
        mode="lines", name="Daily Flags",
        line=dict(color="steelblue", width=1.5)
    ))
    fig_spike.add_trace(go.Scatter(
        x=daily_total["date"], y=daily_total["rolling_mean"],
        mode="lines", name="7-day Rolling Mean",
        line=dict(color="lightblue", width=1, dash="dash")
    ))

    # Mark detected spikes
    spikes = daily_total[daily_total["detected_spike"]]
    fig_spike.add_trace(go.Scatter(
        x=spikes["date"], y=spikes["total_flags"],
        mode="markers", name="Detected Spike",
        marker=dict(color="red", size=10, symbol="circle")
    ))

    # Mark real attacks
    real_atk_days = daily_total[daily_total["is_real_attack"]]
    fig_spike.add_trace(go.Scatter(
        x=real_atk_days["date"], y=real_atk_days["total_flags"],
        mode="markers", name="Real Attack Day (ground truth)",
        marker=dict(color="orange", size=8, symbol="diamond")
    ))

    fig_spike.update_layout(
        title="Daily Flag Volume with Coordinated Attack Detection",
        xaxis_title="Date", yaxis_title="Total Flags",
        height=450, hovermode="x unified"
    )
    st.plotly_chart(fig_spike, use_container_width=True)

    st.markdown("---")
    st.subheader("📋 Known Attack Events")
    st.dataframe(
        df_attacks[["attack_id", "category", "start_date", "duration_days", "num_accounts", "severity", "pattern"]],
        use_container_width=True
    )

    st.markdown("---")
    st.subheader("📝 AI-Generated Weekly Ops Summary")
    st.markdown("Click below to generate a plain-English ops summary using Claude API based on current dashboard metrics.")

    if st.button("🤖 Generate Weekly Summary", type="primary"):
        # Build real metrics for Claude
        last_7 = df_filtered[df_filtered["date"] >= df_filtered["date"].max() - pd.Timedelta(days=7)]
        prev_7 = df_filtered[
            (df_filtered["date"] >= df_filtered["date"].max() - pd.Timedelta(days=14)) &
            (df_filtered["date"] < df_filtered["date"].max() - pd.Timedelta(days=7))
        ]

        top_cat = last_7["category"].value_counts().index[0]
        top_cat_count = last_7["category"].value_counts().iloc[0]
        prev_top_count = prev_7["category"].value_counts().get(top_cat, 1)
        pct_change_top = ((top_cat_count - prev_top_count) / prev_top_count * 100)

        last_7_sla = last_7[last_7["severity"].isin(["high", "critical"])]
        sla_breach_last = last_7_sla[last_7_sla["resolution_hrs"] > 24]
        sla_rate_last = len(sla_breach_last) / len(last_7_sla) * 100 if len(last_7_sla) > 0 else 0

        # Fix ML score — use actual ml_score column not flag counts
        daily_ml_scores = (
            df_filtered.groupby("date")["ml_score"]
            .mean()
            .reset_index()
        )
        daily_ml_scores["rolling_7d"] = daily_ml_scores["ml_score"].rolling(7, min_periods=3).mean()
        recent_ml = daily_ml_scores["rolling_7d"].iloc[-1]

        spikes_last_7 = daily_total[
            (daily_total["date"] >= df_filtered["date"].max() - pd.Timedelta(days=7)) &
            (daily_total["detected_spike"])
        ]

        prompt = f"""You are a Trust & Safety operations analyst writing a weekly summary for leadership.

Here are this week's platform safety metrics:

- Total flags this week: {len(last_7):,}
- Top violation category: {top_cat} ({top_cat_count:,} flags, {pct_change_top:+.1f}% vs last week)
- SLA breach rate (high/critical cases >24hr): {sla_rate_last:.1f}%
- Current ML classifier score (7-day avg): {recent_ml:.3f} (baseline was 0.86, drift threshold is 0.78)
- Coordinated attack spikes detected this week: {len(spikes_last_7)}
- Total reviewers: 20
- Auto-blocked this week: {len(last_7[last_7['action']=='auto_block']):,}
- Sent to human review this week: {len(last_7[last_7['action']=='human_review']):,}

Write a concise weekly ops summary with these sections:
1. TOP RISKS THIS WEEK (2-3 bullet points)
2. CATEGORY TO WATCH (which category is most concerning and why)
3. CLASSIFIER HEALTH (is drift a concern, what action to take)
4. STAFFING RECOMMENDATION (based on queue load and SLA breach rate)
5. KEY METRIC TO WATCH NEXT WEEK (one specific thing)

Be specific, use the numbers provided, write like a senior T&S analyst. Keep it under 300 words."""

        with st.spinner("Claude is generating your weekly ops summary..."):
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}]
            )
            summary = response.content[0].text

        st.markdown("---")
        st.markdown("### 📊 Weekly Ops Summary")
        st.markdown(summary)
        st.caption(f"Generated by Claude API (claude-sonnet-4-5) based on live dashboard metrics")