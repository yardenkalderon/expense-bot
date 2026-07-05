import json
import os
import base64
import hashlib
import secrets
import tempfile
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo
from collections import defaultdict
from dotenv import load_dotenv
from groq import Groq
from supabase import create_client
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler, CallbackQueryHandler

load_dotenv()

TELEGRAM_TOKEN  = os.environ['TELEGRAM_TOKEN']
GROQ_API_KEY    = os.environ['GROQ_API_KEY']
ACCESS_PASSWORD = os.environ['ACCESS_PASSWORD']
SUPABASE_URL    = os.environ['SUPABASE_URL']
SUPABASE_KEY    = os.environ['SUPABASE_KEY']
DASHBOARD_URL   = os.environ.get('DASHBOARD_URL', '')

client = Groq(api_key=GROQ_API_KEY)
db = create_client(SUPABASE_URL, SUPABASE_KEY)

TZ = ZoneInfo("Asia/Jerusalem")

CATEGORIES = ["אוכל ושתייה", "קניות וסופר", "תחבורה ודלק", "פנאי ובילוי", "חשבונות ובית", "בריאות", "אחר"]

password_attempts = {}
pending_reset = set()
pending_username = set()
MAX_ATTEMPTS = 5


def is_authorized(user_id):
    result = db.table('authorized_users').select('user_id').eq('user_id', user_id).execute()
    return len(result.data) > 0


def authorize_user(user_id):
    db.table('authorized_users').upsert({'user_id': user_id}).execute()


def save_username(user_id, username):
    db.table('authorized_users').update({'username': username}).eq('user_id', user_id).execute()


def get_monthly_report(user_id):
    month = datetime.now(TZ).strftime("%Y-%m")
    result = db.table('expenses').select('category,amount').eq('user_id', user_id).like('date', f'{month}%').execute()
    rows = result.data
    if not rows:
        return "אין לך הוצאות רשומות לחודש זה."
    totals = defaultdict(float)
    for row in rows:
        totals[row['category']] += row['amount']
    sorted_totals = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    report = f"📊 *סיכום הוצאות ל-{datetime.now(TZ).strftime('%m/%Y')}:*\n\n"
    total = sum(totals.values())
    for cat, amt in sorted_totals:
        report += f"▫️ *{cat}:* {amt:,.2f} ש\"ח\n"
    report += f"\n💰 *סה\"כ: {total:,.2f} ש\"ח*"
    return report


def get_week_report(user_id):
    week_ago = (datetime.now(TZ) - timedelta(days=7)).strftime("%Y-%m-%d")
    result = db.table('expenses').select('category,amount').eq('user_id', user_id).gte('date', week_ago).execute()
    rows = result.data
    if not rows:
        return "אין הוצאות בשבוע האחרון."
    totals = defaultdict(float)
    for row in rows:
        totals[row['category']] += row['amount']
    sorted_totals = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    report = f"📊 *סיכום שבועי (7 ימים אחרונים):*\n\n"
    for cat, amt in sorted_totals:
        report += f"▫️ *{cat}:* {amt:,.0f} ש\"ח\n"
    report += f"\n💰 *סה\"כ: {sum(totals.values()):,.0f} ש\"ח*"
    return report


def get_category_budget(user_id, category):
    month = datetime.now(TZ).strftime("%Y-%m")
    result = db.table('budgets').select('amount').eq('user_id', user_id).eq('month', month).eq('category', category).eq('group_id', 0).execute()
    return result.data[0]['amount'] if result.data else None


def get_category_spent(user_id, category):
    month = datetime.now(TZ).strftime("%Y-%m")
    result = db.table('expenses').select('amount').eq('user_id', user_id).like('date', f'{month}%').eq('category', category).execute()
    return sum(r['amount'] for r in (result.data or []))


def get_user_groups(user_id):
    result = db.table('group_members').select('group_id').eq('user_id', user_id).execute()
    return [r['group_id'] for r in (result.data or [])]


