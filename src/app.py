import os
import sqlite3
import streamlit as pd_st # importing normal streamlit below as st
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from ai_agent import SalesAIAgent

# Configure page metadata and layout
st.set_page_config(
    page_title="AI-Powered Sales Analytics Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database and file paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "sales.db")

# Injects premium CSS styling (glassmorphism cards, custom font gradients, hover effects)
def inject_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background: radial-gradient(circle at top right, #0F172A 0%, #020617 100%);
        color: #F8FAFC;
    }
    
    /* Custom Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #0B0F19 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Glassmorphism Metric Cards */
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 20px;
        margin-bottom: 25px;
    }
    
    .kpi-card {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 24px;
        text-align: left;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        transition: all 0.3s ease-in-out;
    }
    
    .kpi-card:hover {
        transform: translateY(-4px);
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow: 0 12px 40px 0 rgba(99, 102, 241, 0.15);
    }
    
    .kpi-title {
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #94A3B8;
        margin-bottom: 8px;
    }
    
    .kpi-value {
        font-size: 30px;
        font-weight: 700;
        background: linear-gradient(135deg, #818CF8 0%, #34D399 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }

    .kpi-sub {
        font-size: 11px;
        color: #64748B;
        margin-top: 6px;
    }
    
    /* Query Suggestion Pill Buttons */
    .suggestion-btn {
        background: rgba(99, 102, 241, 0.1);
        border: 1px solid rgba(99, 102, 241, 0.2);
        color: #C7D2FE;
        border-radius: 20px;
        padding: 6px 14px;
        display: inline-block;
        margin: 5px;
        cursor: pointer;
        transition: all 0.2s;
    }
    .suggestion-btn:hover {
        background: rgba(99, 102, 241, 0.25);
        border-color: rgba(99, 102, 241, 0.5);
    }
    
    /* Header Gradient Text */
    .header-title {
        font-size: 40px;
        font-weight: 700;
        background: linear-gradient(135deg, #FFFFFF 30%, #818CF8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# Helper function to query local DB
def run_db_query(query, params=()):
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database Query Error: {e}")
        return pd.DataFrame()

# Initialize AI agent
@st.cache_resource
def get_ai_agent():
    return SalesAIAgent()

ai_agent = get_ai_agent()

# Load filter options
def get_filter_values():
    years = ["All"] + sorted([str(int(y)) for y in run_db_query("SELECT DISTINCT SUBSTR(order_date, 1, 4) as yr FROM orders WHERE yr IS NOT NULL")['yr'].tolist()])
    markets = ["All"] + sorted(run_db_query("SELECT DISTINCT market FROM locations")['market'].tolist())
    segments = ["All"] + sorted(run_db_query("SELECT DISTINCT segment FROM customers")['segment'].tolist())
    return years, markets, segments

inject_custom_css()

# Sidebar Setup
st.sidebar.markdown("<h2 style='color: #818CF8; font-weight:700;'>📊 Sales Analyst</h2>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# Navigation option
page = st.sidebar.radio("Navigation", ["📈 Executive Dashboard", "🤖 AI Query Assistant"])

st.sidebar.markdown("---")

if page == "📈 Executive Dashboard":
    st.markdown("<h1 class='header-title'>Executive Sales Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94A3B8; font-size:16px; margin-bottom: 25px;'>Analyze high-level sales KPIs, customer values, and MoM performance trends.</p>", unsafe_allow_html=True)
    
    # Check if DB exists
    if not os.path.exists(DB_PATH):
        st.warning("⚠️ Local SQLite Database not found! Please run the data loader first using `python src/data_loader.py` to initialize data.")
        st.stop()

    # Load filters in sidebar
    years, markets, segments = get_filter_values()
    
    st.sidebar.markdown("### Global Filters")
    selected_year = st.sidebar.selectbox("Year", years)
    selected_market = st.sidebar.selectbox("Market Region", markets)
    selected_segment = st.sidebar.selectbox("Customer Segment", segments)

    # Build filtered query dynamically
    where_clauses = []
    params = []

    if selected_year != "All":
        where_clauses.append("SUBSTR(o.order_date, 1, 4) = ?")
        params.append(selected_year)
    if selected_market != "All":
        where_clauses.append("l.market = ?")
        params.append(selected_market)
    if selected_segment != "All":
        where_clauses.append("c.segment = ?")
        params.append(selected_segment)

    where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # 1. Fetch KPI Metrics
    kpi_query = f"""
        SELECT 
            SUM(oi.sales) as total_sales,
            SUM(oi.profit) as total_profit,
            COUNT(DISTINCT o.order_id) as total_orders
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN locations l ON o.location_id = l.location_id
        {where_str}
    """
    kpi_df = run_db_query(kpi_query, params)
    
    total_sales = kpi_df['total_sales'].iloc[0] or 0.0
    total_profit = kpi_df['total_profit'].iloc[0] or 0.0
    total_orders = kpi_df['total_orders'].iloc[0] or 0
    margin = (total_profit / total_sales * 100) if total_sales > 0 else 0.0

    # Display KPI Cards via Custom HTML/CSS
    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-card">
            <div class="kpi-title">Total Revenue</div>
            <div class="kpi-value">${total_sales:,.2f}</div>
            <div class="kpi-sub">Total gross sales value</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Total Profit</div>
            <div class="kpi-value" style="background: linear-gradient(135deg, #34D399 0%, #10B981 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">${total_profit:,.2f}</div>
            <div class="kpi-sub">Net profits accrued</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Profit Margin</div>
            <div class="kpi-value" style="background: linear-gradient(135deg, #60A5FA 0%, #3B82F6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{margin:.2f}%</div>
            <div class="kpi-sub">Percentage margin efficiency</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Order Count</div>
            <div class="kpi-value" style="background: linear-gradient(135deg, #FBBF24 0%, #F59E0B 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{total_orders:,}</div>
            <div class="kpi-sub">Distinct client sales orders</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Charts Section
    col1, col2 = st.columns([2, 1.2])

    with col1:
        # Sales and Profit Trend over time
        trend_query = f"""
            SELECT 
                SUBSTR(o.order_date, 1, 7) as yr_mo,
                SUM(oi.sales) as monthly_sales,
                SUM(oi.profit) as monthly_profit
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN locations l ON o.location_id = l.location_id
            {where_str}
            GROUP BY yr_mo
            ORDER BY yr_mo
        """
        trend_df = run_db_query(trend_query, params)

        if not trend_df.empty:
            st.markdown("<h3 style='font-size:18px; font-weight:600; color:#C7D2FE;'>📈 Revenue and Profit Trend (MoM)</h3>", unsafe_allow_html=True)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=trend_df['yr_mo'], y=trend_df['monthly_sales'],
                mode='lines', name='Revenue',
                line=dict(color='#6366F1', width=3),
                fill='tozeroy', fillcolor='rgba(99, 102, 241, 0.1)'
            ))
            fig.add_trace(go.Scatter(
                x=trend_df['yr_mo'], y=trend_df['monthly_profit'],
                mode='lines', name='Profit',
                line=dict(color='#10B981', width=3),
                fill='tozeroy', fillcolor='rgba(16, 185, 129, 0.05)'
            ))
            
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#94A3B8'),
                margin=dict(l=20, r=20, t=10, b=20),
                height=350,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data matches the current filters.")

    with col2:
        # Category Contribution
        cat_query = f"""
            SELECT 
                p.category,
                SUM(oi.sales) as category_sales
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            JOIN orders o ON oi.order_id = o.order_id
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN locations l ON o.location_id = l.location_id
            {where_str}
            GROUP BY p.category
            ORDER BY category_sales DESC
        """
        cat_df = run_db_query(cat_query, params)

        if not cat_df.empty:
            st.markdown("<h3 style='font-size:18px; font-weight:600; color:#C7D2FE;'>🍰 Category Contribution</h3>", unsafe_allow_html=True)
            fig_pie = px.pie(
                cat_df, values='category_sales', names='category',
                hole=0.4,
                color_discrete_sequence=['#6366F1', '#34D399', '#FBBF24']
            )
            fig_pie.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#94A3B8'),
                margin=dict(l=10, r=10, t=10, b=10),
                height=350,
                legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02)
            )
            fig_pie.update_traces(textinfo='percent+label', marker=dict(line=dict(color='#020617', width=2)))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No category data matches selected filters.")

    # 3. Row 3: Customers and Products
    st.markdown("---")
    col3, col4 = st.columns([1.1, 1])

    with col3:
        # Top 10 Customers
        cust_query = f"""
            SELECT 
                c.customer_name,
                SUM(oi.sales) as total_spent,
                SUM(oi.profit) as customer_profit
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN locations l ON o.location_id = l.location_id
            {where_str}
            GROUP BY c.customer_name
            ORDER BY total_spent DESC
            LIMIT 10
        """
        cust_df = run_db_query(cust_query, params)

        if not cust_df.empty:
            st.markdown("<h3 style='font-size:18px; font-weight:600; color:#C7D2FE;'>👥 Top 10 Customers</h3>", unsafe_allow_html=True)
            fig_cust = px.bar(
                cust_df, x='total_spent', y='customer_name',
                orientation='h',
                labels={'total_spent': 'Total Revenue ($)', 'customer_name': 'Customer'},
                color='customer_profit',
                color_continuous_scale=px.colors.sequential.Viridis
            )
            fig_cust.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#94A3B8'),
                margin=dict(l=20, r=20, t=10, b=20),
                height=350,
                xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                yaxis=dict(showgrid=False, categoryorder='total ascending'),
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_cust, use_container_width=True)
        else:
            st.info("No customer data matches selected filters.")

    with col4:
        # Top 10 Products
        prod_query = f"""
            SELECT 
                p.product_name,
                SUM(oi.quantity) as total_quantity
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            JOIN orders o ON oi.order_id = o.order_id
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN locations l ON o.location_id = l.location_id
            {where_str}
            GROUP BY p.product_name
            ORDER BY total_quantity DESC
            LIMIT 10
        """
        prod_df = run_db_query(prod_query, params)

        if not prod_df.empty:
            st.markdown("<h3 style='font-size:18px; font-weight:600; color:#C7D2FE;'>📦 Best-Selling Products (by Volume)</h3>", unsafe_allow_html=True)
            fig_prod = px.bar(
                prod_df, x='total_quantity', y='product_name',
                orientation='h',
                labels={'total_quantity': 'Units Sold', 'product_name': 'Product'},
                color_discrete_sequence=['#34D399']
            )
            
            # Truncate product names for better rendering
            prod_df['short_name'] = prod_df['product_name'].apply(lambda x: x[:35] + '...' if len(x) > 35 else x)
            fig_prod.update_traces(y=prod_df['short_name'])
            
            fig_prod.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#94A3B8'),
                margin=dict(l=20, r=20, t=10, b=20),
                height=350,
                xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                yaxis=dict(showgrid=False, categoryorder='total ascending')
            )
            st.plotly_chart(fig_prod, use_container_width=True)
        else:
            st.info("No product data matches selected filters.")

