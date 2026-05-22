import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, timedelta
import hashlib
import os
import io
import tempfile

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

CATEGORIES = ["אוכל ושתייה", "קניות וסופר", "תחבורה ודלק", "פנאי ובילוי", "חשבונות ובית", "בריאות", "אחר"]
CAT_COLORS = {
    "אוכל ושתייה": "#B45309",
    "קניות וסופר": "#15803D",
    "תחבורה ודלק": "#D97706",
    "פנאי ובילוי": "#DC2626",
    "חשבונות ובית": "#6B7280",
    "בריאות": "#0369A1",
    "אחר": "#78716C",
}

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#78716C",
    xaxis=dict(gridcolor="#D6D0C6", linecolor="#D6D0C6"),
    yaxis=dict(gridcolor="#D6D0C6", linecolor="#D6D0C6"),
    margin=dict(l=0, r=0, t=10, b=0),
)

st.set_page_config(page_title="ניהול הוצאות", page_icon="💰", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Heebo', sans-serif;
    direction: rtl;
}

/* ── רקע ראשי ── */
.stApp { background-color: #F5F0E8; }
.block-container { padding-top: 4rem; background-color: #F5F0E8; }

/* ── הסתרת toolbar של Streamlit ── */
header[data-testid="stHeader"] { background-color: rgba(0,0,0,0) !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/* ── כרטיסי מטריקה ── */
.metric-card {
    background: #FFFFFF;
    border-radius: 14px;
    padding: 1.2rem 1rem;
    text-align: center;
    border: 1px solid #D6D0C6;
    border-top: 4px solid #B45309;
    box-shadow: 0 1px 4px rgba(28,25,23,0.08);
    margin-bottom: 0.5rem;
}
.metric-card.red    { border-top-color: #DC2626; }
.metric-card.green  { border-top-color: #15803D; }
.metric-card.purple { border-top-color: #6B7280; }
.metric-value { font-size: 1.9rem; font-weight: 700; color: #1C1917; }
.metric-label { font-size: 0.82rem; color: #78716C; margin-top: 4px; }

/* ── טאבים ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #EDE8DC;
    border-radius: 10px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 500;
    color: #78716C;
    border: none;
}
.stTabs [aria-selected="true"] {
    background: #FFFFFF !important;
    color: #B45309 !important;
    border: 1px solid #D6D0C6 !important;
    box-shadow: 0 1px 4px rgba(28,25,23,0.08) !important;
}

/* ── כפתורים ── */
.stButton > button {
    background-color: #B45309 !important;
    color: #FFFFFF !important;
    border-radius: 8px;
    border: none !important;
    font-weight: 600;
    font-family: 'Heebo', sans-serif;
}
.stButton > button * { color: #FFFFFF !important; }
.stButton > button:hover { background-color: #92400E !important; color: #FFFFFF !important; }
.stButton > button:hover * { color: #FFFFFF !important; }
/* כפתורי form submit */
.stFormSubmitButton > button {
    background-color: #B45309 !important;
    color: #FFFFFF !important;
    border: none !important;
}
.stFormSubmitButton > button * { color: #FFFFFF !important; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #EDE8DC !important;
    border-left: 1px solid #D6D0C6;
    right: 0 !important;
    left: auto !important;
}
section[data-testid="stSidebar"] * { color: #78716C !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #1C1917 !important; }

/* ── מניעת overlap של sidebar ── */
.main { margin-right: 0 !important; }

/* ── Inputs ── */
.stTextInput input, .stSelectbox select, .stNumberInput input {
    background-color: #FFFFFF !important;
    color: #1C1917 !important;
    border: 1px solid #D6D0C6 !important;
    border-radius: 8px !important;
}
.stSelectbox > div > div {
    background-color: #FFFFFF !important;
    color: #1C1917 !important;
    border: 1px solid #D6D0C6 !important;
}
label, .stRadio label, .stCheckbox label { color: #78716C !important; }

/* ── טבלאות ── */
[data-testid="stDataFrame"] {
    background: #FFFFFF;
    border-radius: 10px;
    border: 1px solid #D6D0C6;
}
[data-testid="stDataFrame"] th {
    background: #EDE8DC !important;
    color: #B45309 !important;
}
[data-testid="stDataFrame"] td { color: #1C1917 !important; }

/* ── כותרות ── */
h1, h2, h3, h4 { color: #1C1917 !important; }
p, span, div { color: #78716C; }

/* ── מפרידים ── */
hr { border-color: #D6D0C6; }

/* ── Expander ── */
details { background: #FFFFFF; border-radius: 10px; border: 1px solid #D6D0C6 !important; }
summary { color: #1C1917 !important; }

/* ── Progress ── */
.stProgress > div > div { background-color: #B45309; }
.stProgress > div { background-color: #D6D0C6; }

/* ── Info/Success/Warning boxes ── */
.stAlert { background-color: #FFFFFF; border-radius: 10px; border: 1px solid #D6D0C6; }

/* ── מובייל ── */
@media (max-width: 768px) {
    .block-container { padding: 3.5rem 0.4rem 0.5rem !important; }
    .metric-value { font-size: 1.3rem !important; }
    .metric-card { padding: 0.8rem 0.5rem !important; }
    .stTabs [data-baseweb="tab"] { padding: 4px 8px !important; font-size: 0.75rem !important; }
    h1, h2, h3 { font-size: 1.1rem !important; }
}
</style>
""", unsafe_allow_html=True)


# ── DB ───────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_db():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


@st.cache_data(ttl=30)
def fetch_expenses(user_id=None, month=None, all_users=False, user_ids=None):
    db = get_db()
    query = db.table("expenses").select("*")
    if user_ids:
        query = query.in_("user_id", list(user_ids))
    elif not all_users and user_id:
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
def fetch_budget(user_id, month, group_id=0):
    db = get_db()
    result = db.table("budgets").select("*").eq("user_id", user_id).eq("month", month).eq("group_id", group_id).execute()
    return {row["category"]: row["amount"] for row in (result.data or [])}


def fetch_groups(user_id):
    db = get_db()
    member_rows = db.table("group_members").select("group_id").eq("user_id", user_id).execute()
    group_ids = [r["group_id"] for r in (member_rows.data or [])]
    if not group_ids:
        return []
    return db.table("groups").select("*").in_("id", group_ids).execute().data or []


def fetch_group_members(group_id):
    db = get_db()
    rows = db.table("group_members").select("user_id").eq("group_id", group_id).execute()
    return [r["user_id"] for r in (rows.data or [])]


def create_group(name, created_by):
    db = get_db()
    result = db.table("groups").insert({"name": name, "created_by": created_by}).execute()
    group_id = result.data[0]["id"]
    db.table("group_members").insert({"group_id": group_id, "user_id": created_by}).execute()
    return group_id


def add_group_member(group_id, user_id):
    db = get_db()
    db.table("group_members").upsert({"group_id": group_id, "user_id": user_id}).execute()


def remove_group_member(group_id, user_id):
    db = get_db()
    db.table("group_members").delete().eq("group_id", group_id).eq("user_id", user_id).execute()


def delete_group(group_id):
    db = get_db()
    db.table("groups").delete().eq("id", group_id).execute()


def save_default_group(user_id, group_id_or_none):
    db = get_db()
    db.table("authorized_users").update({"default_group_id": group_id_or_none}).eq("user_id", user_id).execute()
    fetch_users.clear()


def save_budget_to_db(user_id, month, budgets_dict, group_id=0):
    db = get_db()
    for cat, amount in budgets_dict.items():
        if amount > 0:
            db.table("budgets").upsert({
                "user_id": user_id, "month": month, "group_id": group_id,
                "category": cat, "amount": float(amount)
            }, on_conflict="user_id,group_id,month,category").execute()
        else:
            db.table("budgets").delete().eq("user_id", user_id).eq("month", month).eq("group_id", group_id).eq("category", cat).execute()
    fetch_budget.clear()


@st.cache_data(ttl=30)
def fetch_shared_expenses(group_id, month=None):
    db = get_db()
    query = db.table("expenses").select("*").eq("group_id", group_id)
    if month:
        query = query.like("date", f"{month}%")
    result = query.order("date", desc=True).execute()
    if not result.data:
        return pd.DataFrame()
    df = pd.DataFrame(result.data)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    return df


def calculate_settlement(df_shared, member_ids, user_map):
    """מחשב מי חייב למי — מחזיר רשימת (חייב, זכאי, סכום)."""
    if df_shared.empty or len(member_ids) < 2:
        return []
    total      = df_shared["amount"].sum()
    per_person = total / len(member_ids)
    paid       = df_shared.groupby("user_id")["amount"].sum()
    balances   = {mid: float(paid.get(mid, 0)) - per_person for mid in member_ids}
    creditors  = sorted([(uid, bal)  for uid, bal in balances.items() if bal  >  0.5], key=lambda x: -x[1])
    debtors    = sorted([(uid, -bal) for uid, bal in balances.items() if bal  < -0.5], key=lambda x: -x[1])
    c_amt = {uid: amt for uid, amt in creditors}
    d_amt = {uid: amt for uid, amt in debtors}
    c_list, d_list = [uid for uid, _ in creditors], [uid for uid, _ in debtors]
    result = []
    ci, di = 0, 0
    while ci < len(c_list) and di < len(d_list):
        c, d   = c_list[ci], d_list[di]
        transfer = min(c_amt[c], d_amt[d])
        if transfer > 0.5:
            result.append((user_map.get(d, str(d)), user_map.get(c, str(c)), transfer))
        c_amt[c] -= transfer
        d_amt[d] -= transfer
        if c_amt[c] < 0.5: ci += 1
        if d_amt[d] < 0.5: di += 1
    return result


def fetch_recurring(user_id):
    db = get_db()
    return db.table("recurring_expenses").select("*").eq("user_id", user_id).order("day_of_month").execute().data or []


def save_recurring(user_id, item, category, amount, day):
    db = get_db()
    db.table("recurring_expenses").insert({
        "user_id": user_id, "item": item, "category": category,
        "amount": float(amount), "day_of_month": int(day), "active": True
    }).execute()


def delete_recurring(rec_id):
    db = get_db()
    db.table("recurring_expenses").delete().eq("id", rec_id).execute()


def toggle_recurring(rec_id, active):
    db = get_db()
    db.table("recurring_expenses").update({"active": active}).eq("id", rec_id).execute()


def update_expense(expense_id, category, item, amount, date_str):
    db = get_db()
    db.table("expenses").update({
        "category": category,
        "item": item,
        "amount": float(amount),
        "date": date_str,
    }).eq("id", expense_id).execute()
    fetch_expenses.clear()


def add_expense(user_id, amount, category, item, date):
    db = get_db()
    db.table("expenses").insert({
        "user_id": user_id,
        "amount": float(amount),
        "category": category,
        "item": item,
        "date": str(date) + " 00:00:00"
    }).execute()
    fetch_expenses.clear()


@st.cache_resource
def get_hebrew_font_path():
    font_path = os.path.join(tempfile.gettempdir(), "NotoSansHebrew.ttf")
    if not os.path.exists(font_path):
        try:
            import requests
            r = requests.get(
                "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansHebrew/NotoSansHebrew-Regular.ttf",
                timeout=15
            )
            with open(font_path, "wb") as f:
                f.write(r.content)
        except Exception:
            return None
    return font_path


def generate_pdf(df, selected_month, display_name):
    from fpdf import FPDF
    from bidi.algorithm import get_display

    def heb(text):
        return get_display(str(text))

    # Strip characters that Helvetica can't render (non-latin1, e.g. ₪ U+20AA)
    def lat(text):
        return str(text).encode("latin-1", errors="ignore").decode("latin-1")

    font_path = get_hebrew_font_path()
    has_heb = font_path is not None
    month_label = datetime.strptime(selected_month, "%Y-%m").strftime("%m/%Y")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    if has_heb:
        pdf.add_font("Heb", "", font_path)

    def set_heb(size):
        pdf.set_font("Heb" if has_heb else "Helvetica", size=size)

    def set_num(size):
        pdf.set_font("Helvetica", size=size)

    def bg_page():
        pdf.set_fill_color(15, 25, 35)
        pdf.rect(0, 0, 210, 297, "F")

    bg_page()

    # ── Title bar ──
    pdf.set_fill_color(22, 38, 52)
    pdf.rect(0, 0, 210, 30, "F")

    set_num(16)
    pdf.set_text_color(0, 201, 167)
    pdf.set_xy(10, 5)
    pdf.cell(0, 10, f"Expense Report  {month_label}", align="R")

    set_heb(9)
    pdf.set_text_color(90, 143, 168)
    pdf.set_xy(10, 18)
    pdf.cell(0, 7, heb(display_name), align="R")

    pdf.set_y(38)
    x0 = 10

    # ── Summary cards ──
    if not df.empty:
        total     = df["amount"].sum()
        daily_avg = total / max(df["date"].dt.date.nunique(), 1)
        top_cat   = df.groupby("category")["amount"].sum().idxmax()

        card_data = [
            (heb('סה"כ'),           lat(f"{total:,.0f}"),       False),
            (heb("ממוצע יומי"),     lat(f"{daily_avg:,.0f}"),   False),
            (heb("קטגוריה מובילה"), heb(str(top_cat)),           True),
        ]
        card_w, card_h = 58, 22
        card_xs = [10, 76, 142]
        card_y = pdf.get_y()

        for cx, (lbl, val, is_heb_val) in zip(card_xs, card_data):
            # Card background
            pdf.set_fill_color(26, 48, 64)
            pdf.rect(cx, card_y, card_w, card_h, "F")
            # Accent top border
            pdf.set_fill_color(0, 201, 167)
            pdf.rect(cx, card_y, card_w, 2, "F")
            # Label
            set_heb(7)
            pdf.set_text_color(90, 143, 168)
            pdf.set_xy(cx, card_y + 4)
            pdf.cell(card_w, 5, lbl, align="C")
            # Value — use correct font
            if is_heb_val:
                set_heb(10)
            else:
                set_num(12)
            pdf.set_text_color(224, 240, 248)
            pdf.set_xy(cx, card_y + 11)
            pdf.cell(card_w, 8, val, align="C")

        pdf.set_y(card_y + card_h + 6)

    # ── Table ──
    COL_DATE = 28
    COL_AMT  = 38
    COL_CAT  = 48
    COL_ITEM = 76   # 28+38+48+76 = 190

    def draw_table_header():
        pdf.set_fill_color(0, 201, 167)
        pdf.set_text_color(15, 25, 35)
        set_heb(9)
        pdf.set_x(x0)
        pdf.cell(COL_DATE, 9, heb("תאריך"),    fill=True, align="C")
        pdf.cell(COL_ITEM, 9, heb("פריט"),      fill=True, align="C")
        pdf.cell(COL_CAT,  9, heb("קטגוריה"),  fill=True, align="C")
        set_num(9)
        pdf.cell(COL_AMT,  9, lat("Amount (ILS)"),   fill=True, align="C")
        pdf.ln()

    draw_table_header()

    if not df.empty:
        row_h = 8
        for i, (_, row) in enumerate(df.sort_values("date", ascending=False).iterrows()):
            if pdf.get_y() > 265:
                pdf.add_page()
                bg_page()
                pdf.set_y(15)
                draw_table_header()

            fill_r, fill_g, fill_b = (22, 38, 52) if i % 2 == 0 else (18, 30, 42)
            pdf.set_fill_color(fill_r, fill_g, fill_b)

            date_str = row["date"].strftime("%d/%m/%Y") if hasattr(row["date"], "strftime") else str(row["date"])[:10]
            item_str = str(row["item"])[:30] if row["item"] else ""
            cat_str  = str(row["category"]) if row["category"] else ""
            amt_str  = lat(f"{float(row['amount']):,.0f}")

            pdf.set_x(x0)
            # Date — Helvetica
            set_num(8)
            pdf.set_text_color(200, 220, 235)
            pdf.cell(COL_DATE, row_h, lat(date_str), fill=True, align="C")
            # Item — Hebrew font
            set_heb(8)
            pdf.set_text_color(200, 220, 235)
            pdf.cell(COL_ITEM, row_h, heb(item_str), fill=True, align="R")
            # Category — Hebrew font
            pdf.cell(COL_CAT, row_h, heb(cat_str), fill=True, align="R")
            # Amount — Helvetica, accent color
            set_num(9)
            pdf.set_text_color(0, 201, 167)
            pdf.cell(COL_AMT, row_h, amt_str, fill=True, align="C")
            pdf.ln()

    # ── Category totals ──
    if not df.empty:
        pdf.ln(8)
        set_heb(11)
        pdf.set_text_color(0, 201, 167)
        pdf.set_x(x0)
        pdf.cell(0, 8, heb("סיכום לפי קטגוריה"), align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        totals = df.groupby("category")["amount"].sum().sort_values(ascending=False)
        grand  = totals.sum()

        for cat, amt in totals.items():
            bar_w = int(120 * amt / grand) if grand > 0 else 0
            pdf.set_x(x0)
            # Category name
            set_heb(9)
            pdf.set_fill_color(26, 48, 64)
            pdf.set_text_color(224, 240, 248)
            pdf.cell(130, 7, heb(str(cat)), fill=True, align="R")
            # Amount
            set_num(9)
            pdf.set_fill_color(22, 38, 52)
            pdf.set_text_color(0, 201, 167)
            pdf.cell(50, 7, lat(f"{amt:,.0f}"), fill=True, align="C")
            pdf.ln()
            # Progress bar
            pdf.set_x(x0)
            pdf.set_fill_color(26, 48, 64)
            pdf.cell(180, 2, "", fill=True)
            if bar_w > 0:
                pdf.set_xy(x0, pdf.get_y() - 2)
                pdf.set_fill_color(0, 201, 167)
                pdf.cell(bar_w, 2, "", fill=True)
            pdf.ln(3)

    return bytes(pdf.output())


# ── AUTH ──────────────────────────────────────────────────────────────────────

def login_page():
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='color:#1C1917;text-align:center'>💰 ניהול הוצאות</h2>",
                    unsafe_allow_html=True)
        st.markdown("---")

        tab_login, tab_register = st.tabs(["🔑 כניסה", "📝 הרשמה"])

        # ── כניסה ──────────────────────────────────────────────────────────────
        with tab_login:
            username = st.text_input("שם משתמש", placeholder="שם משתמש", key="login_user")
            password = st.text_input("סיסמה", type="password", placeholder="סיסמה", key="login_pass")
            if st.button("כניסה", use_container_width=True, key="login_btn"):
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

            # ── שחזור סיסמה ──
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("🔓 שכחתי סיסמה"):
                r_uid = st.number_input("Telegram user_id שלך", min_value=1, step=1, key="reset_uid")
                r_pass1 = st.text_input("סיסמה חדשה", type="password", key="reset_p1")
                r_pass2 = st.text_input("אימות סיסמה חדשה", type="password", key="reset_p2")
                if st.button("אפס סיסמה", use_container_width=True, key="reset_btn"):
                    if not r_pass1 or not r_pass2:
                        st.error("מלא את כל השדות")
                    elif r_pass1 != r_pass2:
                        st.error("הסיסמאות אינן תואמות")
                    else:
                        db = get_db()
                        res = db.table("authorized_users").select("user_id").eq("user_id", int(r_uid)).execute()
                        if not res.data:
                            st.error("המזהה לא נמצא במערכת — בדוק שהתחברת לבוט קודם")
                        else:
                            db.table("authorized_users").update({
                                "dashboard_password": hash_pw(r_pass1)
                            }).eq("user_id", int(r_uid)).execute()
                            st.success("✅ הסיסמה עודכנה! כנס עם הסיסמה החדשה")

        # ── הרשמה ──────────────────────────────────────────────────────────────
        with tab_register:
            st.markdown("<span style='color:#78716C;font-size:0.85rem'>לקבלת המזהה שלך — שלח /myid לבוט</span>",
                        unsafe_allow_html=True)
            r_telegram_id = st.number_input("Telegram user_id", min_value=1, step=1, key="reg_uid")
            r_display     = st.text_input("שם תצוגה (עברית)", placeholder="למשל: יארדן", key="reg_name")
            r_username    = st.text_input("שם משתמש לדשבורד", placeholder="לועזית בלבד", key="reg_uname")
            r_pw1         = st.text_input("סיסמה", type="password", key="reg_pw1")
            r_pw2         = st.text_input("אימות סיסמה", type="password", key="reg_pw2")

            if st.button("הירשם", use_container_width=True, key="reg_btn"):
                errors = []
                if not r_display:    errors.append("הכנס שם תצוגה")
                if not r_username:   errors.append("הכנס שם משתמש")
                if not r_pw1:        errors.append("הכנס סיסמה")
                if r_pw1 != r_pw2:   errors.append("הסיסמאות אינן תואמות")
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    db = get_db()
                    # בדוק אם user_id קיים
                    check_uid = db.table("authorized_users").select("user_id").eq("user_id", int(r_telegram_id)).execute()
                    if check_uid.data and check_uid.data[0].get("dashboard_username"):
                        st.error("המזהה הזה כבר רשום במערכת")
                    else:
                        # בדוק אם שם משתמש תפוס
                        check_uname = db.table("authorized_users").select("user_id").eq("dashboard_username", r_username).execute()
                        if check_uname.data:
                            st.error("שם המשתמש כבר תפוס — בחר שם אחר")
                        else:
                            db.table("authorized_users").upsert({
                                "user_id": int(r_telegram_id),
                                "username": r_display,
                                "dashboard_username": r_username,
                                "dashboard_password": hash_pw(r_pw1),
                                "is_admin": False,
                            }).execute()
                            fetch_users.clear()
                            st.success("✅ נרשמת בהצלחה! עבור לטאב כניסה והתחבר")
                            st.balloons()


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
                              textfont_color="#E0F0F8")
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
                    go.Bar(name="החודש", x=cmp["category"], y=cmp["החודש"], marker_color="#B45309"),
                    go.Bar(name="חודש קודם", x=cmp["category"], y=cmp["חודש קודם"], marker_color="#EDE8DC",
                           marker_line_color="#B45309", marker_line_width=1),
                ])
                fig2.update_layout(barmode="group", xaxis_tickangle=-25,
                                   legend=dict(orientation="h", font_color="#78716C"),
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
                      color_discrete_sequence=["#B45309"],
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
                      color_discrete_sequence=["#B45309"],
                      labels={"label": "חודש", "amount": "סכום (₪)"})
        fig2.update_traces(texttemplate="₪%{text:,.0f}", textposition="outside",
                           textfont_color="#E0F0F8")
        fig2.update_layout(xaxis_title="חודש", yaxis_title="סכום (₪)",
                           yaxis_tickformat=",.0f", height=300, **PLOT_LAYOUT)
        st.plotly_chart(fig2, use_container_width=True, key="bar_monthly")


def tab_recurring(user_id):
    st.markdown("### 🔄 הוצאות חוזרות")
    st.markdown("<span style='color:#78716C;font-size:0.85rem'>הוצאות שחוזרות כל חודש — הבוט ישאל לאישור ביום שהגדרת</span>",
                unsafe_allow_html=True)
    st.markdown("---")

    rows = fetch_recurring(user_id)

    if rows:
        for row in rows:
            c1, c2, c3, c4, c5 = st.columns([3, 2, 1.5, 1, 1])
            active = row["active"]
            style  = "color:#1C1917" if active else "color:#78716C;text-decoration:line-through"
            with c1:
                st.markdown(f"<span style='{style};font-weight:600'>{row['item']}</span>",
                            unsafe_allow_html=True)
            with c2:
                st.markdown(f"<span style='{style}'>{row['category']}</span>",
                            unsafe_allow_html=True)
            with c3:
                st.markdown(f"<span style='color:#B45309;font-weight:700'>₪{row['amount']:,.0f}</span>",
                            unsafe_allow_html=True)
            with c4:
                st.markdown(f"<span style='color:#78716C'>יום {row['day_of_month']}</span>",
                            unsafe_allow_html=True)
            with c5:
                cols_btn = st.columns(2)
                with cols_btn[0]:
                    toggle_label = "⏸" if active else "▶️"
                    if st.button(toggle_label, key=f"tog_{row['id']}",
                                 help="השהה" if active else "הפעל"):
                        toggle_recurring(row["id"], not active)
                        st.rerun()
                with cols_btn[1]:
                    if st.button("🗑️", key=f"del_rec_{row['id']}", help="מחק"):
                        delete_recurring(row["id"])
                        st.rerun()
        st.markdown("---")
    else:
        st.info("אין הוצאות חוזרות. הוסף את הראשונה 👇")

    # ── טופס הוספה ──
    with st.expander("➕ הוסף הוצאה חוזרת"):
        with st.form("add_recurring"):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                r_item = st.text_input("פריט", placeholder="שכר דירה")
            with c2:
                r_cat = st.selectbox("קטגוריה", CATEGORIES, key="rec_cat")
            with c3:
                r_amount = st.number_input("סכום (₪)", min_value=1.0, step=10.0)
            with c4:
                r_day = st.number_input("יום בחודש", min_value=1, max_value=28, value=1, step=1)
            if st.form_submit_button("➕ הוסף"):
                if r_item and r_amount > 0:
                    save_recurring(user_id, r_item, r_cat, r_amount, r_day)
                    st.success(f"נוסף: {r_item} — ₪{r_amount:,.0f} בכל יום {r_day} לחודש")
                    st.rerun()
                else:
                    st.error("מלא פריט וסכום")


def tab_table(df_all, user_id, selected_month, display_name):
    st.markdown("### כל ההוצאות")

    # ── הוספת הוצאה ידנית ──
    with st.expander("➕ הוסף הוצאה ידנית"):
        with st.form("manual_expense"):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                m_amount = st.number_input("סכום (₪)", min_value=0.0, step=1.0)
            with c2:
                m_category = st.selectbox("קטגוריה", CATEGORIES, key="man_cat")
            with c3:
                m_item = st.text_input("פריט")
            with c4:
                m_date = st.date_input("תאריך", value=datetime.now().date())
            if st.form_submit_button("➕ הוסף"):
                if m_amount > 0 and m_item:
                    add_expense(user_id, m_amount, m_category, m_item, m_date)
                    st.success(f"נוסף: {m_item} — ₪{m_amount:,.0f}")
                    st.rerun()
                else:
                    st.error("מלא סכום ופריט")

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

    # ── ייצוא PDF ──
    try:
        pdf_bytes = generate_pdf(df_f, selected_month, display_name)
        month_label = datetime.strptime(selected_month, "%Y-%m").strftime("%m-%Y")
        st.download_button(
            label="📄 ייצוא לPDF",
            data=pdf_bytes,
            file_name=f"expenses_{month_label}.pdf",
            mime="application/pdf",
            key="pdf_download"
        )
    except Exception as e:
        st.warning(f"לא ניתן ליצור PDF: {e}")

    # Build editable dataframe (keep id for saving)
    edit_df = df_f[["id", "category", "item", "amount", "date"]].copy()
    edit_df["date"] = edit_df["date"].dt.date
    edit_df["item"] = edit_df["item"].fillna("")
    edit_df["category"] = edit_df["category"].fillna(CATEGORIES[0])
    edit_df.insert(0, "מחק", False)
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
            "מחק": st.column_config.CheckboxColumn("🗑️", default=False),
            "קטגוריה": st.column_config.SelectboxColumn(options=CATEGORIES, required=True),
            "פריט": st.column_config.TextColumn(required=True),
            "סכום (₪)": st.column_config.NumberColumn(min_value=0, format="₪%.0f", required=True),
            "תאריך": st.column_config.DateColumn(format="DD/MM/YYYY", required=True),
        },
        key="expense_editor"
    )

    col_save, col_del, col_info = st.columns([1, 1, 2])
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
    with col_del:
        to_delete = edited[edited["מחק"] == True]
        if st.button(f"🗑️ מחק נבחרים ({len(to_delete)})", key="delete_expenses", disabled=len(to_delete) == 0):
            db = get_db()
            for _, row in to_delete.iterrows():
                db.table("expenses").delete().eq("id", int(row["id"])).execute()
            fetch_expenses.clear()
            st.success(f"נמחקו {len(to_delete)} הוצאות!")
            st.rerun()
    with col_info:
        st.markdown(f"<span style='color:#78716C'>סה\"כ: <b style='color:#B45309'>₪{df_f['amount'].sum():,.0f}</b> | {len(df_f)} הוצאות</span>",
                    unsafe_allow_html=True)


def tab_budget(df, selected_month, user_id, group_id=0):
    st.markdown("### תקציב חודשי")

    # Load from DB if not in session
    bkey = f"budget_{selected_month}_{group_id}"
    if bkey not in st.session_state:
        st.session_state[bkey] = fetch_budget(user_id, selected_month, group_id)

    budgets = st.session_state[bkey]

    st.markdown("#### הגדרת תקציב")
    cols = st.columns(3)
    new_budgets = {}
    for i, cat in enumerate(CATEGORIES):
        with cols[i % 3]:
            val = st.number_input(cat, min_value=0, step=50,
                                   value=int(budgets.get(cat, 0)),
                                   key=f"b_{cat}_{selected_month}_{group_id}")
            new_budgets[cat] = val

    if st.button("שמור תקציב", key=f"save_budget_{selected_month}_{group_id}"):
        save_budget_to_db(user_id, selected_month, new_budgets, group_id)
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
            st.markdown(f"<span style='color:#1C1917;font-weight:600'>{cat}</span>",
                        unsafe_allow_html=True)
            st.progress(pct)
        with col2:
            st.markdown(f"<span style='color:{color};font-weight:600'>₪{spent:,.0f}</span>"
                        f"<span style='color:#78716C'> / ₪{budget:,.0f}</span>",
                        unsafe_allow_html=True)


def tab_shared(groups, uid, selected_month):
    st.markdown("### הוצאות משותפות")

    if not groups:
        st.info("אין לך קבוצות. צור קבוצה בטאב ⚙️ הגדרות")
        return

    group_options = {g["id"]: g["name"] for g in groups}
    selected_gid  = st.selectbox(
        "בחר קבוצה",
        list(group_options.keys()),
        format_func=lambda x: group_options[x],
        key="shared_group_select"
    )

    member_ids = fetch_group_members(selected_gid)
    users      = fetch_users()
    user_map   = {u["user_id"]: u.get("username") or u.get("dashboard_username", str(u["user_id"])) for u in users}

    df = fetch_shared_expenses(selected_gid, selected_month)

    if df.empty:
        st.info("אין הוצאות משותפות לחודש זה.\nכשתרשום הוצאה בבוט, בחר 'שייך לקבוצה'.")
        return

    df["user_name"] = df["user_id"].map(user_map).fillna(df["user_id"].astype(str))
    totals = df.groupby("user_name")["amount"].sum().reset_index()
    grand  = totals["amount"].sum()
    totals["אחוז"] = (totals["amount"] / grand * 100).round(1)

    member_ids = [int(m) for m in member_ids]   # normalise types
    settlements = calculate_settlement(df, member_ids, user_map)
    per_person  = grand / len(member_ids) if member_ids else grand

    # ── member list banner ──
    member_names = [user_map.get(m, str(m)) for m in member_ids]
    st.markdown(
        f"<div style='background:#EDE8DC;border-radius:8px;padding:0.5rem 1rem;margin-bottom:0.8rem;border:1px solid #D6D0C6'>"
        f"<span style='color:#78716C'>חברי הקבוצה ({len(member_ids)}): </span>"
        f"<span style='color:#1C1917;font-weight:600'>{' · '.join(member_names)}</span>"
        f"</div>",
        unsafe_allow_html=True)

    if len(member_ids) < 2:
        st.warning("⚠️ הקבוצה צריכה לפחות 2 חברים לחישוב פשרה — הוסף חברים בטאב ⚙️ הגדרות")

    col1, col2 = st.columns(2)
    with col1:
        with st.container():
            fig = px.pie(totals, values="amount", names="user_name",
                         color_discrete_sequence=["#B45309", "#15803D", "#D97706", "#DC2626", "#6B7280"])
            fig.update_layout(height=300, **PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True, key="pie_shared")

    with col2:
        st.markdown("#### מי שילם כמה")
        for _, row in totals.iterrows():
            st.markdown(
                f"<span style='color:#1C1917;font-weight:600'>{row['user_name']}:</span> "
                f"<span style='color:#B45309;font-weight:700'>₪{row['amount']:,.0f}</span> "
                f"<span style='color:#78716C'>({row['אחוז']}%)</span>",
                unsafe_allow_html=True)
        st.markdown(
            f"<span style='color:#78716C'>סה\"כ: <b style='color:#B45309'>₪{grand:,.0f}</b></span>"
            f"<span style='color:#78716C'> | לאחד: <b style='color:#15803D'>₪{per_person:,.0f}</b></span>",
            unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### 💸 חישוב פשרה")
        if settlements:
            for debtor, creditor, amount in settlements:
                st.markdown(
                    f"<div style='background:#FFFFFF;border-radius:8px;padding:0.6rem 1rem;"
                    f"margin:4px 0;border:1px solid #D6D0C6;border-right:3px solid #DC2626'>"
                    f"<span style='color:#1C1917;font-weight:600'>{debtor}</span>"
                    f"<span style='color:#78716C'> חייב ל</span>"
                    f"<span style='color:#1C1917;font-weight:600'>{creditor}</span>"
                    f"<span style='color:#15803D;font-weight:700'> ₪{amount:,.0f}</span>"
                    f"</div>",
                    unsafe_allow_html=True)
        elif len(member_ids) >= 2:
            st.success("✅ הכל מחולק שווה!")

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
    # ── פרופיל — גלוי לכולם ──────────────────────────────────────────────────
    st.markdown("### 👤 פרופיל")
    uid          = st.session_state.user["user_id"]
    user_groups  = fetch_groups(uid)
    def_options  = {"אני בלבד": None}
    for g in user_groups:
        def_options[g["name"]] = g["id"]

    current_gid  = st.session_state.user.get("default_group_id")
    current_name = next((n for n, gid in def_options.items() if gid == current_gid), "אני בלבד")
    current_idx  = list(def_options.keys()).index(current_name)

    new_default = st.selectbox("תצוגת ברירת מחדל בכניסה לדשבורד",
                               list(def_options.keys()), index=current_idx,
                               key="pref_default_group")
    if st.button("💾 שמור העדפה", key="save_pref"):
        new_gid = def_options[new_default]
        save_default_group(uid, new_gid)
        st.session_state.user["default_group_id"] = new_gid
        st.success(f"✅ ברירת מחדל עודכנה: {new_default}")

    st.markdown("---")

    # ── ניהול — אדמין בלבד ───────────────────────────────────────────────────
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

    st.markdown("---")
    st.markdown("### ניהול קבוצות")

    current_user_id = st.session_state.user["user_id"]
    all_groups = fetch_groups(current_user_id)
    all_users_list = fetch_users()
    user_map = {u["user_id"]: u.get("username") or u.get("dashboard_username", str(u["user_id"])) for u in all_users_list}

    # Show existing groups
    if all_groups:
        for g in all_groups:
            with st.expander(f"👥 {g['name']}"):
                members = fetch_group_members(g["id"])
                member_names = [user_map.get(m, str(m)) for m in members]
                st.markdown(f"**חברים:** {', '.join(member_names)}")

                # Add member
                non_members = [u for u in all_users_list if u["user_id"] not in members]
                if non_members:
                    add_options = {u["user_id"]: user_map.get(u["user_id"], str(u["user_id"])) for u in non_members}
                    add_uid = st.selectbox("הוסף חבר", list(add_options.keys()),
                                           format_func=lambda x: add_options[x],
                                           key=f"add_{g['id']}")
                    if st.button("הוסף", key=f"add_btn_{g['id']}"):
                        add_group_member(g["id"], add_uid)
                        st.success("נוסף!")
                        st.rerun()

                # Remove member (not creator)
                removable = [m for m in members if m != g["created_by"]]
                if removable:
                    rem_options = {m: user_map.get(m, str(m)) for m in removable}
                    rem_uid = st.selectbox("הסר חבר", list(rem_options.keys()),
                                           format_func=lambda x: rem_options[x],
                                           key=f"rem_{g['id']}")
                    if st.button("הסר", key=f"rem_btn_{g['id']}"):
                        remove_group_member(g["id"], rem_uid)
                        st.success("הוסר!")
                        st.rerun()

                if st.button("🗑️ מחק קבוצה", key=f"del_{g['id']}"):
                    delete_group(g["id"])
                    st.success("הקבוצה נמחקה")
                    st.rerun()
    else:
        st.info("אין קבוצות עדיין")

    st.markdown("---")
    st.markdown("#### צור קבוצה חדשה")
    group_name = st.text_input("שם הקבוצה", key="new_group_name")
    if st.button("צור קבוצה"):
        if group_name:
            create_group(group_name, current_user_id)
            st.success(f"הקבוצה '{group_name}' נוצרה!")
            st.rerun()
        else:
            st.error("הכנס שם לקבוצה")


# ── AI INSIGHTS ───────────────────────────────────────────────────────────────

@st.cache_resource
def get_groq_client():
    from groq import Groq
    return Groq(api_key=GROQ_API_KEY)


def _groq_chat(messages: list) -> str:
    try:
        client = get_groq_client()
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=1200,
            temperature=0.6,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"שגיאה בחיבור ל-AI: {e}"


def _build_context(df, df_prev, budgets, month_label: str) -> str:
    lines = [f"נתוני הוצאות לחודש {month_label}:"]
    if df.empty:
        lines.append("אין הוצאות רשומות לחודש זה.")
    else:
        total = df["amount"].sum()
        lines.append(f"סה\"כ: ₪{total:,.0f} ({len(df)} הוצאות)")

        # by category
        lines.append("\nפירוט לפי קטגוריה:")
        for cat, amt in df.groupby("category")["amount"].sum().sort_values(ascending=False).items():
            pct = amt / total * 100
            budget_val = budgets.get(cat, 0)
            bstr = f"  (תקציב: ₪{budget_val:,.0f})" if budget_val > 0 else ""
            lines.append(f"  • {cat}: ₪{amt:,.0f} ({pct:.0f}%){bstr}")

        # vs prev month
        if not df_prev.empty:
            prev_total = df_prev["amount"].sum()
            change = (total - prev_total) / prev_total * 100
            direction = "עלייה" if change > 0 else "ירידה"
            lines.append(f"\nהשוואה לחודש קודם: ₪{prev_total:,.0f} → ₪{total:,.0f} ({direction} של {abs(change):.0f}%)")
            for cat in CATEGORIES:
                c = df.groupby("category")["amount"].sum().get(cat, 0)
                p = df_prev.groupby("category")["amount"].sum().get(cat, 0)
                if p > 0 and abs(c - p) / p > 0.3:
                    d = "עלה" if c > p else "ירד"
                    lines.append(f"  • {cat} {d} ב-{abs(c-p)/p*100:.0f}%")

        # top 5 expenses
        top5 = df.nlargest(5, "amount")[["item", "category", "amount", "date"]]
        lines.append("\n5 ההוצאות הגדולות:")
        for _, r in top5.iterrows():
            d = r["date"].strftime("%d/%m") if hasattr(r["date"], "strftime") else str(r["date"])[:5]
            lines.append(f"  • {r['item']} ({r['category']}) — ₪{r['amount']:,.0f} ב-{d}")

        # spending days
        by_day = df.groupby(df["date"].dt.date)["amount"].sum().sort_values(ascending=False)
        if len(by_day) > 0:
            peak_day = by_day.index[0]
            lines.append(f"\nיום הוצאה שיא: {peak_day.strftime('%d/%m/%Y')} — ₪{by_day.iloc[0]:,.0f}")

    return "\n".join(lines)


_SYSTEM_PROMPT = (
    "אתה עוזר אישי לניהול כספים. תמיד ענה בעברית. "
    "היה ידידותי, ספציפי עם מספרים ותן עצות מעשיות לחיסכון. "
    "אל תמציא נתונים — השתמש רק במה שנמסר לך."
)


def tab_insights(df, df_prev, budgets, selected_month, display_name):
    if not GROQ_API_KEY:
        st.warning("⚠️ GROQ_API_KEY לא מוגדר. הוסף אותו ב-Streamlit Secrets.")
        return

    month_label = datetime.strptime(selected_month, "%Y-%m").strftime("%m/%Y")
    context = _build_context(df, df_prev, budgets, month_label)
    insight_key = f"insight_{selected_month}"
    chat_key    = f"chat_{selected_month}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    # ── חלק א: ניתוח אוטומטי ──────────────────────────────────────────────────
    st.markdown("### 📊 ניתוח חודשי אוטומטי")

    col_refresh, col_spacer = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 רענן ניתוח", key="refresh_insight"):
            st.session_state.pop(insight_key, None)

    if insight_key not in st.session_state:
        with st.spinner("מנתח את ההוצאות שלך..."):
            prompt = (
                f"להלן נתוני ההוצאות של {display_name} לחודש {month_label}:\n\n"
                f"{context}\n\n"
                "בצע ניתוח מקיף הכולל:\n"
                "1. סיכום קצר של החודש\n"
                "2. השוואה לחודש קודם (אם יש נתונים)\n"
                "3. זיהוי 2-3 דפוסי הוצאה מעניינים\n"
                "4. 3 המלצות מעשיות לחיסכון\n\n"
                "כתוב בצורה ברורה עם כותרות ואמוג'ים."
            )
            result = _groq_chat([
                {"role": "system",  "content": _SYSTEM_PROMPT},
                {"role": "user",    "content": prompt},
            ])
            st.session_state[insight_key] = result

    # Display insight in styled card
    insight_text = st.session_state.get(insight_key, "")
    if insight_text:
        st.markdown(
            f"""<div style='background:#FFFFFF;border-radius:12px;padding:1.4rem 1.6rem;
            border:1px solid #D6D0C6;border-right:4px solid #B45309;direction:rtl;
            line-height:1.8;color:#1C1917;font-family:Heebo,sans-serif;
            white-space:pre-wrap;text-align:right;box-shadow:0 1px 4px rgba(28,25,23,0.08)'>{insight_text}</div>""",
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ── חלק ב: שאלות חופשיות ──────────────────────────────────────────────────
    st.markdown("### 💬 שאל את ה-AI על ההוצאות שלך")

    # Chat history
    for msg in st.session_state[chat_key]:
        if msg["role"] == "user":
            st.markdown(
                f"<div style='background:#EDE8DC;border-radius:10px;padding:0.7rem 1rem;"
                f"margin:6px 0;direction:rtl;text-align:right;color:#1C1917;font-family:Heebo,sans-serif'>"
                f"🙋 {msg['content']}</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div style='background:#FFFFFF;border-radius:10px;padding:0.7rem 1rem;"
                f"margin:6px 0;border:1px solid #D6D0C6;border-right:3px solid #B45309;direction:rtl;"
                f"text-align:right;color:#1C1917;font-family:Heebo,sans-serif;white-space:pre-wrap'>"
                f"🤖 {msg['content']}</div>",
                unsafe_allow_html=True
            )

    # Input
    with st.form("chat_form", clear_on_submit=True):
        user_q = st.text_input("שאל שאלה...",
                               placeholder="למשל: על מה הוצאתי הכי הרבה? איפה אפשר לחסוך?",
                               label_visibility="collapsed")
        col_ask, col_clear, _ = st.columns([1, 1, 3])
        with col_ask:
            submitted = st.form_submit_button("שאל 🤖")
        with col_clear:
            cleared = st.form_submit_button("נקה שיחה")

    if cleared:
        st.session_state[chat_key] = []
        st.rerun()

    if submitted and user_q.strip():
        history = st.session_state[chat_key]
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT + f"\n\nנתוני ההוצאות:\n{context}"},
        ]
        for m in history[-6:]:   # last 3 exchanges for context window
            messages.append(m)
        messages.append({"role": "user", "content": user_q.strip()})

        with st.spinner("חושב..."):
            answer = _groq_chat(messages)

        st.session_state[chat_key].append({"role": "user",      "content": user_q.strip()})
        st.session_state[chat_key].append({"role": "assistant", "content": answer})
        st.rerun()


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    if not st.session_state.get("logged_in"):
        login_page()
        return

    user = st.session_state.user
    uid = user["user_id"]
    display_name = user.get("username") or user.get("dashboard_username", "")

    now = datetime.now()
    month_options = []
    for i in range(12):
        d = now.replace(day=1) - timedelta(days=i * 30)
        month_options.append(d.strftime("%Y-%m"))

    groups = fetch_groups(uid)
    group_options = ["אני בלבד"] + [g["name"] for g in groups]

    # ── ברירת מחדל לקבוצה — מוגדרת פעם אחת אחרי כניסה ──
    if "group_initialized" not in st.session_state:
        st.session_state["group_initialized"] = True
        default_gid = user.get("default_group_id")
        if default_gid:
            match = next((g["name"] for g in groups if g["id"] == default_gid), None)
            if match:
                st.session_state["main_group_select"] = match

    col_title, col_month, col_group, col_logout = st.columns([3, 1.5, 1.5, 1])
    with col_month:
        selected_month = st.selectbox(
            "חודש", month_options,
            format_func=lambda x: datetime.strptime(x, "%Y-%m").strftime("%m/%Y"),
            label_visibility="collapsed"
        )
    with col_group:
        selected_group_name = st.selectbox("קבוצה", group_options,
                                           key="main_group_select",
                                           label_visibility="collapsed")
    with col_logout:
        if st.button("התנתק", use_container_width=True):
            for k in ["logged_in", "user", "group_initialized", "main_group_select"]:
                st.session_state.pop(k, None)
            st.rerun()

    # Determine which user_ids and group_id to use
    if selected_group_name == "אני בלבד":
        active_user_ids = None
        active_group_id = 0
    else:
        selected_group = next((g for g in groups if g["name"] == selected_group_name), None)
        active_user_ids = fetch_group_members(selected_group["id"]) if selected_group else None
        active_group_id = selected_group["id"] if selected_group else 0

    prev = prev_month_str(selected_month)
    df = fetch_expenses(user_id=uid, month=selected_month, user_ids=active_user_ids)
    df_prev = fetch_expenses(user_id=uid, month=prev, user_ids=active_user_ids)
    df_all = fetch_expenses(user_id=uid, user_ids=active_user_ids)

    bkey = f"budget_{selected_month}_{active_group_id}"
    if bkey not in st.session_state:
        st.session_state[bkey] = fetch_budget(uid, selected_month, active_group_id)
    budgets = st.session_state[bkey]

    month_label = datetime.strptime(selected_month, "%Y-%m").strftime("%m/%Y")
    with col_title:
        st.markdown(f"<h2 style='color:#1C1917;margin:0'>💰 ניהול הוצאות — {month_label}</h2>",
                    unsafe_allow_html=True)

    t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(
        ["📊 סקירה", "📈 מגמות", "📋 הוצאות", "🔄 חוזרות", "🎯 תקציב", "👥 משותף", "🤖 Insights", "⚙️ הגדרות"])

    with t1: tab_overview(df, df_prev, budgets)
    with t2: tab_trends(df_all)
    with t3: tab_table(df_all, uid, selected_month, display_name)
    with t4: tab_recurring(uid)
    with t5: tab_budget(df, selected_month, uid, active_group_id)
    with t6: tab_shared(groups, uid, selected_month)
    with t7: tab_insights(df, df_prev, budgets, selected_month, display_name)
    with t8: tab_settings()


if __name__ == "__main__":
    main()
