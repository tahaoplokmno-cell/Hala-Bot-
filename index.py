import json, os, random, re, string
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===================== إعدادات البوت (عدلها هنا) =====================
BOT_TOKEN = "8609994927:AAGQMKmfcc5F6lpQ0I8bV333uarCTEqr5_M"  # توكن البوت الصحيح
ADMIN_CHANNEL_ID = "-1004375641673"  # معرف القناة
ADMIN_PASSWORD = "admin123"  # كلمة السر
DEVELOPER_USERNAME = "@Hmert17"  # يوزر الأدمن
SYRIA_CASH_NUMBER = "0c00056d08e7e1636cd4fb7c5fb86fb6"  # رقم شام كاش
ADMIN_ID = "8243108672"  # معرف الأدمن الأساسي
DB_FILE = 'numbers_database.json'
SYRIA_CASH_NAME = "شام كاش"

# ===================== دوال قاعدة البيانات =====================
def load_db():
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {
            "users": {},
            "banned": {},
            "admin_notes": "",
            "bot_maintenance": False,
            "pending_orders": {},
            "catalog": {},
            "stats": {"purchases": 0, "refunds": 0, "deposits": 0, "complaints": 0},
            "activity_log": [],
            "authenticated_admins": [],
            "exchange_rate": 13800,
            "next_node_seq": 100,
        }

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def generate_order_id():
    return ''.join(random.choices(string.digits, k=6))

def new_node_id(db, prefix="x"):
    seq = db.get("next_node_seq", 100)
    db["next_node_seq"] = seq + 1
    return f"{prefix}{seq}"

def is_admin(db, uid):
    return str(uid) in db.get("authenticated_admins", [])

def safe_md(text):
    if not text:
        return ""
    return str(text).replace('*', '').replace('_', '').replace('`', '').replace('[', '')

# ===================== القوائم والأزرار =====================
main_menu = ReplyKeyboardMarkup([
    ['📱 الأرقام', '💳 المحفظة'],
    ['💰 استرجاع', '📞 الدعم']
], resize_keyboard=True)

numbers_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("📱 أرقام واتساب", callback_data="whatsapp")],
    [InlineKeyboardButton("📱 أرقام تيليجرام", callback_data="telegram")],
    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
])

wallet_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("💳 شحن", callback_data="charge")],
    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
])

CANCEL_BTN = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_flow")]
])

# ===================== دوال التحكم =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    db = load_db()
    if user_id in db.get("banned", {}):
        await update.message.reply_text("🚫 حسابك محظور.")
        return
    if user_id not in db["users"]:
        db["users"][user_id] = {
            "name": update.effective_user.first_name or "مستخدم",
            "balance_usd": 0,
            "joined": datetime.now().isoformat()
        }
        save_db(db)
    balance = db["users"][user_id]["balance_usd"]
    text = f"مرحباً بك في بوت الأرقام.\nرصيدك الحالي: {balance}$\nاستخدم الأزرار للتنقل."
    await update.message.reply_text(text, reply_markup=main_menu)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user_id = str(update.effective_user.id)
    if is_admin(db, user_id):
        await update.message.reply_text("✅ أنت أدمن.")
        return
    context.user_data['awaiting_password'] = True
    await update.message.reply_text("🔐 اكتب كلمة السر:")

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user_id = str(update.effective_user.id)
    if is_admin(db, user_id):
        await update.message.reply_text("🛸 لوحة التحكم", reply_markup=get_admin_panel())
    else:
        await update.message.reply_text("❌ غير مصرح.")

