import json, os, random, re, string, base64
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===================== التشفير =====================
# هذه التوكنات مشفرة بـ Base64 (ضع معلوماتك هنا مشفرة)
# يمكنك تشفير أي نص عبر: base64.b64encode("نصك".encode()).decode()

# 1. توكن البوت (مشفّر)
ENCRYPTED_BOT_TOKEN = "ODYwOTk5NDkyNzpBQUdRTUttZmNjNUY2bHBRSjBJOGJWMzMzdWFyQ1RFcXI1X00="

# 2. معرف القناة (مشفّر)
ENCRYPTED_CHANNEL_ID = "LTEwMDQzNzU2NDE2NzM="

# 3. كلمة السر (مشفّرة)
ENCRYPTED_ADMIN_PASS = "YWRtaW4xMjM="

# 4. رقم شام كاش (مشفّر)
ENCRYPTED_SYRIA_CASH = "MGMwMDAwNTZkMDhlN2UxNjM2Y2Q0ZmI3YzVmYjg2ZmI2"

# 5. يوزر الأدمن (مشفّر)
ENCRYPTED_DEVELOPER = "QEhNZXJ0MTc="

# ===================== فك التشفير =====================
def decrypt(encrypted_text):
    return base64.b64decode(encrypted_text.encode()).decode()

# ===================== إعدادات البوت =====================
BOT_TOKEN = decrypt(ENCRYPTED_BOT_TOKEN)
ADMIN_CHANNEL_ID = decrypt(ENCRYPTED_CHANNEL_ID)
ADMIN_PASSWORD = decrypt(ENCRYPTED_ADMIN_PASS)
SYRIA_CASH_NUMBER = decrypt(ENCRYPTED_SYRIA_CASH)
DEVELOPER_USERNAME = decrypt(ENCRYPTED_DEVELOPER)

ADMIN_ID = "8243108672"  # ضع معرفك هنا (غير مشفر)
DB_FILE = 'numbers_database.json'
SYRIA_CASH_NAME = "شام كاش"
PAGE_SIZE = 6

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
    ['💰 استرجاع الأموال', '📞 الدعم الفني']
], resize_keyboard=True)

numbers_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("📱 أرقام واتساب", callback_data="whatsapp")],
    [InlineKeyboardButton("📱 أرقام تيليجرام", callback_data="telegram")],
    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
])

wallet_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("💵 شحن بالدولار", callback_data="charge#usd")],
    [InlineKeyboardButton("🇸🇾 شحن بالليرة", callback_data="charge#syr")],
    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
])

support_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("📩 إرسال شكوى / استفسار", callback_data="support#start")],
    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
])

CANCEL_BTN = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel_flow")]
])

# ===================== دوال التحكم =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    db = load_db()
    if user_id in db.get("banned", {}):
        await update.message.reply_text("🚫 حسابك محظور من استخدام هذا البوت.")
        return
    if user_id not in db["users"]:
        db["users"][user_id] = {
            "name": update.effective_user.first_name or "مستخدم",
            "balance_usd": 0,
            "joined": datetime.now().isoformat()
        }
        save_db(db)
    balance = db["users"][user_id]["balance_usd"]
    rate = db.get("exchange_rate", 13800)
    name = safe_md(update.effective_user.first_name or "مستخدم")
    text = f"🔥 **أهلاً بك في بوت أرقام واتساب وتيليجرام الوهمية (جميع الدول)** 🔥\n━━━━━━━━━━━━━━━━━━━━\n👤 مرحباً: {name}\n💰 رصيدك: ${balance:.2f}\n🇸🇾 بالليرة: {balance*rate:,.0f} ل.س\n📈 سعر الصرف: 1$ = {rate:,} ل.س\n━━━━━━━━━━━━━━━━━━━━\n⚠️ استخدم الأزرار للتنقل ❤️"
    await update.message.reply_text(text, reply_markup=main_menu)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user_id = str(update.effective_user.id)
    if is_admin(db, user_id):
        await update.message.reply_text("✅ أنت مصادق بالفعل! استخدم /panel للوحة التحكم.")
        return
    context.user_data['awaiting_password'] = True
    await update.message.reply_text("🔐 اكتب كلمة السر للتحقق:")

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user_id = str(update.effective_user.id)
    if is_admin(db, user_id):
        await update.message.reply_text("🛸 **لوحة التحكم الإدارية**", reply_markup=get_admin_panel(db))
    else:
        await update.message.reply_text("❌ ليس لديك صلاحية. استخدم /admin أولاً.")

def get_admin_panel(db):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="adm#stats")],
        [InlineKeyboardButton("➕ إضافة منتج", callback_data="adm#add_product")],
        [InlineKeyboardButton("📦 الطلبات المعلقة", callback_data="adm#pending_list")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ])

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # سيتم إضافة دوال handle_text كاملة من البوت الأساسي
    pass

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # سيتم إضافة دوال handle_callback كاملة من البوت الأساسي
    pass

# ===================== تشغيل البوت =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("panel", panel_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_text))
    print("🚀 بوت الأرقام الوهمية شغال!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