elif page == "🤖 AI Query Assistant":
    st.markdown("<h1 class='header-title'>AI Query Assistant</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94A3B8; font-size:16px; margin-bottom: 25px;'>Ask business questions in plain English and let Gemini convert them to SQL queries to retrieve answers instantly.</p>", unsafe_allow_html=True)

    # API configuration warning
    if not ai_agent.initialized:
        st.info("ℹ️ **Simulation Mode Active**: The system is running in offline simulation mode because a valid `GEMINI_API_KEY` was not configured in `.env`. Standard query queries will be matched dynamically to demonstrate behavior.")

    # Suggestion Buttons
    st.markdown("<h5 style='color: #94A3B8; margin-bottom: 10px;'>💡 Query Suggestions</h5>", unsafe_allow_html=True)
    
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    query_input = ""
    
    # Capture button clicks using session state
    if col_s1.button("Who are the top 5 customers by sales?", use_container_width=True):
        st.session_state.selected_query = "Who are the top 5 customers by sales?"
    if col_s2.button("What were the sales in March 2014?", use_container_width=True):
        st.session_state.selected_query = "What were the sales in March 2014?"
    if col_s3.button("What is the best selling product by quantity?", use_container_width=True):
        st.session_state.selected_query = "What is the best selling product by quantity?"
    if col_s4.button("Show me total profit by market region", use_container_width=True):
        st.session_state.selected_query = "Show me total profit by market region"

    # Default key in session state
    if 'selected_query' not in st.session_state:
        st.session_state.selected_query = ""

    # Search Bar
    user_query = st.text_input(
        "Enter your sales analysis question:",
        value=st.session_state.selected_query,
        placeholder="e.g., Show me monthly revenue growth in 2014"
    )

    if user_query:
        st.markdown("---")
        with st.spinner("🤖 AI is translating and querying the database..."):
            # 1. Translate question to SQL
            sql_query = ai_agent.translate_to_sql(user_query)
            
            # Display generated SQL code block
            st.markdown("### 🔍 Generated SQL Query")
            st.code(sql_query, language="sql")
            
            # 2. Execute SQL query on database
            df, error = ai_agent.execute_query(sql_query)
            
            if error:
                st.error(f"❌ SQL Execution Error: {error}")
                st.info("The AI might have written a SQL function unsupported by the SQLite driver. Try rephrasing your request.")
            elif df is not None:
                if df.empty:
                    st.info("ℹ️ No records found matching that query.")
                else:
                    st.markdown("### 📊 Query Results")
                    st.dataframe(df, use_container_width=True)
                    
                    # 3. Generate summary explanation
                    with st.spinner("✍️ Writing analysis insights..."):
                        insights = ai_agent.generate_explanation(user_query, sql_query, df)
                        
                    st.markdown("### 💡 Business Insights & Interpretation")
                    st.markdown(f"<div style='background: rgba(30, 41, 59, 0.3); border: 1px solid rgba(255,255,255,0.05); padding: 20px; border-radius: 12px; line-height:1.6;'>{insights}</div>", unsafe_allow_html=True)