def get_user_groups_with_names(user_id):
    group_ids = get_user_groups(user_id)
    if not group_ids:
        return []
    result = db.table('groups').select('id,name').in_('id', group_ids).execute()
    return result.data or []


def get_group_other_members(user_id, group_id):
    result = db.table('group_members').select('user_id').eq('group_id', group_id).neq('user_id', user_id).execute()
    return [r['user_id'] for r in (result.data or [])]


def get_username(user_id):
    result = db.table('authorized_users').select('username').eq('user_id', user_id).execute()
    return result.data[0].get('username', '') if result.data else ''


def get_last_expenses(user_id):
    result = db.table('expenses').select('item,amount,category,date').eq('user_id', user_id).order('id', desc=True).limit(10).execute()
    rows = result.data
    if not rows:
        return "אין לך הוצאות רשומות עדיין."
    text = "🧾 *10 ההוצאות האחרונות שלך:*\n\n"
    for row in rows:
        text += f"• {row['item']} — *{row['amount']:,.0f} ש\"ח* ({row['category']}) [{row['date'][:10]}]\n"
    return text


def save_expense(user_id, amount, category, item):
    result = db.table('expenses').insert({
        'user_id': user_id,
        'amount': amount,
        'category': category,
        'item': item,
        'date': datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    }).execute()
    return result.data[0]['id'] if result.data else None


def analyze_text_with_ai(user_text):
    categories_str = ", ".join(CATEGORIES)
    system_prompt = (
        f"Return ONLY JSON with keys: 'amount' (number), 'category' (Hebrew string), 'item' (Hebrew string). "
        f"You MUST use ONLY one of these exact categories: {categories_str}. "
        f"Do NOT create new categories. If unsure, use 'אחר'."
    )
    last_error = None
    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze: {user_text}"}
                ],
                response_format={"type": "json_object"}
            )
            data = json.loads(completion.choices[0].message.content)
            if not isinstance(data.get('amount'), (int, float)):
                data['amount'] = 0
            if data.get('category') not in CATEGORIES:
                data['category'] = 'אחר'
            if not data.get('item'):
                data['item'] = 'לא ידוע'
            return data
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            last_error = e
            break  # JSON בעייתי — retry לא יעזור
        except Exception as e:
            last_error = e  # שגיאת API — כדאי לנסות שוב
    raise RuntimeError(f"Groq API failed after retries: {last_error}")


async def start_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "👋 *שלום! אני הבוט לניהול ההוצאות שלך*\n\n"
        "אני עוזר לך לעקוב אחרי ההוצאות היומיות שלך בקלות — "
        "פשוט כתוב לי במשפט רגיל מה קנית, ואני אדאג לשאר.\n\n"
        "━━━━━━━━━━━━━━━\n"
        "📝 *רישום הוצאה*\n"
        "• טקסט: _קפה 15 שקל_\n"
        "• הקלטה קולית: פשוט תדבר\n"
        "• תמונת קבלה: שלח תמונה של הקבלה\n\n"
        "━━━━━━━━━━━━━━━\n"
        "📊 *צפייה בנתונים*\n"
        "• *דוח* — סיכום הוצאות לפי קטגוריה החודש\n"
        "• *מה קניתי* — 10 ההוצאות האחרונות\n\n"
        "━━━━━━━━━━━━━━━\n"
        "🛠️ *ניהול*\n"
        "• *טעות* — מחיקת ההוצאה האחרונה\n"
        "• *איפוס* — מחיקת כל הנתונים שלך\n"
        "• *עזרה* — הצגת הודעה זו\n\n"
        "━━━━━━━━━━━━━━━\n"
        "🗂️ *קטגוריות:*\n"
        "אוכל ושתייה | קניות וסופר | תחבורה ודלק\n"
        "פנאי ובילוי | חשבונות ובית | בריאות | אחר"
    )
    if DASHBOARD_URL:
        help_text += (
            "\n\n━━━━━━━━━━━━━━━\n"
            "💻 *דשבורד ניהול*\n"
            "צפה בגרפים, ניתוח AI, הוצאות חוזרות,\n"
            "תקציב חודשי והוצאות משותפות עם הקבוצה שלך.\n\n"
            f"🔗 {DASHBOARD_URL}\n"
            "🪪 לקבלת המזהה שלך לכניסה: /myid\n"
            "🔑 שכחת סיסמה לדשבורד? /resetpass"
        )
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def myid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = f"🪪 *המזהה שלך:*\n`{user_id}`\n\n_(לחץ על המספר להעתקה)_"
    if DASHBOARD_URL:
        text += f"\n\n📊 השתמש במזהה זה בעת ההרשמה לדשבורד:\n{DASHBOARD_URL}"
    await update.message.reply_text(text, parse_mode='Markdown')


