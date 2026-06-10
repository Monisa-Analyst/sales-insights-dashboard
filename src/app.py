"""
app.py — main streamlit dashboard
Includes four pages: analytics dashboard, data submission,
data quality monitoring, and the AI query assistant.
Run with: streamlit run src/app.py
"""

import os, sqlite3, json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from ai_agent import SalesAIAgent
from ingestion import (
    clean_dataframe, run_quality_checks, determine_verdict,
    merge_into_database, run_production_checks
)
from batch_log import log_batch, get_batch_history, get_pending_alerts

st.set_page_config(page_title="Sales Analytics", page_icon="🛒", layout="wide", initial_sidebar_state="expanded")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# on streamlit cloud the project dir is read-only, so we use /tmp for the db
if os.path.exists("/mount/src/sales-insights-dashboard"):
    DB = "/tmp/sales.db"
    # seed the /tmp db from the bundled copy on first run
    bundled = os.path.join(ROOT, "data", "sales.db")
    if not os.path.exists(DB) and os.path.exists(bundled):
        import shutil
        shutil.copy2(bundled, DB)
else:
    DB = os.path.join(ROOT, "data", "sales.db")

# auto-build database on first run if it doesn't exist
if not os.path.exists(DB):
    st.info("Database not found — building it from the raw dataset now...")
    with st.spinner("Downloading and parsing sales records... hang tight."):
        try:
            import sys
            sys.path.append(ROOT)
            sys.path.append(os.path.join(ROOT, "src"))
            import data_loader
            data_loader.setup_folders()
            data_loader.grab_dataset()
            data_loader.build_tables()
            st.success("Database ready! Refreshing...")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to build database: {e}")
            st.warning("Try running `python src/data_loader.py` manually.")
            st.stop()


# --- Styling ---

def apply_styles():
    st.markdown("""<style>
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');

        html, body, [class*="css"], .stApp {
            font-family: 'Nunito', sans-serif !important;
            background: #fafaf8 !important;
            color: #2d2d2d !important;
        }

        section[data-testid="stSidebar"] { background: #1a1a2e !important; }
        section[data-testid="stSidebar"] * { color: #b8b8d0 !important; }
        section[data-testid="stSidebar"] h2 { color: #22d3ae !important; }
        section[data-testid="stSidebar"] .stRadio label span { font-size: 14px !important; }

        .top-banner {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 18px; padding: 36px 42px; margin-bottom: 28px; color: white;
        }
        .top-banner h1 { font-size: 32px; font-weight: 800; margin: 0 0 6px 0; color: #ffffff !important; }
        .top-banner p { color: #8b8ba8; font-size: 15px; margin: 0; }

        .stats-row { display: flex; gap: 18px; margin-bottom: 26px; }
        .stat-box {
            flex: 1; background: white; border-radius: 14px; padding: 22px 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04); border-left: 4px solid transparent;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .stat-box:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,0,0,0.07); }
        .stat-box.teal   { border-left-color: #14b8a6; }
        .stat-box.green  { border-left-color: #22c55e; }
        .stat-box.coral  { border-left-color: #f97316; }
        .stat-box.purple { border-left-color: #8b5cf6; }

        .stat-label { font-size: 12px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
        .stat-num { font-size: 28px; font-weight: 800; color: #1f2937; margin: 0; }
        .stat-hint { font-size: 11px; color: #b0b0b0; margin-top: 4px; }

        .chart-wrap {
            background: white; border-radius: 14px; padding: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04); margin-bottom: 22px;
        }
        .chart-wrap h3 { font-size: 16px; font-weight: 700; color: #1f2937; margin: 0 0 4px 0; }
        .chart-wrap .subtitle { font-size: 12px; color: #9ca3af; margin-bottom: 16px; }

        .query-box {
            background: white; border-radius: 14px; padding: 26px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04); margin-bottom: 20px;
        }
        .query-box h3 { font-size: 16px; font-weight: 700; color: #1f2937; margin: 0 0 12px 0; }

        .result-summary {
            background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px;
            padding: 20px 24px; line-height: 1.75; color: #374151; font-size: 14px;
        }

        div[data-testid="stButton"] > button {
            background: #f0fdfa !important; color: #0f766e !important;
            border: 1px solid #99f6e4 !important; border-radius: 20px !important;
            font-weight: 600 !important; font-size: 13px !important; transition: all 0.2s !important;
        }
        div[data-testid="stButton"] > button:hover {
            background: #14b8a6 !important; color: white !important; border-color: #14b8a6 !important;
        }

        hr { border-color: #f0f0f0 !important; }
        .stDataFrame { border-radius: 12px !important; overflow: hidden; }

        /* alert cards for data quality */
        .dq-card {
            background: white; border-radius: 12px; padding: 16px 20px;
            border-left: 4px solid #94a3b8; margin-bottom: 10px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        }
        .dq-card.pass { border-left-color: #22c55e; }
        .dq-card.warn { border-left-color: #f59e0b; }
        .dq-card.fail { border-left-color: #ef4444; }
        .dq-card .label { font-size: 0.78rem; font-weight: 700; color: #64748b; text-transform: uppercase; }
        .dq-card .value { font-size: 1.1rem; font-weight: 700; color: #1e293b; }
    </style>""", unsafe_allow_html=True)


