import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, timedelta
import hashlib
import os

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://zqbimrpywehyfodghgan.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '***REMOVED***')

CATEGORIES = ["אוכל ושתייה", "קניות וסופר", "תחבורה ודלק", "פנאי ובילוי", "חשבונות ובית", "בריאות", "אחר"]
CAT_COLORS = {
    "אוכל ושתייה": "#4A9EFF",
    "קניות וסופר": "#7B68EE",
    "תחבורה ודלק": "#50C878",
    "פנאי ובילוי": "#FFB347",
    "חשבונות ובית": "#87CEEB",
    "בריאות": "#FF6B6B",
    "אחר": "#607D8B",
}

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#A0B4C8",
    xaxis=dict(gridcolor="#1E3A5F", linecolor="#1E3A5F"),
    yaxis=dict(gridcolor="#1E3A5F", linecolor="#1E3A5F"),
    margin=dict(l=0, r=0, t=10, b=0),
)

st.set_page_config(page_title="דשבורד הוצאות", page_icon="💰", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Heebo', sans-serif;
    direction: rtl;
}

/* ── רקע ראשי ── */
.stApp { background-color: #0F1B2D; }
.block-container { padding-top: 1.2rem; background-color: #0F1B2D; }

/* ── כרטיסי מטריקה ── */
.metric-card {
    background: #1A2F4A;
    border-radius: 14px;
    padding: 1.2rem 1rem;
    text-align: center;
    border-top: 4px solid #4A9EFF;
    margin-bottom: 0.5rem;
}
.metric-card.red    { border-top-color: #FF6B6B; }
.metric-card.green  { border-top-color: #50C878; }
.metric-card.purple { border-top-color: #7B68EE; }
.metric-value { font-size: 1.9rem; font-weight: 700; color: #FFFFFF; }
.metric-label { font-size: 0.82rem; color: #A0B4C8; margin-top: 4px; }

/* ── טאבים ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: #0F1B2D;
}
.stTabs [data-baseweb="tab"] {
    background: #1A2F4A;
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 500;
    color: #A0B4C8;
    border: none;
}
.stTabs [aria-selected="true"] {
    background: #4A9EFF !important;
    color: #FFFFFF !important;
}

/* ── כפתורים ── */
.stButton > button {
    background-color: #4A9EFF;
    color: #FFFFFF;
    border-radius: 8px;
    border: none;
    font-weight: 600;
    font-family: 'Heebo', sans-serif;
}
.stButton > button:hover { background-color: #2d7ed4; color: white; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #0A1628 !important;
    border-left: 1px solid #1A2F4A;
}
section[data-testid="stSidebar"] * { color: #A0B4C8 !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #FFFFFF !important; }

/* ── Inputs ── */
.stTextInput input, .stSelectbox select, .stNumberInput input {
    background-color: #1A2F4A !important;
    color: #FFFFFF !important;
    border: 1px solid #2A4A6A !important;
    border-radius: 8px !important;
}
.stSelectbox > div > div {
    background-color: #1A2F4A !important;
    color: #FFFFFF !important;
    border: 1px solid #2A4A6A !important;
}
label, .stRadio label, .stCheckbox label { color: #A0B4C8 !important; }

/* ── טבלאות ── */
[data-testid="stDataFrame"] {
    background: #1A2F4A;
    border-radius: 10px;
}
[data-testid="stDataFrame"] th {
    background: #0F1B2D !important;
    color: #4A9EFF !important;
}
[data-testid="stDataFrame"] td { color: #FFFFFF !important; }

/* ── כותרות ── */
h1, h2, h3, h4 { color: #FFFFFF !important; }
p, span, div { color: #A0B4C8; }

/* ── מפרידים ── */
hr { border-color: #1A2F4A; }

/* ── Expander ── */
details { background: #1A2F4A; border-radius: 10px; border: none !important; }
summary { color: #FFFFFF !important; }

/* ── Progress ── */
.stProgress > div > div { background-color: #4A9EFF; }
.stProgress > div { background-color: #1A2F4A; }

/* ── Info/Success/Warning boxes ── */
.stAlert { background-color: #1A2F4A; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)


# ── DB ───────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_db():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


@st.cache_data(ttl=30)
def fetch_expenses(user_id=None, month=None, all_users=False):
    db = get_db()
    query = db.table("expenses").select("*")
    if not all_users and user_id:
        query = query.eq("user_id", user_id)
    if month:
        query = query.like("date", f"{month}%")
    result = query.order("date", desc=True).execute()
    if not result.data:
        return pd.DataFrame()
    df = pd.DataFrame(result.data)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    return df


@st.cache_data(ttl=30)
def fetch_users():
    db = get_db()
    result = db.table("authorized_users").select("*").execute()
    return result.data or []


@st.cache_data(ttl=60)
def fetch_budget(user_id, month):
    db = get_db()
    result = db.table("budgets").select("*").eq("user_id", user_id).eq("month", month).execute()
    return {row["category"]: row["amount"] for row in (result.data or [])}


def save_budget_to_db(user_id, month, budgets_dict):
    db = get_db()
    for cat, amount in budgets_dict.items():
        if amount > 0:
            db.table("budgets").upsert({
                "user_id": user_id, "month": month,
                "category": cat, "amount": float(amount)
            }).execute()
        else:
            db.table("budgets").delete().eq("user_id", user_id).eq("month", month).eq("category", cat).execute()
    fetch_budget.clear()


def update_expense(expense_id, category, item, amount, date_str):
    db = get_db()
    db.table("expenses").update({
        "category": category,
        "item": item,
        "amount": float(amount),
        "date": date_str,
    }).eq("id", expense_id).execute()
    fetch_expenses.clear()


# ── AUTH ──────────────────────────────────────────────────────────────────────

def login_page():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='color:#FFFFFF;text-align:center'>💰 דשבורד הוצאות</h2>",
                    unsafe_allow_html=True)
        st.markdown("---")
        username = st.text_input("שם משתמש", placeholder="הכנס שם משתמש")
        password = st.text_input("סיסמה", type="password", placeholder="הכנס סיסמה")
        if st.button("כניסה", use_container_width=True):
            db = get_db()
            res = db.table("authorized_users").select("*").eq("dashboard_username", username).execute()
            if res.data:
                user = res.data[0]
                if user.get("dashboard_password", "") == hash_pw(password):
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("סיסמה שגויה")
            else:
                st.error("משתמש לא נמצא")


# ── HELPERS ───────────────────────────────────────────────────────────────────

def card(label, value, cls=""):
    st.markdown(f"""
    <div class="metric-card {cls}">
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
    </div>""", unsafe_allow_html=True)


def prev_month_str(month_str: str) -> str:
    d = datetime.strptime(month_str, "%Y-%m")
    return (d.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def apply_dark_layout(fig, height=340):
    fig.update_layout(height=height, **PLOT_LAYOUT)
    return fig


# ── TABS ──────────────────────────────────────────────────────────────────────

def tab_overview(df, df_prev, budgets):
    if df.empty:
        st.info("אין הוצאות רשומות לחודש זה.")
        return

    total = df["amount"].sum()
    active_days = df["date"].dt.date.nunique()
    daily_avg = total / max(active_days, 1)
    top_cat = df.groupby("category")["amount"].sum().idxmax()
    total_budget = sum(budgets.values()) if budgets else 0
    budget_pct = (total / total_budget * 100) if total_budget > 0 else None

    c1, c2, c3, c4 = st.columns(4)
    with c1: card("סה\"כ החודש", f"₪{total:,.0f}")
    with c2: card("ממוצע יומי", f"₪{daily_avg:,.0f}", "purple")
    with c3: card("קטגוריה מובילה", top_cat, "red")
    with c4:
        if budget_pct is not None:
            card("% מהתקציב", f"{budget_pct:.0f}%", "red" if budget_pct > 90 else "green")
        else:
            card("תקציב", "לא הוגדר")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### הוצאות לפי קטגוריה")
        with st.container():
            cat_df = df.groupby("category")["amount"].sum().reset_index()
            colors = [CAT_COLORS.get(c, "#607D8B") for c in cat_df["category"]]
            fig = px.pie(cat_df, values="amount", names="category",
                         color_discrete_sequence=colors, hole=0.42)
            fig.update_traces(textinfo="percent+label", textposition="inside", textfont_size=12,
                              textfont_color="#FFFFFF")
            fig.update_layout(showlegend=False, height=340, **PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True, key="pie_overview")

    with col2:
        st.markdown("### השוואה לחודש קודם")
        with st.container():
            if not df_prev.empty:
                curr = df.groupby("category")["amount"].sum()
                prev = df_prev.groupby("category")["amount"].sum()
                cmp = pd.DataFrame({"החודש": curr, "חודש קודם": prev}).fillna(0).reset_index()
                fig2 = go.Figure([
                    go.Bar(name="החודש", x=cmp["category"], y=cmp["החודש"], marker_color="#4A9EFF"),
                    go.Bar(name="חודש קודם", x=cmp["category"], y=cmp["חודש קודם"], marker_color="#1A2F4A",
                           marker_line_color="#4A9EFF", marker_line_width=1),
                ])
                fig2.update_layout(barmode="group", xaxis_tickangle=-25,
                                   legend=dict(orientation="h", font_color="#A0B4C8"),
                                   height=340, **PLOT_LAYOUT)
                st.plotly_chart(fig2, use_container_width=True, key="bar_compare")
            else:
                st.info("אין נתוני חודש קודם להשוואה")


def tab_trends(df_all):
    if df_all.empty:
        st.info("אין נתונים")
        return

    st.markdown("### הוצאות לאורך זמן")
    gran = st.radio("תצוגה:", ["יומי", "שבועי", "חודשי"], horizontal=True, key="gran_radio")

    df2 = df_all.copy()
    if gran == "יומי":
        df2["period"] = df2["date"].dt.strftime("%d/%m/%Y")
    elif gran == "שבועי":
        df2["period"] = df2["date"].dt.to_period("W").apply(
            lambda x: x.start_time.strftime("%d/%m/%Y"))
    else:
        df2["period"] = df2["date"].dt.strftime("%m/%Y")

    pts = df2.groupby("period")["amount"].sum().reset_index()

    with st.container():
        fig = px.line(pts, x="period", y="amount", markers=True,
                      color_discrete_sequence=["#4A9EFF"],
                      labels={"period": "תאריך", "amount": "סכום (₪)"})
        fig.update_traces(line_width=2.5, marker_size=7,
                          hovertemplate="<b>%{x}</b><br>₪%{y:,.0f}<extra></extra>")
        fig.update_layout(
            xaxis_title="תאריך", yaxis_title="סכום (₪)",
            xaxis_tickangle=-30,
            yaxis_tickformat=",.0f",
            height=320, **PLOT_LAYOUT
        )
        st.plotly_chart(fig, use_container_width=True, key="line_trends")

    st.markdown("### השוואה חודשית")
    df3 = df_all.copy()
    df3["month_key"] = df3["date"].dt.strftime("%Y-%m")
    monthly = df3.groupby("month_key")["amount"].sum().reset_index().tail(6)
    monthly["label"] = monthly["month_key"].apply(
        lambda x: datetime.strptime(x, "%Y-%m").strftime("%m/%Y"))

    with st.container():
        fig2 = px.bar(monthly, x="label", y="amount", text="amount",
                      color_discrete_sequence=["#4A9EFF"],
                      labels={"label": "חודש", "amount": "סכום (₪)"})
        fig2.update_traces(texttemplate="₪%{text:,.0f}", textposition="outside",
                           textfont_color="#FFFFFF")
        fig2.update_layout(xaxis_title="חודש", yaxis_title="סכום (₪)",
                           yaxis_tickformat=",.0f", height=300, **PLOT_LAYOUT)
        st.plotly_chart(fig2, use_container_width=True, key="bar_monthly")


def tab_table(df_all):
    st.markdown("### כל ההוצאות")
    if df_all.empty:
        st.info("אין נתונים")
        return

    col1, col2 = st.columns(2)
    months = ["הכל"] + sorted(df_all["date"].dt.strftime("%Y-%m").unique(), reverse=True)
    with col1:
        sel_month = st.selectbox("חודש", months,
                                  format_func=lambda x: x if x == "הכל" else
                                  datetime.strptime(x, "%Y-%m").strftime("%m/%Y"),
                                  key="table_month")
    with col2:
        sel_cat = st.selectbox("קטגוריה", ["הכל"] + CATEGORIES, key="table_cat")

    df_f = df_all.copy().sort_values("date", ascending=False)
    if sel_month != "הכל":
        df_f = df_f[df_f["date"].dt.strftime("%Y-%m") == sel_month]
    if sel_cat != "הכל":
        df_f = df_f[df_f["category"] == sel_cat]

    if df_f.empty:
        st.info("אין תוצאות")
        return

    # Build editable dataframe (keep id for saving)
    edit_df = df_f[["id", "category", "item", "amount", "date"]].copy()
    edit_df["date"] = edit_df["date"].dt.date
    edit_df = edit_df.rename(columns={
        "category": "קטגוריה", "item": "פריט",
        "amount": "סכום (₪)", "date": "תאריך"
    })

    edited = st.data_editor(
        edit_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": None,
            "קטגוריה": st.column_config.SelectboxColumn(options=CATEGORIES, required=True),
            "פריט": st.column_config.TextColumn(required=True),
            "סכום (₪)": st.column_config.NumberColumn(min_value=0, format="₪%.0f", required=True),
            "תאריך": st.column_config.DateColumn(format="DD/MM/YYYY", required=True),
        },
        key="expense_editor"
    )

    col_save, col_info = st.columns([1, 3])
    with col_save:
        if st.button("💾 שמור שינויים", key="save_expenses"):
            changed = 0
            for i, row in edited.iterrows():
                orig = edit_df.loc[i]
                if (row["קטגוריה"] != orig["קטגוריה"] or
                    row["פריט"] != orig["פריט"] or
                    row["סכום (₪)"] != orig["סכום (₪)"] or
                    str(row["תאריך"]) != str(orig["תאריך"])):
                    update_expense(
                        int(row["id"]),
                        row["קטגוריה"],
                        row["פריט"],
                        row["סכום (₪)"],
                        str(row["תאריך"]) + " 00:00:00"
                    )
                    changed += 1
            if changed:
                st.success(f"עודכנו {changed} הוצאות!")
                st.rerun()
            else:
                st.info("לא זוהו שינויים")
    with col_info:
        st.markdown(f"<span style='color:#A0B4C8'>סה\"כ: <b style='color:#4A9EFF'>₪{df_f['amount'].sum():,.0f}</b> | {len(df_f)} הוצאות</span>",
                    unsafe_allow_html=True)


def tab_budget(df, selected_month, user_id):
    st.markdown("### תקציב חודשי")

    # Load from DB if not in session
    bkey = f"budget_{selected_month}"
    if bkey not in st.session_state:
        st.session_state[bkey] = fetch_budget(user_id, selected_month)

    budgets = st.session_state[bkey]

    st.markdown("#### הגדרת תקציב")
    cols = st.columns(3)
    new_budgets = {}
    for i, cat in enumerate(CATEGORIES):
        with cols[i % 3]:
            val = st.number_input(cat, min_value=0, step=50,
                                   value=int(budgets.get(cat, 0)),
                                   key=f"b_{cat}_{selected_month}")
            new_budgets[cat] = val

    if st.button("שמור תקציב", key=f"save_budget_{selected_month}"):
        save_budget_to_db(user_id, selected_month, new_budgets)
        st.session_state[bkey] = new_budgets
        budgets = new_budgets
        st.success("התקציב נשמר!")

    st.markdown("---")
    st.markdown("#### התקדמות vs תקציב")

    active = {c: v for c, v in budgets.items() if v > 0}
    if not active:
        st.info("הגדר תקציב בשדות למעלה ולחץ 'שמור'")
        return

    cat_totals = df.groupby("category")["amount"].sum() if not df.empty else pd.Series(dtype=float)

    for cat, budget in active.items():
        spent = float(cat_totals.get(cat, 0))
        pct = min(spent / budget, 1.0)
        color = "#FF6B6B" if pct > 0.9 else "#FFB347" if pct > 0.7 else "#50C878"
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"<span style='color:#FFFFFF;font-weight:600'>{cat}</span>",
                        unsafe_allow_html=True)
            st.progress(pct)
        with col2:
            st.markdown(f"<span style='color:{color};font-weight:600'>₪{spent:,.0f}</span>"
                        f"<span style='color:#A0B4C8'> / ₪{budget:,.0f}</span>",
                        unsafe_allow_html=True)


def tab_shared(selected_month):
    st.markdown("### הוצאות משותפות")

    users = fetch_users()
    if not users:
        st.info("אין משתמשים")
        return

    user_map = {
        u["user_id"]: u.get("username") or u.get("dashboard_username", str(u["user_id"]))
        for u in users
    }

    df = fetch_expenses(all_users=True, month=selected_month)
    if df.empty:
        st.info("אין נתונים לחודש זה")
        return

    df["user_name"] = df["user_id"].map(user_map).fillna(df["user_id"].astype(str))
    totals = df.groupby("user_name")["amount"].sum().reset_index()
    grand = totals["amount"].sum()
    totals["אחוז"] = (totals["amount"] / grand * 100).round(1)

    col1, col2 = st.columns(2)
    with col1:
        with st.container():
            fig = px.pie(totals, values="amount", names="user_name",
                         color_discrete_sequence=["#4A9EFF", "#7B68EE", "#50C878", "#FFB347", "#FF6B6B"])
            fig.update_layout(height=300, **PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True, key="pie_shared")

    with col2:
        st.markdown("#### סיכום")
        for _, row in totals.iterrows():
            st.markdown(
                f"<span style='color:#FFFFFF;font-weight:600'>{row['user_name']}:</span> "
                f"<span style='color:#4A9EFF'>₪{row['amount']:,.0f}</span> "
                f"<span style='color:#A0B4C8'>({row['אחוז']}%)</span>",
                unsafe_allow_html=True)
        st.markdown(f"<span style='color:#A0B4C8'>סה\"כ משותף: <b style='color:#4A9EFF'>₪{grand:,.0f}</b></span>",
                    unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### פירוט לפי משתמש")
    for uname, udf in df.groupby("user_name"):
        with st.expander(f"📋 {uname} — ₪{udf['amount'].sum():,.0f}"):
            d = udf[["category", "item", "amount", "date"]].copy().sort_values("date", ascending=False)
            d["date"] = d["date"].dt.strftime("%d/%m/%Y")
            d["amount"] = d["amount"].apply(lambda x: f"₪{x:,.0f}")
            d.columns = ["קטגוריה", "פריט", "סכום (₪)", "תאריך"]
            st.dataframe(d, use_container_width=True, hide_index=True)


def tab_settings():
    st.markdown("### ניהול משתמשים")

    if not st.session_state.user.get("is_admin"):
        st.warning("גישה מוגבלת — אדמין בלבד")
        return

    db = get_db()
    users = fetch_users()
    if users:
        df_u = pd.DataFrame(users)
        cols_show = [c for c in ["user_id", "username", "dashboard_username", "is_admin"] if c in df_u.columns]
        st.dataframe(df_u[cols_show].fillna(""), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### הוסף / עדכן משתמש")

    uid = st.number_input("Telegram user_id", min_value=0, step=1)
    uname = st.text_input("שם תצוגה (עברית)")
    dash_user = st.text_input("שם משתמש לדשבורד")
    dash_pass = st.text_input("סיסמה לדשבורד", type="password")
    is_admin = st.checkbox("הרשאות אדמין")

    if st.button("שמור משתמש"):
        if uid and dash_user and dash_pass:
            db.table("authorized_users").upsert({
                "user_id": int(uid),
                "username": uname,
                "dashboard_username": dash_user,
                "dashboard_password": hash_pw(dash_pass),
                "is_admin": is_admin,
            }).execute()
            fetch_users.clear()
            st.success(f"המשתמש '{dash_user}' נשמר!")
        else:
            st.error("מלא user_id, שם משתמש וסיסמה")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    if not st.session_state.get("logged_in"):
        login_page()
        return

    user = st.session_state.user
    uid = user["user_id"]
    display_name = user.get("username") or user.get("dashboard_username", "")

    with st.sidebar:
        st.markdown(f"<h3 style='color:#FFFFFF'>שלום, {display_name} 👋</h3>",
                    unsafe_allow_html=True)
        st.markdown("---")

        now = datetime.now()
        month_options = []
        for i in range(12):
            d = now.replace(day=1) - timedelta(days=i * 30)
            month_options.append(d.strftime("%Y-%m"))

        selected_month = st.selectbox(
            "חודש", month_options,
            format_func=lambda x: datetime.strptime(x, "%Y-%m").strftime("%m/%Y")
        )
        all_users = st.checkbox("כל המשתמשים", value=False)
        st.markdown("---")
        if st.button("התנתק", use_container_width=True):
            for k in ["logged_in", "user"]:
                st.session_state.pop(k, None)
            st.rerun()

    prev = prev_month_str(selected_month)
    df = fetch_expenses(user_id=uid, month=selected_month, all_users=all_users)
    df_prev = fetch_expenses(user_id=uid, month=prev, all_users=all_users)
    df_all = fetch_expenses(user_id=uid, all_users=all_users)

    bkey = f"budget_{selected_month}"
    if bkey not in st.session_state:
        st.session_state[bkey] = fetch_budget(uid, selected_month)
    budgets = st.session_state[bkey]

    month_label = datetime.strptime(selected_month, "%Y-%m").strftime("%m/%Y")
    st.markdown(f"<h1 style='color:#FFFFFF'>💰 דשבורד הוצאות — {month_label}</h1>",
                unsafe_allow_html=True)

    t1, t2, t3, t4, t5, t6 = st.tabs(
        ["📊 סקירה", "📈 מגמות", "📋 הוצאות", "🎯 תקציב", "👥 משותף", "⚙️ הגדרות"])

    with t1: tab_overview(df, df_prev, budgets)
    with t2: tab_trends(df_all)
    with t3: tab_table(df_all)
    with t4: tab_budget(df, selected_month, uid)
    with t5: tab_shared(selected_month)
    with t6: tab_settings()


if __name__ == "__main__":
    main()