async def resetpass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """שולח קוד אימות חד-פעמי לאיפוס סיסמת הדשבורד. רק למשתמשים מורשים."""
    if not update.message:
        return
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        return
    code = f"{secrets.randbelow(1000000):06d}"
    expires = (datetime.now(TZ) + timedelta(minutes=15)).isoformat()
    db.table('authorized_users').update({
        'reset_code': hashlib.sha256(code.encode()).hexdigest(),
        'reset_code_expires': expires
    }).eq('user_id', user_id).execute()
    await update.message.reply_text(
        f"🔑 *קוד אימות לאיפוס סיסמה בדשבורד:*\n\n`{code}`\n\n"
        f"הזן אותו בטופס \"שכחתי סיסמה\" בדשבורד.\nהקוד תקף ל-15 דקות.",
        parse_mode='Markdown'
    )


async def check_auth(update: Update, user_text: str) -> bool:
    user_id = update.message.from_user.id
    if is_authorized(user_id):
        return True
    attempts = password_attempts.get(user_id, 0)
    if attempts >= MAX_ATTEMPTS:
        await update.message.reply_text("🚫 חשבונך נחסם עקב יותר מדי ניסיונות כושלים.")
        return False
    if user_text == ACCESS_PASSWORD:
        authorize_user(user_id)
        password_attempts.pop(user_id, None)
        pending_username.add(user_id)
        dashboard_line = f"\n\n📊 לדשבורד ההוצאות: {DASHBOARD_URL}\nהירשם עם המזהה שלך: `{user_id}` (או שלח /myid)" if DASHBOARD_URL else ""
        await update.message.reply_text(
            f"✅ הסיסמה נכונה! ברוך הבא.{dashboard_line}\n\nאיך קוראים לך? (שלח את שמך)",
            parse_mode='Markdown'
        )
    else:
        password_attempts[user_id] = attempts + 1
        remaining = MAX_ATTEMPTS - password_attempts[user_id]
        if remaining > 0:
            await update.message.reply_text(f"🔐 הבוט נעול. נא להזין סיסמה. נותרו {remaining} ניסיונות.")
        else:
            await update.message.reply_text("🚫 חשבונך נחסם עקב יותר מדי ניסיונות כושלים.")
    return False


async def _register_expense(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            user_id: int, amount, category: str, item: str, header: str = ""):
    """שומר הוצאה, שולח אישור עם כפתורים, ובודק תקציב. משותף לטקסט/קול/קבלה."""
    exp_id = save_expense(user_id, amount, category, item)
    conf_text = f"{header}✅ נרשם: *{amount:,.0f} ש\"ח* על {item}\n📂 קטגוריה: {category}"
    if exp_id and get_user_groups_with_names(user_id):
        conf_text += "\n\n*לאן לשייך?*"
    await update.message.reply_text(conf_text, reply_markup=_full_keyboard(exp_id, user_id), parse_mode='Markdown')
    # התראת תקציב
    budget = get_category_budget(user_id, category)
    if budget:
        spent = get_category_spent(user_id, category)
        pct = spent / budget
        if pct >= 1.0:
            await update.message.reply_text(
                f"🚨 חרגת מהתקציב בקטגוריה *{category}*!\n"
                f"הוצאת *{spent:,.0f} ש\"ח* מתוך תקציב *{budget:,.0f} ש\"ח*",
                parse_mode='Markdown'
            )
        elif pct >= 0.9:
            await update.message.reply_text(
                f"⚠️ הגעת ל-{pct*100:.0f}% מהתקציב בקטגוריה *{category}*!\n"
                f"נשאר לך רק *{budget - spent:,.0f} ש\"ח*",
                parse_mode='Markdown'
            )