def chart_style(**extra):
    base = dict(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Nunito', color='#6b7280', size=12),
        margin=dict(l=16, r=16, t=8, b=16), height=330,
        xaxis=dict(showgrid=False, linecolor='#e5e7eb', tickfont=dict(size=11)),
        yaxis=dict(showgrid=True, gridcolor='#f5f5f5', linecolor='#e5e7eb', tickfont=dict(size=11)),
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Nunito"),
        legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center", font=dict(size=11)),
    )
    base.update(extra)
    return base


def query_db(sql, params=()):
    if not os.path.exists(DB):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB)
        df = pd.read_sql_query(sql, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        st.error(f"query error: {e}")
        return pd.DataFrame()


def load_agent():
    return SalesAIAgent()

agent = load_agent()


def get_filters():
    yrs = ["All"] + sorted([str(int(y)) for y in query_db(
        "SELECT DISTINCT SUBSTR(order_date, 1, 4) as yr FROM orders WHERE yr IS NOT NULL")['yr'].tolist()])
    mkts = ["All"] + sorted(query_db("SELECT DISTINCT market FROM locations")['market'].tolist())
    segs = ["All"] + sorted(query_db("SELECT DISTINCT segment FROM customers")['segment'].tolist())
    return yrs, mkts, segs


# --- Layout Setup ---
apply_styles()

st.sidebar.markdown("## 🛒 Sales Analytics")
st.sidebar.caption("v2.0 — now with live data ingestion")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    ["📊 Dashboard", "📥 Submit Data", "🔍 Data Quality", "🤖 Ask AI"],
    label_visibility="collapsed"
)
st.sidebar.markdown("---")

# show alert count in sidebar if there are pending reviews
alerts = get_pending_alerts()
if alerts:
    st.sidebar.warning(f"⚠️ {len(alerts)} batch(es) need analyst review")

st.sidebar.markdown("### 🔗 Portfolio Links")
st.sidebar.markdown("- 🐙 [GitHub Profile](https://github.com/Monisa-Analyst)")
st.sidebar.markdown("- 🛡️ [Sentinel SOC Triage Platform](https://share.streamlit.io/monisa-analyst/ai-soc-analyst/main/app.py)")
st.sidebar.markdown("- 💼 [LinkedIn Profile](https://www.linkedin.com/in/monisa-l-333546366)")
st.sidebar.markdown("---")