def get_admin_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة زر", callback_data="add_button")],
        [InlineKeyboardButton("✏️ تعديل زر", callback_data="edit_button")],
        [InlineKeyboardButton("🗑️ حذف زر", callback_data="delete_button")],
        [InlineKeyboardButton("📝 إضافة نص", callback_data="add_text")],
        [InlineKeyboardButton("👥 عرض المستخدمين", callback_data="list_users")],
        [InlineKeyboardButton("📩 تواصل مع مستخدم", callback_data="contact_user")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ])

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text
    db = load_db()
    ud = context.user_data

    if ud.get('awaiting_password'):
        ud['awaiting_password'] = False
        if text.strip() == ADMIN_PASSWORD:
            if user_id not in db['authenticated_admins']:
                db['authenticated_admins'].append(user_id)
                save_db(db)
            await update.message.reply_text("✅ تم التحقق.")
        else:
            await update.message.reply_text("❌ كلمة سر خاطئة.")
        return

    if ud.get('awaiting_charge_proof'):
        # هنا معالجة وصل الشحن
        amount = ud.get('charge_amount')
        if amount is None:
            await update.message.reply_text("⚠️ لم يتم تحديد المبلغ، أعد المحاولة.")
            return
        # التحقق من أن المبلغ عدد صحيح (بدون كسور)
        if not re.match(r'^\d+$', str(amount)):
            await update.message.reply_text("❌ ممنوع الكسور، أدخل أرقاماً صحيحة فقط.")
            return
        order_id = generate_order_id()
        db['pending_orders'][order_id] = {
            "type": "charge",
            "user_id": user_id,
            "amount": amount,
            "ref": text
        }
        save_db(db)
        await update.message.reply_text(f"✅ تم إرسال طلب الشحن (رقم {order_id}) للإدارة.")
        ud['awaiting_charge_proof'] = False
        return

    if text == '📱 الأرقام':
        await update.message.reply_text("اختر القسم:", reply_markup=numbers_menu)
    elif text == '💳 المحفظة':
        balance = db["users"][user_id]["balance_usd"]
        await update.message.reply_text(f"رصيدك: {balance}$", reply_markup=wallet_menu)
    elif text == '💰 استرجاع':
        await update.message.reply_text("💰 استرجاع الأموال\nأرسل رقم الطلب للاسترجاع.", reply_markup=CANCEL_BTN)
    elif text == '📞 الدعم':
        await update.message.reply_text(f"📞 الدعم: {DEVELOPER_USERNAME}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = str(update.effective_user.id)
    db = load_db()

    if data == "whatsapp":
        await query.edit_message_text(
            "📱 أرقام واتساب\nاختر الدولة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data="numbers_back")]
            ])
        )
    elif data == "telegram":
        await query.edit_message_text(
            "📱 أرقام تيليجرام\nاختر الدولة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data="numbers_back")]
            ])
        )
    elif data == "charge":
        # طلب الشحن المباشر بدون كتابة المبلغ
        await query.edit_message_text(
            f"💳 شحن الرصيد\n"
            f"رقم شام كاش: {SYRIA_CASH_NUMBER}\n"
            f"الاسم: {SYRIA_CASH_NAME}\n\n"
            f"أرسل صورة الوصل أو رقم العملية.",
            reply_markup=CANCEL_BTN
        )
        context.user_data['awaiting_charge_proof'] = True
    elif data == "numbers_back":
        await query.edit_message_text("اختر القسم:", reply_markup=numbers_menu)
    elif data == "main_menu":
        await query.edit_message_text("القائمة الرئيسية", reply_markup=main_menu)
    elif data == "cancel_flow":
        context.user_data.clear()
        await query.edit_message_text("تم الإلغاء.", reply_markup=main_menu)
    elif data.startswith("adm#"):
        # لوحة التحكم
        if not is_admin(db, user_id):
            await query.edit_message_text("❌ غير مصرح.")
            return
        action = data.split('#')[1]
        if action == "stats":
            total_users = len(db["users"])
            total_balance = sum(u.get("balance_usd", 0) for u in db["users"].values())
            await query.edit_message_text(
                f"📊 الإحصائيات\n"
                f"المستخدمين: {total_users}\n"
                f"إجمالي الأرصدة: {total_balance}$"
            )
        elif action == "list_users":
            users_list = "\n".join([f"`{uid}` - {u.get('name', 'مجهول')}" for uid, u in list(db["users"].items())[:10]])
            await query.edit_message_text(f"👥 المستخدمون:\n{users_list}")
        else:
            await query.edit_message_text("🛠️ جارٍ التطوير...")

# ===================== تشغيل البوت =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("panel", panel_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_text))
    print("🚀 البوت شغال!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