async def process_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    try:
        data = analyze_text_with_ai(text)
        amount = data.get('amount', 0)
        category = data.get('category', 'אחר')
        item = data.get('item', 'לא ידוע')
        if amount > 0:
            await _register_expense(update, context, user_id, amount, category, item)
        else:
            await update.message.reply_text(
                "לא הצלחתי לזהות סכום. נסה לנסח מחדש, למשל: _קפה 15 שקל_",
                parse_mode='Markdown'
            )
    except Exception as e:
        err_msg = str(e)
        if "Groq" in err_msg or "API" in err_msg or "retries" in err_msg:
            await update.message.reply_text("⚠️ שירות ה-AI לא זמין כרגע. נסה שוב בעוד כמה שניות.")
        else:
            await update.message.reply_text("לא הצלחתי לעבד את הבקשה. נסה לנסח מחדש, למשל: _קפה 15 שקל_", parse_mode='Markdown')


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.message.from_user.id
    if not await check_auth(update, ""):
        return
    await update.message.reply_chat_action("typing")
    try:
        voice_file = await update.message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await voice_file.download_to_drive(tmp_path)
        with open(tmp_path, 'rb') as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                language="he"
            )
        os.unlink(tmp_path)
        transcribed_text = transcription.text
        await update.message.reply_text(f"🎙️ שמעתי: _{transcribed_text}_", parse_mode='Markdown')
        await process_and_save(update, context, user_id, transcribed_text)
    except Exception:
        await update.message.reply_text("אירעה שגיאה בעיבוד ההקלטה. נסה שוב.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.message.from_user.id
    if not await check_auth(update, ""):
        return
    await update.message.reply_chat_action("typing")
    try:
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        await photo_file.download_to_drive(tmp_path)
        with open(tmp_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        os.unlink(tmp_path)
        categories_str = ", ".join(CATEGORIES)
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                    {"type": "text", "text": (
                        f"This is a receipt. Extract the expense info. "
                        f"Return ONLY JSON with keys: 'amount' (total number in ILS), "
                        f"'category' (Hebrew string), 'item' (Hebrew string describing what was purchased). "
                        f"You MUST use ONLY one of these exact categories: {categories_str}. "
                        f"Do NOT create new categories. If unsure, use 'אחר'."
                    )}
                ]
            }],
            response_format={"type": "json_object"}
        )
        data = json.loads(completion.choices[0].message.content)
        amount = data.get('amount', 0)
        category = data.get('category', 'אחר')
        if category not in CATEGORIES:
            category = 'אחר'
        item = data.get('item', 'לא ידוע')
        if amount > 0:
            await _register_expense(update, context, user_id, amount, category, item, header="🧾 קבלה זוהתה!\n")
        else:
            await update.message.reply_text("לא הצלחתי לזהות סכום בקבלה. נסה לצלם שוב בצורה ברורה יותר.")
    except Exception:
        await update.message.reply_text("אירעה שגיאה בעיבוד הקבלה. נסה שוב.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_id = update.message.from_user.id
    user_text = update.message.text.strip()

    if not await check_auth(update, user_text):
        return

    # שמירת שם משתמש
    if user_id in pending_username:
        pending_username.discard(user_id)
        save_username(user_id, user_text)
        await update.message.reply_text(
            f"👋 שלום {user_text}! שמחים שהצטרפת.\n\nשלח *עזרה* להוראות שימוש.",
            parse_mode='Markdown'
        )
        return

    # עריכת הוצאה — ממתין לקלט מהמשתמש
    if 'pending_edit' in context.user_data:
        edit_info = context.user_data.pop('pending_edit')
        exp_id = edit_info['exp_id']
        field  = edit_info['field']
        if field == 'amount':
            try:
                new_amount = float(user_text.replace(',', '').replace('₪', '').replace('ש"ח', '').strip())
                db.table('expenses').update({'amount': new_amount}).eq('id', exp_id).execute()
                res = db.table('expenses').select('item,amount,category').eq('id', exp_id).execute()
                if res.data:
                    row = res.data[0]
                    await update.message.reply_text(
                        f"✅ עודכן: *{row['amount']:,.0f} ש\"ח* על {row['item']}\n📂 קטגוריה: {row['category']}",
                        parse_mode='Markdown',
                        reply_markup=_full_keyboard(exp_id, user_id)
                    )
            except ValueError:
                await update.message.reply_text("לא הצלחתי להבין את הסכום. שלח מספר בלבד, למשל: *50*", parse_mode='Markdown')
                context.user_data['pending_edit'] = edit_info  # שמור מחדש
        elif field == 'item':
            db.table('expenses').update({'item': user_text}).eq('id', exp_id).execute()
            res = db.table('expenses').select('item,amount,category').eq('id', exp_id).execute()
            if res.data:
                row = res.data[0]
                await update.message.reply_text(
                    f"✅ עודכן: *{row['amount']:,.0f} ש\"ח* על {row['item']}\n📂 קטגוריה: {row['category']}",
                    parse_mode='Markdown',
                    reply_markup=_full_keyboard(exp_id, user_id)
                )
        return

    # אישור איפוס
    if user_id in pending_reset:
        pending_reset.discard(user_id)
        if user_text in ["כן", "אישור", "מאשר"]:
            db.table('expenses').delete().eq('user_id', user_id).execute()
            await update.message.reply_text("🗑️ כל הנתונים שלך נמחקו.")
        else:
            await update.message.reply_text("❌ האיפוס בוטל.")
        return

    if any(k in user_text for k in ["עזרה", "help"]):
        await start_help(update, context)
        return

    if any(k in user_text for k in ["דוח", "סיכום", "כמה בזבזתי"]):
        await update.message.reply_text(get_monthly_report(user_id), parse_mode='Markdown')
        return

    if "מה קניתי" in user_text:
        await update.message.reply_text(get_last_expenses(user_id), parse_mode='Markdown')
        return

    if any(k in user_text for k in ["מחק הוצאה אחרונה", "טעות", "בטל"]):
        result = db.table('expenses').select('id,item,amount').eq('user_id', user_id).order('id', desc=True).limit(1).execute()
        if result.data:
            row = result.data[0]
            db.table('expenses').delete().eq('id', row['id']).execute()
            await update.message.reply_text(f"🗑️ נמחק: {row['item']} ({row['amount']:,.0f} ש\"ח).")
        else:
            await update.message.reply_text("לא נמצאו הוצאות למחיקה.")
        return

    if "איפוס" in user_text:
        pending_reset.add(user_id)
        await update.message.reply_text(
            "⚠️ האם אתה בטוח שברצונך למחוק את *כל* ההוצאות שלך?\n\n"
            "שלח *כן* לאישור או כל הודעה אחרת לביטול.",
            parse_mode='Markdown'
        )
        return

    await update.message.reply_chat_action("typing")
    await process_and_save(update, context, user_id, user_text)


async def weekly_report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        return
    await update.message.reply_text(get_week_report(user_id), parse_mode='Markdown')


async def send_recurring_reminders(bot):
    now = datetime.now(TZ)
    today_day = now.day
    current_month = now.strftime("%Y-%m")
    # כולל "השלמה": כל הוצאה שיומה כבר הגיע החודש ועוד לא נשלחה עליה תזכורת
    rows = (db.table("recurring_expenses")
              .select("*")
              .eq("active", True)
              .lte("day_of_month", today_day)
              .execute().data or [])
    for row in rows:
        if row.get("last_reminded") == current_month:
            continue  # כבר נשלחה תזכורת החודש — דלג כדי למנוע כפילות
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ כן, רשום", callback_data=f"rec_yes_{row['id']}"),
            InlineKeyboardButton("❌ דלג החודש",  callback_data=f"rec_skip_{row['id']}")
        ]])
        try:
            await bot.send_message(
                chat_id=row["user_id"],
                text=f"🔄 *{row['item']}* — ₪{row['amount']:,.0f}\nלרשום אוטומטית לחודש זה?",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            db.table("recurring_expenses").update(
                {"last_reminded": current_month}
            ).eq("id", row["id"]).execute()
        except Exception:
            pass


async def handle_recurring_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts  = query.data.split("_")   # rec_yes_5  or  rec_skip_5
    action = parts[1]
    rec_id = int(parts[2])

    if action == "yes":
        result = db.table("recurring_expenses").select("*").eq("id", rec_id).execute()
        if result.data:
            row = result.data[0]
            save_expense(row["user_id"], row["amount"], row["category"], row["item"])
            await query.edit_message_text(
                f"✅ נרשם: *{row['item']}* — ₪{row['amount']:,.0f} ({row['category']})",
                parse_mode='Markdown'
            )
    else:
        result = db.table("recurring_expenses").select("item").eq("id", rec_id).execute()
        item = result.data[0]["item"] if result.data else ""
        await query.edit_message_text(f"⏭️ *{item}* — דולג החודש", parse_mode='Markdown')


async def handle_share_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")   # share_grp_{exp_id}_{group_id}  or  share_skip_{exp_id}
    action = parts[1]

    if action == "grp":
        exp_id   = int(parts[2])
        group_id = int(parts[3])
        db.table('expenses').update({'group_id': group_id}).eq('id', exp_id).execute()
        group_res = db.table('groups').select('name').eq('id', group_id).execute()
        group_name = group_res.data[0]['name'] if group_res.data else str(group_id)
        exp_res = db.table('expenses').select('item,amount,category').eq('id', exp_id).execute()
        edit_del_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✏️ ערוך", callback_data=f"edit_start_{exp_id}"),
            InlineKeyboardButton("🗑️ מחק",  callback_data=f"del_{exp_id}")
        ]])
        if exp_res.data:
            row = exp_res.data[0]
            await query.edit_message_text(
                f"✅ נרשם: *{row['amount']:,.0f} ש\"ח* על {row['item']}\n"
                f"📂 קטגוריה: {row['category']}\n"
                f"👥 שויך ל*{group_name}*",
                parse_mode='Markdown',
                reply_markup=edit_del_kb
            )
            # התראה לחברי הקבוצה — רק אחרי שההוצאה שויכה אליה בפועל
            sharer_id = query.from_user.id
            username = get_username(sharer_id) or "חבר קבוצה"
            for member_id in get_group_other_members(sharer_id, group_id):
                try:
                    await context.bot.send_message(
                        chat_id=member_id,
                        text=f"💸 *{username}* הוסיף ל*{group_name}*: *{row['amount']:,.0f} ש\"ח* על {row['item']} ({row['category']})",
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass
        else:
            await query.edit_message_reply_markup(reply_markup=edit_del_kb)
    else:  # skip — keep as personal
        exp_id = int(parts[2])
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✏️ ערוך", callback_data=f"edit_start_{exp_id}"),
            InlineKeyboardButton("🗑️ מחק",  callback_data=f"del_{exp_id}")
        ]]))