# =====================================================================
# Page 1: Dashboard
# =====================================================================
if page == "📊 Dashboard":

    st.markdown("""<div class="top-banner">
        <h1>Sales Overview</h1>
        <p>Key metrics and trends from your e-commerce data</p>
    </div>""", unsafe_allow_html=True)

    yrs, mkts, segs = get_filters()
    st.sidebar.markdown("### Filters")
    yr = st.sidebar.selectbox("Year", yrs)
    mkt = st.sidebar.selectbox("Market", mkts)
    seg = st.sidebar.selectbox("Segment", segs)

    conditions, params = [], []
    if yr != "All":
        conditions.append("SUBSTR(o.order_date, 1, 4) = ?"); params.append(yr)
    if mkt != "All":
        conditions.append("l.market = ?"); params.append(mkt)
    if seg != "All":
        conditions.append("c.segment = ?"); params.append(seg)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    kpis = query_db(f"""
        SELECT SUM(oi.sales) as rev, SUM(oi.profit) as profit,
               COUNT(DISTINCT o.order_id) as orders, COUNT(DISTINCT o.customer_id) as custs
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN locations l ON o.location_id = l.location_id {where}
    """, params)

    rev = kpis['rev'].iloc[0] or 0
    profit = kpis['profit'].iloc[0] or 0
    num_orders = kpis['orders'].iloc[0] or 0
    num_custs = kpis['custs'].iloc[0] or 0
    margin_pct = (profit / rev * 100) if rev > 0 else 0

    st.markdown(f"""<div class="stats-row">
        <div class="stat-box teal">
            <div class="stat-label">Revenue</div>
            <div class="stat-num">${rev:,.0f}</div>
            <div class="stat-hint">total gross sales</div>
        </div>
        <div class="stat-box green">
            <div class="stat-label">Profit</div>
            <div class="stat-num">${profit:,.0f}</div>
            <div class="stat-hint">net after costs</div>
        </div>
        <div class="stat-box coral">
            <div class="stat-label">Margin</div>
            <div class="stat-num">{margin_pct:.1f}%</div>
            <div class="stat-hint">profit / revenue</div>
        </div>
        <div class="stat-box purple">
            <div class="stat-label">Customers</div>
            <div class="stat-num">{num_custs:,}</div>
            <div class="stat-hint">{num_orders:,} orders total</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # monthly trend
    trend = query_db(f"""
        SELECT SUBSTR(o.order_date, 1, 7) as month,
               SUM(oi.sales) as sales, SUM(oi.profit) as profit
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN locations l ON o.location_id = l.location_id {where}
        GROUP BY month ORDER BY month
    """, params)

    if not trend.empty:
        st.markdown("""<div class="chart-wrap">
            <h3>Monthly Sales & Profit</h3>
            <div class="subtitle">Revenue vs profit over time</div>
        """, unsafe_allow_html=True)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend['month'], y=trend['sales'], name='Revenue',
            mode='lines', line=dict(color='#14b8a6', width=2.5, shape='spline'),
            fill='tozeroy', fillcolor='rgba(20,184,166,0.06)'
        ))
        fig.add_trace(go.Scatter(
            x=trend['month'], y=trend['profit'], name='Profit',
            mode='lines', line=dict(color='#f97316', width=2.5, shape='spline'),
            fill='tozeroy', fillcolor='rgba(249,115,22,0.04)'
        ))
        fig.update_layout(**chart_style(height=300))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # category + customers row
    left, right = st.columns([1, 1.3])

    with left:
        cats = query_db(f"""
            SELECT p.category, SUM(oi.sales) as sales
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            JOIN orders o ON oi.order_id = o.order_id
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN locations l ON o.location_id = l.location_id {where}
            GROUP BY p.category ORDER BY sales DESC
        """, params)

        if not cats.empty:
            st.markdown("""<div class="chart-wrap">
                <h3>Sales by Category</h3>
                <div class="subtitle">Product line breakdown</div>
            """, unsafe_allow_html=True)
            fig_cat = px.pie(cats, values='sales', names='category', hole=0.5,
                             color_discrete_sequence=['#14b8a6', '#f97316', '#8b5cf6'])
            fig_cat.update_traces(textinfo='label+percent',
                                  marker=dict(line=dict(color='white', width=2)))
            fig_cat.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                                   font=dict(family='Nunito', color='#6b7280'),
                                   margin=dict(l=8, r=8, t=8, b=8), height=340, showlegend=False)
            st.plotly_chart(fig_cat, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    with right:
        top_custs = query_db(f"""
            SELECT c.customer_name, SUM(oi.sales) as spent
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN locations l ON o.location_id = l.location_id {where}
            GROUP BY c.customer_name ORDER BY spent DESC LIMIT 8
        """, params)

        if not top_custs.empty:
            st.markdown("""<div class="chart-wrap">
                <h3>Top Customers</h3>
                <div class="subtitle">By total revenue generated</div>
            """, unsafe_allow_html=True)
            top_custs['name'] = top_custs['customer_name'].apply(
                lambda x: x[:20] + '...' if len(x) > 20 else x)
            fig_c = px.bar(top_custs.sort_values('spent'), x='spent', y='name',
                           orientation='h', color_discrete_sequence=['#14b8a6'],
                           labels={'spent': 'Revenue ($)', 'name': ''})
            fig_c.update_layout(**chart_style(
                height=340,
                yaxis=dict(showgrid=False, linecolor='#e5e7eb', tickfont=dict(size=11)),
                xaxis=dict(showgrid=True, gridcolor='#f5f5f5', linecolor='#e5e7eb')
            ))
            fig_c.update_traces(marker_cornerradius=5)
            st.plotly_chart(fig_c, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # products + markets row
    c1, c2 = st.columns(2)

    with c1:
        prods = query_db(f"""
            SELECT p.product_name, SUM(oi.quantity) as qty
            FROM order_items oi JOIN products p ON oi.product_id = p.product_id
            JOIN orders o ON oi.order_id = o.order_id
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN locations l ON o.location_id = l.location_id {where}
            GROUP BY p.product_name ORDER BY qty DESC LIMIT 6
        """, params)

        if not prods.empty:
            st.markdown("""<div class="chart-wrap">
                <h3>Top Products</h3>
                <div class="subtitle">Most purchased items by volume</div>
            """, unsafe_allow_html=True)
            prods['short'] = prods['product_name'].apply(lambda x: x[:18] + '...' if len(x) > 18 else x)
            fig_p = px.bar(prods, x='short', y='qty', color_discrete_sequence=['#8b5cf6'],
                           labels={'qty': 'Units', 'short': ''})
            fig_p.update_layout(**chart_style(
                height=320,
                xaxis=dict(showgrid=False, linecolor='#e5e7eb', tickangle=-25, tickfont=dict(size=10)),
                yaxis=dict(showgrid=True, gridcolor='#f5f5f5', linecolor='#e5e7eb')
            ))
            fig_p.update_traces(marker_cornerradius=6)
            st.plotly_chart(fig_p, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        markets = query_db(f"""
            SELECT l.market, SUM(oi.sales) as sales, SUM(oi.profit) as profit
            FROM order_items oi JOIN orders o ON oi.order_id = o.order_id
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN locations l ON o.location_id = l.location_id {where}
            GROUP BY l.market ORDER BY sales DESC
        """, params)

        if not markets.empty:
            st.markdown("""<div class="chart-wrap">
                <h3>Revenue by Market</h3>
                <div class="subtitle">Sales and profit across regions</div>
            """, unsafe_allow_html=True)
            fig_m = px.bar(markets, x='market', y=['sales', 'profit'], barmode='group',
                           color_discrete_sequence=['#14b8a6', '#f97316'],
                           labels={'value': '$', 'market': '', 'variable': ''})
            fig_m.update_layout(**chart_style(
                height=320,
                xaxis=dict(showgrid=False, linecolor='#e5e7eb'),
                yaxis=dict(showgrid=True, gridcolor='#f5f5f5', linecolor='#e5e7eb')
            ))
            fig_m.update_traces(marker_cornerradius=6)
            st.plotly_chart(fig_m, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# Page 2: Submit Data
# =====================================================================
elif page == "📥 Submit Data":

    st.markdown("""<div class="top-banner">
        <h1>Submit Sales Data</h1>
        <p>Upload a CSV or Excel file to add new records to the analytics database</p>
    </div>""", unsafe_allow_html=True)

    st.markdown("""
    **How it works:**
    1. Upload your file — we'll auto-detect and map columns to the database schema
    2. Data gets cleaned (dates parsed, currency stripped, missing values filled)
    3. Nine SQL validation checks run against your batch
    4. If the data passes quality thresholds, it's merged into the live database
    """)

    if os.path.exists("/mount/src/sales-insights-dashboard"):
        st.info("☁️ **Cloud mode** — uploaded data persists for your current session. "
                "The database resets when the app restarts after inactivity.")

    st.markdown("---")

    uploaded = st.file_uploader(
        "Drop your sales data file here",
        type=["csv", "xlsx", "xls"],
        help="CSV or Excel files with columns like Order ID, Customer Name, Sales, etc."
    )

    if uploaded:
        # parse the file
        try:
            if uploaded.name.endswith((".xlsx", ".xls")):
                raw_df = pd.read_excel(uploaded, engine="openpyxl")
            else:
                raw_df = pd.read_csv(uploaded, encoding="latin-1")
        except Exception as e:
            st.error(f"Couldn't read the file: {e}")
            st.stop()

        st.markdown(f"### 📄 File Preview — `{uploaded.name}` ({len(raw_df):,} rows)")
        st.dataframe(raw_df.head(10), use_container_width=True)

        # step 1: clean and map columns
        st.markdown("---")
        with st.spinner("Mapping columns and cleaning data..."):
            cleaned, mapping, warnings = clean_dataframe(raw_df)

        if cleaned is None:
            st.error("❌ Could not map any columns from this file to our schema.")
            for w in warnings:
                st.warning(w)
            st.stop()

        # show column mapping
        st.markdown("### 🔗 Column Mapping")
        map_col1, map_col2 = st.columns(2)
        with map_col1:
            st.markdown("**Your Column → Our Schema**")
            for our_name, their_col in mapping.items():
                st.markdown(f"- `{their_col}` → **{our_name}**")
        with map_col2:
            if warnings:
                st.markdown("**⚠️ Warnings**")
                for w in warnings:
                    st.warning(w)

        st.markdown(f"**Cleaned rows ready for validation:** {len(cleaned):,}")

        # step 2: run quality checks
        st.markdown("---")
        st.markdown("### 🧪 Data Quality Validation")

        with st.spinner("Running SQL consistency checks..."):
            issues, health = run_quality_checks(cleaned)
            verdict = determine_verdict(health)

        # health score display
        health_color = "#22c55e" if health >= 80 else "#f59e0b" if health >= 50 else "#ef4444"
        st.markdown(f"""<div class="stats-row">
            <div class="stat-box" style="border-left-color: {health_color};">
                <div class="stat-label">Batch Health Score</div>
                <div class="stat-num" style="color: {health_color};">{health}%</div>
                <div class="stat-hint">{verdict}</div>
            </div>
            <div class="stat-box teal">
                <div class="stat-label">Rows Parsed</div>
                <div class="stat-num">{len(cleaned):,}</div>
                <div class="stat-hint">from {uploaded.name}</div>
            </div>
            <div class="stat-box purple">
                <div class="stat-label">Checks Run</div>
                <div class="stat-num">{len(issues)}</div>
                <div class="stat-hint">{sum(1 for i in issues if i['passed'])} passed</div>
            </div>
        </div>""", unsafe_allow_html=True)

        # individual check results
        for issue in issues:
            if issue["passed"]:
                card_class = "pass"
                icon = "✅"
            elif issue["severity"] == "info":
                card_class = "pass"
                icon = "ℹ️"
            elif issue["severity"] == "warning":
                card_class = "warn"
                icon = "⚠️"
            else:
                card_class = "fail"
                icon = "🔴"

            st.markdown(f"""<div class="dq-card {card_class}">
                <div class="label">{icon} {issue['name']}</div>
                <div class="value">{issue['count']} row(s) flagged</div>
                <div style="font-size:0.82rem;color:#64748b;">{issue['desc']}</div>
            </div>""", unsafe_allow_html=True)

        # step 3: merge or reject
        st.markdown("---")
        if verdict == "Accepted":
            st.success(f"✅ **Batch Accepted** — health score {health}%. Click below to merge into the database.")
            if st.button("▶️ Merge into Database", type="primary"):
                with st.spinner("Merging records..."):
                    accepted = merge_into_database(cleaned)
                    log_batch(uploaded.name, len(raw_df), "Accepted", health,
                              issues, accepted, 0)
                st.success(f"🎉 Done! {accepted:,} records merged. Switch to the Dashboard to see updated charts.")
                st.balloons()

        elif verdict == "Needs Review":
            st.warning(f"⚠️ **Needs Analyst Review** — health score {health}%. "
                       f"Some quality checks flagged issues. You can still force-merge, but review the warnings first.")
            col_merge, col_skip = st.columns(2)
            with col_merge:
                if st.button("⚡ Force Merge Anyway", type="primary"):
                    with st.spinner("Merging records..."):
                        accepted = merge_into_database(cleaned)
                        log_batch(uploaded.name, len(raw_df), "Needs Review", health,
                                  issues, accepted, 0)
                    st.success(f"Merged {accepted:,} records. Check the Data Quality page for details.")
            with col_skip:
                if st.button("🛑 Skip This Batch"):
                    log_batch(uploaded.name, len(raw_df), "Needs Review", health,
                              issues, 0, len(raw_df))
                    st.info("Batch logged but not merged. An analyst can review it on the Data Quality page.")

        else:
            st.error(f"🔴 **Batch Rejected** — health score {health}%. "
                     f"Too many quality issues to merge safely. Fix the data and re-upload.")
            log_batch(uploaded.name, len(raw_df), "Rejected", health,
                      issues, 0, len(raw_df))

            # offer a download of the cleaned data so they can inspect what went wrong
            csv_download = cleaned.to_csv(index=False)
            st.download_button(
                "⬇️ Download Cleaned Data for Review",
                data=csv_download,
                file_name=f"cleaned_{uploaded.name}.csv",
                mime="text/csv"
            )


# =====================================================================
# Page 3: Data Quality
# =====================================================================
elif page == "🔍 Data Quality":

    st.markdown("""<div class="top-banner">
        <h1>Data Quality Monitor</h1>
        <p>Batch submission log, active alerts, and live database consistency checks</p>
    </div>""", unsafe_allow_html=True)

    # active alerts section
    pending = get_pending_alerts()
    if pending:
        st.markdown("### 🚨 Active Alerts — Batches Needing Review")
        for batch in pending:
            with st.expander(f"Batch #{batch['batch_id']} — {batch['filename']} ({batch['submitted_at']})"):
                st.markdown(f"- **Rows:** {batch['row_count']:,}")
                st.markdown(f"- **Health Score:** {batch['health_score']}%")
                st.markdown(f"- **Status:** {batch['status']}")

                try:
                    batch_issues = json.loads(batch.get("issues_json") or "[]")
                    failed = [i for i in batch_issues if not i.get("passed", True)]
                    if failed:
                        st.markdown("**Issues found:**")
                        for issue in failed:
                            st.markdown(f"- ⚠️ **{issue['name']}**: {issue['count']} row(s) — {issue['desc']}")
                except (json.JSONDecodeError, TypeError):
                    st.caption("No issue details available.")

        st.markdown("---")
    else:
        st.success("✅ No pending alerts — all batches are clean.")
        st.markdown("---")

    # live production database checks
    st.markdown("### 🏥 Live Database Health")
    st.caption("These checks run against the current production database right now.")

    with st.spinner("Running consistency checks..."):
        prod_checks = run_production_checks()

    for check in prod_checks:
        if check["count"] == 0:
            card_class = "pass"
            icon = "✅" if check["severity"] != "info" else "ℹ️"
        elif check["count"] == -1:
            card_class = "fail"
            icon = "❌"
        elif check["severity"] == "critical":
            card_class = "fail"
            icon = "🔴"
        elif check["severity"] == "warning":
            card_class = "warn"
            icon = "⚠️"
        else:
            card_class = "pass"
            icon = "ℹ️"

        count_str = f"{check['count']} issue(s)" if check["count"] > 0 else ("OK" if check["count"] == 0 else "Error")
        st.markdown(f"""<div class="dq-card {card_class}">
            <div class="label">{icon} {check['name']}</div>
            <div class="value">{count_str}</div>
            <div style="font-size:0.82rem;color:#64748b;">{check['desc']}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # batch history table
    st.markdown("### 📋 Submission History")
    history = get_batch_history()

    if history:
        hist_df = pd.DataFrame(history)
        display_cols = ["batch_id", "submitted_at", "filename", "row_count", "status", "health_score", "accepted_rows", "rejected_rows"]
        display_cols = [c for c in display_cols if c in hist_df.columns]
        hist_df = hist_df[display_cols].rename(columns={
            "batch_id": "ID", "submitted_at": "Submitted", "filename": "File",
            "row_count": "Rows", "status": "Status", "health_score": "Health %",
            "accepted_rows": "Accepted", "rejected_rows": "Rejected"
        })
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
    else:
        st.info("No submissions yet. Upload data from the **Submit Data** page to get started.")


# =====================================================================
# Page 4: Ask AI
# =====================================================================
elif page == "🤖 Ask AI":

    st.markdown("""<div class="top-banner">
        <h1>Ask AI</h1>
        <p>Type a question in plain english and get SQL results instantly</p>
    </div>""", unsafe_allow_html=True)

    if agent.initialized:
        st.success("✅ Gemini AI connected — ask any question about your sales data.")
    else:
        st.info("Running in **demo mode** — add your GEMINI_API_KEY to `.env` for full AI.")

    st.markdown("""<div class="query-box">
        <h3>Try one of these</h3>
    """, unsafe_allow_html=True)
    s1, s2, s3, s4 = st.columns(4)
    if s1.button("Top 5 customers", use_container_width=True):
        st.session_state.q = "Who are the top 5 customers by sales?"
    if s2.button("March sales", use_container_width=True):
        st.session_state.q = "What were the sales in March 2014?"
    if s3.button("Best product", use_container_width=True):
        st.session_state.q = "What is the best selling product by quantity?"
    if s4.button("Profit by region", use_container_width=True):
        st.session_state.q = "Show me total profit by market region"
    st.markdown("</div>", unsafe_allow_html=True)

    if 'q' not in st.session_state:
        st.session_state.q = ""

    question = st.text_input("Your question:", value=st.session_state.q,
                              placeholder="e.g. What was the revenue growth in 2014?")

    if question:
        st.markdown("---")
        with st.spinner("thinking..."):
            sql = agent.translate_to_sql(question)

        st.markdown("""<div class="query-box"><h3>🔎 SQL Query</h3>""", unsafe_allow_html=True)
        st.code(sql, language="sql")
        st.markdown("</div>", unsafe_allow_html=True)

        df, err = agent.execute_query(sql)

        if err:
            st.error(f"Error: {err}")
            st.info("Try rephrasing — the query might use unsupported syntax.")
        elif df is not None:
            if df.empty:
                st.info("No results found.")
            else:
                st.markdown("""<div class="query-box"><h3>📋 Results</h3>""", unsafe_allow_html=True)
                st.dataframe(df, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

                with st.spinner("analyzing results..."):
                    explanation = agent.generate_explanation(question, sql, df)

                st.markdown(f"""<div class="query-box">
                    <h3>💡 Analysis</h3>
                    <div class="result-summary">{explanation}</div>
                </div>""", unsafe_allow_html=True)