def _full_keyboard(exp_id, user_id):
    """בונה keyboard מלא: שיוך קבוצה (אם יש) + ערוך/מחק."""
    edit_del_row = [
        InlineKeyboardButton("✏️ ערוך", callback_data=f"edit_start_{exp_id}"),
        InlineKeyboardButton("🗑️ מחק",  callback_data=f"del_{exp_id}")
    ]
    groups = get_user_groups_with_names(user_id)
    if groups:
        btn_rows = [[InlineKeyboardButton(f"👥 {g['name']}", callback_data=f"share_grp_{exp_id}_{g['id']}")]
                    for g in groups]
        btn_rows.append([InlineKeyboardButton("👤 אישי", callback_data=f"share_skip_{exp_id}")])
        btn_rows.append(edit_del_row)
        return InlineKeyboardMarkup(btn_rows)
    return InlineKeyboardMarkup([edit_del_row])


async def handle_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")   # edit_start_5 / edit_amount_5 / edit_item_5 / edit_cat_5 / edit_cancel_5

    sub   = parts[1]
    exp_id = int(parts[2])

    if sub == "start":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💰 סכום",     callback_data=f"edit_amount_{exp_id}"),
                InlineKeyboardButton("📂 קטגוריה",  callback_data=f"edit_cat_{exp_id}"),
                InlineKeyboardButton("📝 פריט",     callback_data=f"edit_item_{exp_id}"),
            ],
            [InlineKeyboardButton("🔙 ביטול", callback_data=f"edit_cancel_{exp_id}")]
        ])
        await query.edit_message_reply_markup(reply_markup=kb)

    elif sub == "amount":
        context.user_data['pending_edit'] = {'exp_id': exp_id, 'field': 'amount'}
        await query.edit_message_text(
            (query.message.text or "") + "\n\n✏️ *שלח את הסכום החדש:*",
            parse_mode='Markdown'
        )

    elif sub == "item":
        context.user_data['pending_edit'] = {'exp_id': exp_id, 'field': 'item'}
        await query.edit_message_text(
            (query.message.text or "") + "\n\n✏️ *שלח את שם הפריט החדש:*",
            parse_mode='Markdown'
        )

    elif sub == "cat":
        cat_rows = [[InlineKeyboardButton(cat, callback_data=f"editcat_{exp_id}_{i}")]
                    for i, cat in enumerate(CATEGORIES)]
        cat_rows.append([InlineKeyboardButton("🔙 ביטול", callback_data=f"edit_cancel_{exp_id}")])
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(cat_rows))

    elif sub == "cancel":
        await query.edit_message_reply_markup(reply_markup=_full_keyboard(exp_id, query.from_user.id))


async def handle_editcat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """editcat_{exp_id}_{cat_index}"""
    query = update.callback_query
    await query.answer()
    parts   = query.data.split("_")   # editcat_5_2
    exp_id  = int(parts[1])
    new_cat = CATEGORIES[int(parts[2])]
    user_id = query.from_user.id

    db.table('expenses').update({'category': new_cat}).eq('id', exp_id).execute()
    res = db.table('expenses').select('item,amount,category').eq('id', exp_id).execute()
    if res.data:
        row = res.data[0]
        await query.edit_message_text(
            f"✅ עודכן: *{row['amount']:,.0f} ש\"ח* על {row['item']}\n📂 קטגוריה: {row['category']}",
            parse_mode='Markdown',
            reply_markup=_full_keyboard(exp_id, user_id)
        )


async def handle_del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """del_{exp_id}"""
    query = update.callback_query
    await query.answer()
    exp_id = int(query.data.split("_")[1])

    res = db.table('expenses').select('item,amount').eq('id', exp_id).execute()
    if res.data:
        row = res.data[0]
        db.table('expenses').delete().eq('id', exp_id).execute()
        await query.edit_message_text(
            f"🗑️ נמחק: *{row['item']}* — ₪{row['amount']:,.0f}",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("לא נמצאה ההוצאה.")


def copy_budgets_for_new_month():
    """ב-1 בחודש: מעתיק תקציב מהחודש הקודם לכל משתמש/קבוצה שעוד אין להם תקציב החודש."""
    now = datetime.now(TZ)
    current_month = now.strftime("%Y-%m")
    prev_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    prev_rows = db.table('budgets').select('*').eq('month', prev_month).execute().data or []
    if not prev_rows:
        return
    curr_rows = db.table('budgets').select('user_id,group_id').eq('month', current_month).execute().data or []
    has_current = {(r['user_id'], r.get('group_id', 0)) for r in curr_rows}
    for r in prev_rows:
        if (r['user_id'], r.get('group_id', 0)) in has_current:
            continue  # כבר הוגדר תקציב החודש — לא דורסים
        db.table('budgets').insert({
            'user_id': r['user_id'],
            'group_id': r.get('group_id', 0),
            'month': current_month,
            'category': r['category'],
            'amount': r['amount'],
        }).execute()


async def send_monthly_summaries(bot):
    result = db.table('authorized_users').select('user_id').execute()
    for row in (result.data or []):
        uid = row['user_id']
        report = get_monthly_report(uid)
        try:
            await bot.send_message(chat_id=uid, text=f"📅 *סיכום חודשי אוטומטי*\n\n{report}", parse_mode='Markdown')
        except Exception:
            pass


async def _recurring_job(context: ContextTypes.DEFAULT_TYPE):
    await send_recurring_reminders(context.bot)


async def _monthly_job(context: ContextTypes.DEFAULT_TYPE):
    # רץ כל יום ב-20:00 — שולח רק אם היום הוא היום האחרון בחודש
    now = datetime.now(TZ)
    if (now + timedelta(days=1)).month != now.month:
        await send_monthly_summaries(context.bot)


async def _budget_copy_job(context: ContextTypes.DEFAULT_TYPE):
    # רץ כל יום ב-00:10 — מעתיק תקציב רק ב-1 בחודש
    if datetime.now(TZ).day == 1:
        copy_budgets_for_new_month()


async def post_init(application):
    jq = application.job_queue
    # תזכורת יומית ב-09:00 שעון ישראל
    jq.run_daily(_recurring_job, time=dtime(hour=9, minute=0, tzinfo=TZ))
    # רשת ביטחון + השלמה בהפעלה: בדיקה כל שעה (חסינה לכפילויות דרך last_reminded)
    jq.run_repeating(_recurring_job, interval=3600, first=10)
    # סיכום חודשי ב-20:00 ביום האחרון של החודש
    jq.run_daily(_monthly_job, time=dtime(hour=20, minute=0, tzinfo=TZ))
    # העתקת תקציב אוטומטית ב-1 בחודש (00:10), כולל השלמה אם הבוט הופעל מחדש באותו יום
    jq.run_daily(_budget_copy_job, time=dtime(hour=0, minute=10, tzinfo=TZ))
    jq.run_once(_budget_copy_job, when=20)


if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_help))
    app.add_handler(CommandHandler("help", start_help))
    app.add_handler(CommandHandler("myid", myid_cmd))
    app.add_handler(CommandHandler("resetpass", resetpass_cmd))
    app.add_handler(CommandHandler("week", weekly_report_cmd))
    app.add_handler(CallbackQueryHandler(handle_recurring_callback, pattern="^rec_"))
    app.add_handler(CallbackQueryHandler(handle_share_callback,     pattern="^share_"))
    app.add_handler(CallbackQueryHandler(handle_edit_callback,      pattern="^edit_"))
    app.add_handler(CallbackQueryHandler(handle_editcat_callback,   pattern="^editcat_"))
    app.add_handler(CallbackQueryHandler(handle_del_callback,       pattern="^del_"))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("🚀 הבוט רץ!")
    app.run_polling()
