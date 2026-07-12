import json
import random
import re
import string
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, BufferedInputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===================== إعدادات البوت (عدلها هنا) =====================
BOT_TOKEN = "8609994927:AAGQMKmfcc5F6lpQ0I8bV333uarCTEqr5_M"
ADMIN_CHANNEL_ID = "-1004375641673"
ADMIN_PASSWORD = "admin123"
DEVELOPER_USERNAME = "@Hmert17"
SYRIA_CASH_NUMBER = "0c00056d08e7e1636cd4fb7c5fb86fb6"
SYRIA_CASH_NAME = "شام كاش"
ADMIN_ID = "8243108672"
DB_FILE = 'numbers_database.json'
PAGE_SIZE = 6

PURCHASE_WARNING = (
    "⚠️ **تنبيه هام قبل الطلب:**\n"
    "سيتم تسليم الرقم/الكود مباشرة بعد الموافقة على طلبك.\n"
    "❌ في حال وجود أي مشكلة بالرقم يرجى التواصل مع الدعم فوراً.\n"
    "✅ تأكد من قراءة الوصف جيداً قبل الشراء."
)


# ===================== دوال قاعدة البيانات =====================
def default_db():
    return {
        "users": {},
        "banned": {},
        "admin_notes": "",
        "bot_maintenance": False,
        "pending_orders": {},
        "catalog": {},
        "catalog_roots": {"whatsapp": [], "telegram": []},
        "stats": {"purchases": 0, "refunds": 0, "deposits": 0, "complaints": 0},
        "activity_log": [],
        "authenticated_admins": [],
        "exchange_rate": 13800,
        "next_node_seq": 100,
    }


def load_db():
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
    for k, v in default_db().items():
        if k not in data:
            data[k] = v
    return data


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


def get_balance(db, uid):
    return db["users"].get(str(uid), {}).get("balance_usd", 0)


def update_balance(db, uid, amount):
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"name": "مستخدم", "balance_usd": 0, "joined": datetime.now().isoformat()}
    db["users"][uid]["balance_usd"] = db["users"][uid].get("balance_usd", 0) + amount


def log_activity(db, text):
    db.setdefault("activity_log", []).append(f"{datetime.now().strftime('%m-%d %H:%M')} | {text}")
    db["activity_log"] = db["activity_log"][-50:]


def clear_awaiting(ud):
    for k in list(ud.keys()):
        if k.startswith('awaiting_'):
            ud[k] = False


def safe_md(text):
    """يزيل الرموز التي قد تكسر تنسيق Markdown عند إدراج نص كتبه المستخدم."""
    if not text:
        return ""
    return str(text).replace('*', '').replace('_', '').replace('`', '').replace('[', '').replace(']', '')


async def notify_admin_dm(context, text, markup=None):
    try:
        await context.bot.send_message(ADMIN_ID, text, reply_markup=markup)
    except Exception:
        pass


# ===================== القوائم والأزرار =====================
main_menu = ReplyKeyboardMarkup([
    ['📱 الأرقام', '💳 المحفظة'],
    ['💰 استرجاع الأموال', '📞 الدعم الفني']
], resize_keyboard=True)

numbers_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("📱 أرقام واتساب", callback_data="root#whatsapp#0")],
    [InlineKeyboardButton("📱 أرقام تيليجرام", callback_data="root#telegram#0")],
    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
])

wallet_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("💳 شحن الرصيد", callback_data="charge")],
    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
])

support_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("📩 إرسال شكوى / استفسار", callback_data="support#start")],
    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
])

CANCEL_BTN = InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel_flow")]])


def get_admin_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 الإحصائيات الشاملة", callback_data="adm#stats")],
        [InlineKeyboardButton("📋 آخر العمليات", callback_data="adm#log")],
        [InlineKeyboardButton("📦 الطلبات المعلقة", callback_data="adm#pending_list")],
        [InlineKeyboardButton("📢 إرسال إعلان", callback_data="adm#broadcast")],
        [InlineKeyboardButton("👥 المستخدمين", callback_data="adm#users"),
         InlineKeyboardButton("💰 الأرصدة", callback_data="adm#view_balances")],
        [InlineKeyboardButton("🔎 بحث عن مستخدم", callback_data="adm#search_user")],
        [InlineKeyboardButton("➕ إضافة رصيد", callback_data="adm#add_balance"),
         InlineKeyboardButton("➖ خصم رصيد", callback_data="adm#sub_balance")],
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="adm#ban_user"),
         InlineKeyboardButton("✅ رفع الحظر", callback_data="adm#unban_user")],
        [InlineKeyboardButton("📈 تعديل سعر الصرف", callback_data="adm#edit_rate")],
        [InlineKeyboardButton("🗂️ عرض شجرة المتجر", callback_data="adm#tree")],
        [InlineKeyboardButton("➕ إضافة قسم/مجلد", callback_data="adm#add_category"),
         InlineKeyboardButton("➕ إضافة منتج", callback_data="adm#add_product")],
        [InlineKeyboardButton("✏️ تعديل السعر", callback_data="adm#edit_price"),
         InlineKeyboardButton("✏️ تعديل الوصف", callback_data="adm#edit_desc")],
        [InlineKeyboardButton("⛔ تفعيل/تعطيل عنصر", callback_data="adm#toggle")],
        [InlineKeyboardButton("🗑️ حذف عنصر", callback_data="adm#delete_node"),
         InlineKeyboardButton("♻️ استرجاع محذوف", callback_data="adm#restore_node")],
        [InlineKeyboardButton("🧹 تنظيف الطلبات المعلقة", callback_data="adm#clean")],
        [InlineKeyboardButton("🛠️ وضع الصيانة تشغيل/إيقاف", callback_data="adm#toggle_maintenance")],
        [InlineKeyboardButton("📝 ملاحظات الإدارة", callback_data="adm#admin_notes")],
        [InlineKeyboardButton("💾 نسخة احتياطية", callback_data="adm#backup")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ])


def render_listing(db, children_ids, back_cb, nav_prefix, page=0):
    cat = db["catalog"]
    items = []
    for cid in children_ids:
        node = cat.get(cid)
        if not node or node.get("deleted"):
            continue
        if node["type"] == "product" and not node.get("active", True):
            continue
        items.append((cid, node))

    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    subset = items[page * PAGE_SIZE: (page + 1) * PAGE_SIZE]

    buttons = []
    for cid, node in subset:
        cb = f"view#{cid}" if node["type"] == "product" else f"nav#{cid}#0"
        buttons.append([InlineKeyboardButton(node["name"], callback_data=cb)])

    if not items:
        buttons.append([InlineKeyboardButton("لا يوجد عناصر هنا حالياً", callback_data="noop")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"{nav_prefix}#{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("التالي ➡️", callback_data=f"{nav_prefix}#{page+1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=back_cb)])
    buttons.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def back_cb_for(node):
    if node.get("parent"):
        return f"nav#{node['parent']}#0"
    return f"root#{node['section']}#0"


# ===================== أوامر البوت =====================
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
    s = db.get("stats", {})
    total_ops = s.get("purchases", 0) + s.get("deposits", 0) + s.get("refunds", 0)
    name = safe_md(update.effective_user.first_name) or "صديقنا"
    text = (
        f"🔥 أهلاً وسهلاً بك في بوت بيع الأرقام 🔥\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 مرحباً بك: {name}\n"
        f"💰 رصيدك الحالي: {balance:.2f}$\n"
        f"🇸🇾 ما يعادله بالليرة: {balance * rate:,.0f} ل.س\n"
        f"📈 سعر الصرف الحالي: 1$ = {rate:,} ل.س\n"
        f"✅ عدد العمليات المكتملة على البوت: {total_ops}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 نوفر لك أرقام واتساب وتيليجرام بأفضل الأسعار وبشكل فوري.\n"
        f"💳 يمكنك شحن رصيدك عبر شام كاش والشراء مباشرة.\n"
        f"📞 لأي استفسار، الدعم الفني متواجد دائماً لخدمتك.\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ استخدم الأزرار أدناه للتنقل بين أقسام المتجر ❤️"
    )
    await update.message.reply_text(text, reply_markup=main_menu)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user_id = str(update.effective_user.id)
    if is_admin(db, user_id):
        await update.message.reply_text("✅ أنت مصادق بالفعل! استخدم /panel لفتح لوحة التحكم.")
        return
    clear_awaiting(context.user_data)
    context.user_data['awaiting_password'] = True
    await update.message.reply_text("🔐 اكتب كلمة السر للتحقق (مرة واحدة فقط، ستُحفظ دائماً):")


async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user_id = str(update.effective_user.id)
    if is_admin(db, user_id):
        await update.message.reply_text("🛸 لوحة التحكم الإدارية", reply_markup=get_admin_panel())
    else:
        await update.message.reply_text("❌ ليس لديك صلاحية. استخدم /admin أولاً وأدخل كلمة السر.")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user_id = str(update.effective_user.id)
    context.user_data.clear()
    await update.message.reply_text("✅ تم إلغاء أي عملية معلقة.", reply_markup=main_menu)
    if is_admin(db, user_id):
        await update.message.reply_text(
            "لديك صلاحية أدمن، اضغط لفتح لوحة التحكم:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛸 فتح لوحة التحكم", callback_data="open_panel")]])
        )


# ===================== معالج النصوص =====================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_id = str(update.effective_user.id)
    text = update.message.text
    db = load_db()
    ud = context.user_data

    if user_id in db.get("banned", {}) and not is_admin(db, user_id):
        await update.message.reply_text("🚫 حسابك محظور من استخدام هذا البوت.")
        return

    if db.get("bot_maintenance", False) and not is_admin(db, user_id):
        await update.message.reply_text("🛠️ البوت حالياً في وضع الصيانة، حاول لاحقاً 🙏")
        return

    # ---------- كلمة سر الأدمن ----------
    if ud.get('awaiting_password'):
        ud['awaiting_password'] = False
        if text.strip() == ADMIN_PASSWORD:
            if user_id not in db['authenticated_admins']:
                db['authenticated_admins'].append(user_id)
                save_db(db)
            await update.message.reply_text("✅ تم التحقق نهائياً! استخدم /panel لفتح لوحة التحكم بأي وقت.")
        else:
            await update.message.reply_text("❌ كلمة سر خاطئة!")
        return

    # ---------- الأزرار الرئيسية ----------
    if text == '📱 الأرقام':
        await update.message.reply_text("📱 اختر القسم:", reply_markup=numbers_menu)
        return
    if text == '💳 المحفظة':
        balance = get_balance(db, user_id)
        await update.message.reply_text(f"💳 رصيدك الحالي:\n💰 {balance:.2f}$", reply_markup=wallet_menu)
        return
    if text == '💰 استرجاع الأموال':
        clear_awaiting(ud)
        ud['awaiting_refund_amount'] = True
        balance = get_balance(db, user_id)
        await update.message.reply_text(
            f"💰 رصيدك الحالي: {balance:.2f}$\n✍️ اكتب المبلغ الذي تريد استرجاعه بالدولار:",
            reply_markup=CANCEL_BTN
        )
        return
    if text == '📞 الدعم الفني':
        await update.message.reply_text(
            f"📞 الدعم الفني\nللتواصل المباشر: {DEVELOPER_USERNAME}\nأو أرسل شكواك/استفسارك مباشرة من هنا:",
            reply_markup=support_menu
        )
        return

    # ---------- شكوى/دعم ----------
    if ud.get('awaiting_complaint'):
        ud['awaiting_complaint'] = False
        db['stats']['complaints'] += 1
        log_activity(db, f"شكوى جديدة من {user_id}")
        save_db(db)
        name = safe_md(update.effective_user.first_name)
        try:
            await context.bot.send_message(
                ADMIN_CHANNEL_ID,
                f"📩 شكوى / استفسار جديد\n━━━━━━━━━━━━━━━━━━━━\n👤 {name}\n🆔 {user_id}\n\n📝 {safe_md(text)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ الرد على الزبون", callback_data=f"reply_user#{user_id}")]])
            )
        except Exception:
            pass
        await update.message.reply_text("✅ تم استلام رسالتك وسيتم الرد عليك بأقرب وقت ممكن 🙏")
        return

    if ud.get('awaiting_reply_to_user'):
        target_id = ud.get('reply_target_id')
        ud['awaiting_reply_to_user'] = False
        try:
            await context.bot.send_message(target_id, f"💬 رد الدعم الفني:\n{text}")
            await update.message.reply_text(f"✅ تم إرسال الرد إلى {target_id}")
        except Exception as e:
            await update.message.reply_text(f"❌ فشل إرسال الرد: {e}")
        return

    # ---------- شحن الرصيد ----------
    if ud.get('awaiting_charge_amount'):
        try:
            amount_syp = float(text)
            if amount_syp <= 0:
                raise ValueError
        except Exception:
            await update.message.reply_text("❌ اكتب رقماً صحيحاً بالليرة السورية.", reply_markup=CANCEL_BTN)
            return
        rate = db.get('exchange_rate', 13800)
        usd_amount = amount_syp / rate
        ud['charge_amount_syp'] = amount_syp
        ud['charge_usd_amount'] = usd_amount
        ud['awaiting_charge_amount'] = False
        ud['awaiting_charge_proof'] = True
        await update.message.reply_text(
            f"💳 المبلغ: {amount_syp:,.0f} ل.س = {usd_amount:.2f}$\n\n"
            f"📤 حوّل عبر {SYRIA_CASH_NAME} إلى الرقم:\n`{SYRIA_CASH_NUMBER}`\n\n"
            f"📸 ثم أرسل صورة الوصل، أو اكتب رقم/مرجع العملية هنا:",
            parse_mode='Markdown', reply_markup=CANCEL_BTN
        )
        return

    if ud.get('awaiting_charge_proof') and not update.message.photo:
        amount_syp = ud.get('charge_amount_syp')
        usd_amount = ud.get('charge_usd_amount')
        if amount_syp is None:
            await update.message.reply_text("⚠️ لم يتم تحديد المبلغ، ابدأ من جديد من زر 💳 شحن الرصيد.")
            ud['awaiting_charge_proof'] = False
            return
        order_id = generate_order_id()
        db['pending_orders'][order_id] = {
            "type": "charge", "user_id": user_id, "usd_amount": usd_amount,
            "syp_amount": amount_syp, "ref": text
        }
        save_db(db)
        name = safe_md(update.effective_user.first_name)
        await context.bot.send_message(
            ADMIN_CHANNEL_ID,
            f"🏦 طلب شحن رصيد (برقم العملية)\n━━━━━━━━━━━━━━━━━━━━\n📋 رقم الطلب: {order_id}\n"
            f"👤 {name}\n🆔 {user_id}\n💰 {amount_syp:,.0f} ل.س = {usd_amount:.2f}$\n🧾 المرجع: {safe_md(text)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ قبول وإضافة الرصيد", callback_data=f"charge_ok#{order_id}")],
                [InlineKeyboardButton("❌ رفض", callback_data=f"charge_no#{order_id}")]
            ])
        )
        ud['awaiting_charge_proof'] = False
        await update.message.reply_text(f"🚀 تم إرسال طلب الشحن (رقم {order_id}) للإدارة، بانتظار الموافقة.\nℹ️ يمكنك أيضاً إرسال صورة الوصل بدل الكتابة.")
        return

    # ---------- استرجاع الأموال ----------
    if ud.get('awaiting_refund_amount'):
        try:
            amount = float(text)
            if amount <= 0:
                raise ValueError
        except Exception:
            await update.message.reply_text("❌ اكتب رقماً صحيحاً بالدولار.", reply_markup=CANCEL_BTN)
            return
        balance = get_balance(db, user_id)
        if balance < amount:
            await update.message.reply_text(f"❌ رصيدك ({balance:.2f}$) أقل من المبلغ المطلوب استرجاعه!")
            ud['awaiting_refund_amount'] = False
            return
        ud['refund_amount'] = amount
        ud['awaiting_refund_amount'] = False
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تأكيد طلب الاسترجاع", callback_data="confirm_refund")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_flow")]
        ])
        await update.message.reply_text(f"💰 المبلغ المطلوب استرجاعه: {amount:.2f}$\nهل تريد تأكيد الطلب؟", reply_markup=btn)
        return

    # ---------- شراء منتج (تأكيد) ----------
    if ud.get('awaiting_purchase_confirm_text'):
        # لا يُستخدم حالياً - الشراء يتم بالكامل عبر الأزرار
        pass

    # ================= تدفقات الأدمن (نصية) =================
    if ud.get('awaiting_broadcast'):
        ud['awaiting_broadcast'] = False
        await update.message.reply_text("🚀 جاري الإرسال...")
        count = 0
        for uid in db["users"]:
            try:
                await context.bot.send_message(uid, f"📢 إعلان عام\n━━━━━━━━━━━━━━━━━━━━\n{text}")
                count += 1
            except Exception:
                pass
        await update.message.reply_text(f"✅ تم إرسال الإعلان إلى {count} مستخدم.")
        return

    if ud.get('awaiting_add_balance'):
        try:
            parts = text.split('|')
            target_id, amount = parts[0].strip(), float(parts[1].strip())
            if amount <= 0 or target_id not in db["users"]:
                raise ValueError
            update_balance(db, target_id, amount)
            log_activity(db, f"إضافة يدوية {amount}$ لـ {target_id}")
            save_db(db)
            await update.message.reply_text(f"✅ تم إضافة {amount}$ إلى {db['users'][target_id]['name']}")
            await context.bot.send_message(target_id, f"🎉 تم إضافة {amount}$ إلى محفظتك!")
        except Exception:
            await update.message.reply_text("❌ الصيغة غير صحيحة! استخدم: `آيدي|المبلغ`", parse_mode='Markdown', reply_markup=CANCEL_BTN)
            return
        ud['awaiting_add_balance'] = False
        return

    if ud.get('awaiting_sub_balance'):
        try:
            parts = text.split('|')
            target_id, amount = parts[0].strip(), float(parts[1].strip())
            if amount <= 0 or target_id not in db["users"]:
                raise ValueError
            update_balance(db, target_id, -amount)
            log_activity(db, f"خصم يدوي {amount}$ من {target_id}")
            save_db(db)
            await update.message.reply_text(f"✅ تم خصم {amount}$ من {db['users'][target_id]['name']}")
            await context.bot.send_message(target_id, f"⚠️ تم خصم {amount}$ من محفظتك من قبل الإدارة.")
        except Exception:
            await update.message.reply_text("❌ الصيغة غير صحيحة! استخدم: `آيدي|المبلغ`", parse_mode='Markdown', reply_markup=CANCEL_BTN)
            return
        ud['awaiting_sub_balance'] = False
        return

    if ud.get('awaiting_ban_user'):
        target_id = text.strip()
        if target_id not in db["users"]:
            await update.message.reply_text("❌ لا يوجد مستخدم بهذا المعرف.", reply_markup=CANCEL_BTN)
            return
        db.setdefault("banned", {})[target_id] = True
        log_activity(db, f"حظر {target_id}")
        save_db(db)
        await update.message.reply_text(f"🚫 تم حظر {target_id}")
        ud['awaiting_ban_user'] = False
        return

    if ud.get('awaiting_unban_user'):
        target_id = text.strip()
        db.setdefault("banned", {}).pop(target_id, None)
        log_activity(db, f"رفع الحظر عن {target_id}")
        save_db(db)
        await update.message.reply_text(f"✅ تم رفع الحظر عن {target_id}")
        ud['awaiting_unban_user'] = False
        return

    if ud.get('awaiting_search_user'):
        target = text.strip()
        info = db['users'].get(target)
        ud['awaiting_search_user'] = False
        if not info:
            await update.message.reply_text("❌ لا يوجد مستخدم بهذا المعرف.")
            return
        await update.message.reply_text(
            f"🔎 بيانات المستخدم\n🆔 {target}\n👤 {safe_md(info.get('name'))}\n💰 {info.get('balance_usd',0):.2f}$\n"
            f"🚫 محظور: {'نعم' if target in db.get('banned',{}) else 'لا'}"
        )
        return

    if ud.get('awaiting_new_rate'):
        try:
            r = float(text)
            if r <= 0:
                raise ValueError
            db['exchange_rate'] = r
            save_db(db)
            await update.message.reply_text(f"✅ تم تعديل سعر الصرف إلى {r:,} ل.س")
        except Exception:
            await update.message.reply_text("❌ اكتب رقماً صحيحاً!", reply_markup=CANCEL_BTN)
            return
        ud['awaiting_new_rate'] = False
        return

    if ud.get('awaiting_add_category'):
        try:
            parts = text.split('|')
            parent_raw, section, name = parts[0].strip(), parts[1].strip(), parts[2].strip()
            parent = None if parent_raw.lower() == 'root' else parent_raw
            if section not in db['catalog_roots'] or (parent and parent not in db['catalog']):
                raise ValueError
            nid = new_node_id(db, "x")
            db['catalog'][nid] = {"name": f"📁 {name}", "section": section, "parent": parent,
                                   "type": "folder", "price": None, "description": "",
                                   "active": True, "deleted": False, "children": []}
            if parent:
                db['catalog'][parent]['children'].append(nid)
            else:
                db['catalog_roots'][section].append(nid)
            save_db(db)
            await update.message.reply_text(f"✅ تم إضافة القسم [{name}] بمعرف {nid}")
        except Exception:
            await update.message.reply_text(
                "❌ الصيغة غير صحيحة! استخدم:\n`parent_id_أو_root|whatsapp_أو_telegram|الاسم`\nمثال: `root|whatsapp|أرقام مصر`",
                parse_mode='Markdown', reply_markup=CANCEL_BTN)
            return
        ud['awaiting_add_category'] = False
        return

    if ud.get('awaiting_add_product'):
        try:
            parts = text.split('|')
            parent, name, price, desc = parts[0].strip(), parts[1].strip(), float(parts[2].strip()), (parts[3].strip() if len(parts) > 3 else "")
            if parent not in db['catalog'] or price <= 0:
                raise ValueError
            nid = new_node_id(db, "x")
            db['catalog'][nid] = {"name": f"🎯 {name} ~ {price}$", "section": db['catalog'][parent]['section'],
                                   "parent": parent, "type": "product", "price": price, "description": desc,
                                   "active": True, "deleted": False, "children": []}
            db['catalog'][parent]['children'].append(nid)
            save_db(db)
            await update.message.reply_text(f"✅ تم إضافة المنتج [{name}] بمعرف {nid}")
        except Exception:
            await update.message.reply_text(
                "❌ الصيغة غير صحيحة! استخدم:\n`parent_id|الاسم|السعر|الوصف(اختياري)`\nمثال: `x101|رقم مصر واتساب|1.5|رقم مصري جاهز للتفعيل`",
                parse_mode='Markdown', reply_markup=CANCEL_BTN)
            return
        ud['awaiting_add_product'] = False
        return

    if ud.get('awaiting_edit_price'):
        try:
            parts = text.split('|')
            nid, price = parts[0].strip(), float(parts[1].strip())
            node = db['catalog'][nid]
            node['price'] = price
            node['active'] = True
            base_name = node['name'].split(' ~ ')[0]
            node['name'] = base_name + f" ~ {price}$"
            save_db(db)
            await update.message.reply_text(f"✅ تم تعديل سعر {nid} إلى {price}$ وتفعيله.")
        except Exception:
            await update.message.reply_text("❌ الصيغة غير صحيحة! استخدم: `node_id|السعر_الجديد`", parse_mode='Markdown', reply_markup=CANCEL_BTN)
            return
        ud['awaiting_edit_price'] = False
        return

    if ud.get('awaiting_edit_desc'):
        try:
            nid, desc = text.split('|', 1)
            nid = nid.strip()
            node = db['catalog'][nid]
            node['description'] = desc.strip()
            save_db(db)
            await update.message.reply_text(f"✅ تم تعديل وصف {nid}.")
        except Exception:
            await update.message.reply_text("❌ الصيغة غير صحيحة! استخدم: `node_id|الوصف الجديد`", parse_mode='Markdown', reply_markup=CANCEL_BTN)
            return
        ud['awaiting_edit_desc'] = False
        return

    if ud.get('awaiting_toggle'):
        nid = text.strip()
        node = db['catalog'].get(nid)
        if not node:
            await update.message.reply_text("❌ لا يوجد عنصر بهذا المعرف.", reply_markup=CANCEL_BTN)
            return
        node['active'] = not node.get('active', True)
        save_db(db)
        await update.message.reply_text(f"✅ الحالة الآن: {'مفعّل' if node['active'] else 'معطّل'} لـ {nid}")
        ud['awaiting_toggle'] = False
        return

    if ud.get('awaiting_delete_node'):
        nid = text.strip()
        node = db['catalog'].get(nid)
        if not node:
            await update.message.reply_text("❌ لا يوجد عنصر بهذا المعرف.", reply_markup=CANCEL_BTN)
            return
        node['deleted'] = True
        save_db(db)
        await update.message.reply_text(f"🗑️ تم حذف {nid} (قابل للاسترجاع).")
        ud['awaiting_delete_node'] = False
        return

    if ud.get('awaiting_restore_node'):
        nid = text.strip()
        node = db['catalog'].get(nid)
        if not node:
            await update.message.reply_text("❌ لا يوجد عنصر بهذا المعرف.", reply_markup=CANCEL_BTN)
            return
        node['deleted'] = False
        save_db(db)
        await update.message.reply_text(f"♻️ تم استرجاع {nid}.")
        ud['awaiting_restore_node'] = False
        return

    if ud.get('awaiting_admin_notes'):
        db['admin_notes'] = text
        save_db(db)
        ud['awaiting_admin_notes'] = False
        await update.message.reply_text("✅ تم تحديث ملاحظات الإدارة.")
        return

    # ---------- تسليم المنتج ----------
    if ud.get('awaiting_delivery_code'):
        order_id = ud.get('delivery_order_id')
        order = db['pending_orders'].get(order_id)
        ud['awaiting_delivery_code'] = False
        if not order:
            await update.message.reply_text("❌ الطلب غير موجود أو تم تسليمه مسبقاً.")
            return
        target_id = order['user_id']
        try:
            await context.bot.send_message(
                target_id,
                f"✅ تم تفعيل طلبك!\n━━━━━━━━━━━━━━━━━━━━\n🎁 المنتج: {order.get('item_name','')}\n"
                f"📋 رقم الطلب: {order_id}\n\n🎟️ التفاصيل:\n{text}"
            )
            await update.message.reply_text(f"✅ تم تسليم الطلب (رقم {order_id}) للزبون بنجاح.")
            db['stats']['purchases'] += 1
            log_activity(db, f"تسليم طلب #{order_id} لـ {target_id}")
            del db['pending_orders'][order_id]
            save_db(db)
        except Exception as e:
            await update.message.reply_text(f"❌ فشل الإرسال للزبون: {e}\nحاول مجدداً.")
            ud['awaiting_delivery_code'] = True
            ud['delivery_order_id'] = order_id
        return

    await update.message.reply_text("⚠️ لم أفهم طلبك، استخدم الأزرار من القائمة.", reply_markup=CANCEL_BTN)


# ===================== معالج الصور =====================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return
    user_id = str(update.effective_user.id)
    db = load_db()
    ud = context.user_data

    if ud.get('awaiting_charge_proof'):
        amount_syp = ud.get('charge_amount_syp')
        usd_amount = ud.get('charge_usd_amount')
        if amount_syp is None:
            await update.message.reply_text("⚠️ لم يتم تحديد المبلغ، ابدأ من جديد من زر 💳 شحن الرصيد.")
            ud['awaiting_charge_proof'] = False
            return
        order_id = generate_order_id()
        db['pending_orders'][order_id] = {
            "type": "charge", "user_id": user_id, "usd_amount": usd_amount, "syp_amount": amount_syp
        }
        save_db(db)
        photo_id = update.message.photo[-1].file_id
        name = safe_md(update.effective_user.first_name)
        await context.bot.send_photo(
            ADMIN_CHANNEL_ID, photo_id,
            caption=(f"🏦 طلب شحن رصيد\n━━━━━━━━━━━━━━━━━━━━\n📋 رقم الطلب: {order_id}\n"
                     f"👤 {name}\n🆔 {user_id}\n💰 {amount_syp:,.0f} ل.س = {usd_amount:.2f}$"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ قبول وإضافة الرصيد", callback_data=f"charge_ok#{order_id}")],
                [InlineKeyboardButton("❌ رفض", callback_data=f"charge_no#{order_id}")]
            ])
        )
        ud['awaiting_charge_proof'] = False
        await update.message.reply_text(f"🚀 تم إرسال طلب الشحن (رقم {order_id}) للإدارة، بانتظار الموافقة.")
        return


# ===================== معالج الأزرار =====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = str(update.effective_user.id)
    db = load_db()
    ud = context.user_data

    if data == "noop":
        return

    if data == "cancel_flow":
        clear_awaiting(ud)
        await query.edit_message_text("✅ تم إلغاء العملية.")
        return

    if data == "open_panel":
        if not is_admin(db, user_id):
            await query.edit_message_text("❌ ليس لديك صلاحية.")
            return
        await query.edit_message_text("🛸 لوحة التحكم الإدارية", reply_markup=get_admin_panel())
        return

    if data == "main_menu":
        await context.bot.send_message(chat_id=update.effective_chat.id, text="🎯 القائمة الرئيسية", reply_markup=main_menu)
        return

    # ---------- قسم الأرقام ----------
    if data.startswith("root#"):
        parts = data.split('#')
        section, page = parts[1], int(parts[2]) if len(parts) > 2 else 0
        roots = db['catalog_roots'].get(section, [])
        title = "📱 أرقام واتساب:" if section == "whatsapp" else "📱 أرقام تيليجرام:"
        await query.edit_message_text(title, reply_markup=render_listing(db, roots, "numbers_back", f"root#{section}", page))
        return

    if data == "numbers_back":
        await query.edit_message_text("📱 اختر القسم:", reply_markup=numbers_menu)
        return

    if data.startswith("nav#"):
        parts = data.split('#')
        nid, page = parts[1], int(parts[2]) if len(parts) > 2 else 0
        node = db['catalog'].get(nid)
        if not node:
            await query.edit_message_text("⚠️ هذا القسم غير موجود.")
            return
        await query.edit_message_text(f"📁 {node['name']}", reply_markup=render_listing(db, node['children'], back_cb_for(node), f"nav#{nid}", page))
        return

    if data.startswith("view#"):
        nid = data.split('#')[1]
        node = db['catalog'].get(nid)
        if not node or node.get('deleted') or not node.get('active', True):
            await query.edit_message_text("⚠️ هذا المنتج غير متوفر حالياً.")
            return
        desc = node.get('description') or "لا يوجد وصف إضافي."
        msg = f"{node['name']}\n\n📝 الوصف:\n{desc}\n\n💰 السعر: {node['price']}$"
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تأكيد الشراء", callback_data=f"confirm_buy#{nid}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data=back_cb_for(node))]
        ])
        await query.edit_message_text(msg, reply_markup=btn)
        return

    if data.startswith("confirm_buy#"):
        nid = data.split('#')[1]
        node = db['catalog'].get(nid)
        if not node or node.get('deleted') or not node.get('active', True):
            await query.edit_message_text("⚠️ هذا المنتج غير متوفر.")
            return
        balance = get_balance(db, user_id)
        if balance < node['price']:
            await query.edit_message_text(f"❌ رصيدك ({balance:.2f}$) لا يكفي لشراء هذا المنتج!")
            return
        order_id = generate_order_id()
        db['pending_orders'][order_id] = {
            "type": "purchase", "user_id": user_id, "node_id": nid,
            "price": node['price'], "item_name": node['name']
        }
        save_db(db)
        name = safe_md(update.effective_user.first_name)
        await context.bot.send_message(
            ADMIN_CHANNEL_ID,
            f"🛒 طلب شراء جديد\n━━━━━━━━━━━━━━━━━━━━\n📋 رقم الطلب: {order_id}\n"
            f"👤 {name}\n🆔 {user_id}\n🎁 {node['name']}\n💰 {node['price']}$",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ موافقة وخصم", callback_data=f"order_ok#{order_id}")],
                [InlineKeyboardButton("❌ رفض", callback_data=f"order_no#{order_id}")]
            ])
        )
        await query.edit_message_text(f"✅ تم إرسال طلبك (رقم {order_id}) للإدارة، بانتظار الموافقة.")
        return

    if data.startswith("order_ok#"):
        order_id = data.split('#')[1]
        order = db['pending_orders'].get(order_id)
        if not is_admin(db, user_id):
            await query.answer("❌ غير مصرح لك", show_alert=True)
            return
        if not order:
            await query.edit_message_text("⚠️ هذا الطلب لم يعد موجوداً.")
            return
        target_id = order['user_id']
        balance = get_balance(db, target_id)
        if balance < order['price']:
            await query.edit_message_text("❌ رصيد الزبون لم يعد كافياً!")
            return
        update_balance(db, target_id, -order['price'])
        save_db(db)
        await query.edit_message_text(f"✅ تم خصم {order['price']}$ من الزبون (رقم الطلب {order_id}).\n📩 تحقق من رسائلك الخاصة مع البوت لإدخال الرقم/الكود.")
        clear_awaiting(ud)
        ud['awaiting_delivery_code'] = True
        ud['delivery_order_id'] = order_id
        await notify_admin_dm(context, f"✍️ اكتب الآن هنا الرقم/الكود لتسليمه للزبون (طلب {order_id} — {order.get('item_name','')}):")
        return

    if data.startswith("order_no#"):
        if not is_admin(db, user_id):
            await query.answer("❌ غير مصرح لك", show_alert=True)
            return
        order_id = data.split('#')[1]
        order = db['pending_orders'].pop(order_id, None)
        save_db(db)
        await query.edit_message_text(f"❌ تم رفض الطلب (رقم {order_id})")
        if order:
            await context.bot.send_message(order['user_id'], f"❌ عذراً، تم رفض طلبك (رقم {order_id}).")
        return

    # ---------- شحن الرصيد ----------
    if data == "charge":
        clear_awaiting(ud)
        ud['awaiting_charge_amount'] = True
        await query.edit_message_text("✍️ اكتب المبلغ الذي تريد شحنه بالليرة السورية:", reply_markup=CANCEL_BTN)
        return

    if data.startswith("charge_ok#"):
        if not is_admin(db, user_id):
            await query.answer("❌ غير مصرح لك", show_alert=True)
            return
        order_id = data.split('#')[1]
        order = db['pending_orders'].pop(order_id, None)
        if not order:
            await query.edit_message_text("⚠️ هذا الطلب لم يعد موجوداً.")
            return
        update_balance(db, order['user_id'], order['usd_amount'])
        db['stats']['deposits'] += 1
        log_activity(db, f"إيداع #{order_id} لـ {order['user_id']} بقيمة {order['usd_amount']:.2f}$")
        save_db(db)
        await query.edit_message_text(f"✅ تم قبول الشحن (رقم {order_id}) وإضافة {order['usd_amount']:.2f}$")
        await context.bot.send_message(order['user_id'], f"✅ تم شحن {order['usd_amount']:.2f}$ إلى محفظتك (رقم {order_id}).")
        return

    if data.startswith("charge_no#"):
        if not is_admin(db, user_id):
            await query.answer("❌ غير مصرح لك", show_alert=True)
            return
        order_id = data.split('#')[1]
        order = db['pending_orders'].pop(order_id, None)
        save_db(db)
        await query.edit_message_text(f"❌ تم رفض طلب الشحن (رقم {order_id})")
        if order:
            await context.bot.send_message(order['user_id'], f"❌ عذراً، تم رفض طلب الشحن (رقم {order_id}). تأكد من صحة إثبات الدفع.")
        return

    # ---------- استرجاع الأموال ----------
    if data == "confirm_refund":
        amount = ud.get('refund_amount')
        if amount is None:
            await query.edit_message_text("⚠️ حدث خطأ، ابدأ من جديد من زر 💰 استرجاع الأموال.")
            return
        balance = get_balance(db, user_id)
        if balance < amount:
            await query.edit_message_text(f"❌ رصيدك ({balance:.2f}$) لم يعد كافياً!")
            return
        order_id = generate_order_id()
        db['pending_orders'][order_id] = {"type": "refund", "user_id": user_id, "amount": amount}
        save_db(db)
        name = safe_md(update.effective_user.first_name)
        await context.bot.send_message(
            ADMIN_CHANNEL_ID,
            f"💰 طلب استرجاع أموال\n━━━━━━━━━━━━━━━━━━━━\n📋 رقم الطلب: {order_id}\n"
            f"👤 {name}\n🆔 {user_id}\n💵 المبلغ: {amount:.2f}$",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ موافقة", callback_data=f"refund_ok#{order_id}")],
                [InlineKeyboardButton("❌ رفض", callback_data=f"refund_no#{order_id}")]
            ])
        )
        await query.edit_message_text(f"✅ تم إرسال طلب الاسترجاع (رقم {order_id}) للإدارة.")
        return

    if data.startswith("refund_ok#"):
        if not is_admin(db, user_id):
            await query.answer("❌ غير مصرح لك", show_alert=True)
            return
        order_id = data.split('#')[1]
        order = db['pending_orders'].pop(order_id, None)
        if not order:
            await query.edit_message_text("⚠️ هذا الطلب لم يعد موجوداً.")
            return
        update_balance(db, order['user_id'], -order['amount'])
        db['stats']['refunds'] += 1
        log_activity(db, f"استرجاع #{order_id} لـ {order['user_id']} بقيمة {order['amount']:.2f}$")
        save_db(db)
        await query.edit_message_text(f"✅ تم قبول الاسترجاع (رقم {order_id}) وخصم {order['amount']:.2f}$")
        await context.bot.send_message(order['user_id'], f"✅ تم قبول استرجاع {order['amount']:.2f}$ وسيتم تحويلها لك قريباً (رقم {order_id}).")
        return

    if data.startswith("refund_no#"):
        if not is_admin(db, user_id):
            await query.answer("❌ غير مصرح لك", show_alert=True)
            return
        order_id = data.split('#')[1]
        order = db['pending_orders'].pop(order_id, None)
        save_db(db)
        await query.edit_message_text(f"❌ تم رفض طلب الاسترجاع (رقم {order_id})")
        if order:
            await context.bot.send_message(order['user_id'], f"❌ عذراً، تم رفض طلب استرجاع الأموال (رقم {order_id}).")
        return

    # ---------- الدعم ----------
    if data == "support#start":
        clear_awaiting(ud)
        ud['awaiting_complaint'] = True
        await query.edit_message_text("📝 اكتب شكواك أو استفسارك الآن بالتفصيل:", reply_markup=CANCEL_BTN)
        return

    if data.startswith("reply_user#"):
        if not is_admin(db, user_id):
            await query.answer("❌ غير مصرح لك", show_alert=True)
            return
        target_id = data.split('#')[1]
        clear_awaiting(ud)
        ud['awaiting_reply_to_user'] = True
        ud['reply_target_id'] = target_id
        await notify_admin_dm(context, f"✍️ اكتب الآن هنا ردك على المستخدم {target_id}:")
        await query.answer("📩 تحقق من رسائلك الخاصة مع البوت لكتابة الرد", show_alert=True)
        return

    # ---------- لوحة التحكم ----------
    if data.startswith("adm#"):
        if not is_admin(db, user_id):
            await query.edit_message_text("❌ غير مصرح لك. استخدم /admin وأدخل كلمة السر.")
            return
        action = data.split('#')[1]

        if action == "stats":
            total_users = len(db["users"])
            total_balance = sum(u.get("balance_usd", 0) for u in db["users"].values())
            total_orders = len(db.get("pending_orders", {}))
            s = db.get("stats", {})
            await query.edit_message_text(
                f"📊 الإحصائيات الشاملة\n━━━━━━━━━━━━━━━━━━━━\n👥 المستخدمين: {total_users}\n"
                f"💰 إجمالي الأرصدة: {total_balance:.2f}$\n📦 الطلبات المعلقة الآن: {total_orders}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n🛒 عمليات شراء: {s.get('purchases',0)}\n"
                f"💸 عمليات استرجاع: {s.get('refunds',0)}\n💳 عمليات إيداع: {s.get('deposits',0)}\n"
                f"📩 شكاوى: {s.get('complaints',0)}"
            )
            return

        if action == "log":
            log = db.get("activity_log", [])[-15:]
            txt = "📋 آخر العمليات\n━━━━━━━━━━━━━━━━━━━━\n" + ("\n".join(log) if log else "لا يوجد سجل بعد.")
            await query.edit_message_text(txt)
            return

        if action == "pending_list":
            orders = db.get("pending_orders", {})
            if not orders:
                await query.edit_message_text("📦 لا يوجد طلبات معلقة حالياً.")
                return
            lines = ["📦 الطلبات المعلقة\n━━━━━━━━━━━━━━━━━━━━"]
            for oid, o in list(orders.items())[:25]:
                lines.append(f"{oid} — {o.get('type')} — {o.get('user_id')}")
            await query.edit_message_text("\n".join(lines))
            return

        if action == "broadcast":
            clear_awaiting(ud)
            ud['awaiting_broadcast'] = True
            await query.edit_message_text("✍️ اكتب رسالة الإعلان:", reply_markup=CANCEL_BTN)
            return

        if action == "users":
            s = "👥 المستخدمين\n━━━━━━━━━━━━━━━━━━━━\n"
            for uid, info in list(db["users"].items())[:25]:
                s += f"{uid} — {safe_md(info.get('name','مجهول'))}\n"
            await query.edit_message_text(s or "لا يوجد مستخدمين.")
            return

        if action == "view_balances":
            s = "💰 الأرصدة\n━━━━━━━━━━━━━━━━━━━━\n"
            for uid, info in list(db["users"].items())[:25]:
                s += f"{safe_md(info.get('name','مجهول'))} — {info.get('balance_usd',0):.2f}$ ({uid})\n"
            await query.edit_message_text(s or "لا يوجد مستخدمين.")
            return

        if action == "search_user":
            clear_awaiting(ud)
            ud['awaiting_search_user'] = True
            await query.edit_message_text("✍️ اكتب آيدي المستخدم:", reply_markup=CANCEL_BTN)
            return

        if action == "add_balance":
            clear_awaiting(ud)
            ud['awaiting_add_balance'] = True
            await query.edit_message_text("✍️ اكتب: `آيدي|المبلغ`", parse_mode='Markdown', reply_markup=CANCEL_BTN)
            return

        if action == "sub_balance":
            clear_awaiting(ud)
            ud['awaiting_sub_balance'] = True
            await query.edit_message_text("✍️ اكتب: `آيدي|المبلغ` لخصمه", parse_mode='Markdown', reply_markup=CANCEL_BTN)
            return

        if action == "ban_user":
            clear_awaiting(ud)
            ud['awaiting_ban_user'] = True
            await query.edit_message_text("✍️ اكتب آيدي المستخدم لحظره:", reply_markup=CANCEL_BTN)
            return

        if action == "unban_user":
            clear_awaiting(ud)
            ud['awaiting_unban_user'] = True
            await query.edit_message_text("✍️ اكتب آيدي المستخدم لرفع الحظر عنه:", reply_markup=CANCEL_BTN)
            return

        if action == "edit_rate":
            clear_awaiting(ud)
            ud['awaiting_new_rate'] = True
            await query.edit_message_text(f"📈 سعر الصرف الحالي: {db.get('exchange_rate',13800):,} ل.س\n✍️ اكتب السعر الجديد:", reply_markup=CANCEL_BTN)
            return

        if action == "tree":
            lines = ["🗂️ شجرة المتجر الكاملة (المعرف: الاسم)\n━━━━━━━━━━━━━━━━━━━━"]
            for section, roots in db['catalog_roots'].items():
                lines.append(f"\n📦 __{section}__")

                def walk(nid, depth):
                    node = db['catalog'].get(nid)
                    if not node:
                        return
                    flag = ""
                    if node.get('deleted'):
                        flag = " 🗑️محذوف"
                    elif node['type'] == 'product' and not node.get('active', True):
                        flag = " ⛔معطّل"
                    lines.append(("  " * depth) + f"{nid} {node['name']}{flag}")
                    for c in node.get('children', []):
                        walk(c, depth + 1)

                for r in roots:
                    walk(r, 1)
            full_text = "\n".join(lines)
            if not any(db['catalog_roots'].values()):
                full_text += "\n\n(القائمة فارغة حالياً، أضف أقسام ومنتجات من الأزرار أعلاه)"
            if len(full_text) > 3800:
                full_text = full_text[:3800] + "\n...\n(القائمة طويلة)"
            await query.edit_message_text(full_text)
            return

        if action == "add_category":
            clear_awaiting(ud)
            ud['awaiting_add_category'] = True
            await query.edit_message_text(
                "✍️ اكتب بالصيغة:\n`parent_id_أو_root|whatsapp_أو_telegram|الاسم`\n\n"
                "مثال (قسم رئيسي): `root|whatsapp|أرقام مصر`\n"
                "مثال (مجلد فرعي داخل x101): `x101|whatsapp|مجلد فرعي`",
                parse_mode='Markdown', reply_markup=CANCEL_BTN)
            return

        if action == "add_product":
            clear_awaiting(ud)
            ud['awaiting_add_product'] = True
            await query.edit_message_text(
                "✍️ اكتب بالصيغة:\n`parent_id|الاسم|السعر|الوصف(اختياري)`\n\n"
                "مثال: `x101|رقم مصر واتساب|1.5|رقم مصري جديد جاهز للتفعيل الفوري`",
                parse_mode='Markdown', reply_markup=CANCEL_BTN)
            return

        if action == "edit_price":
            clear_awaiting(ud)
            ud['awaiting_edit_price'] = True
            await query.edit_message_text("✍️ اكتب بالصيغة: `node_id|السعر_الجديد`", parse_mode='Markdown', reply_markup=CANCEL_BTN)
            return

        if action == "edit_desc":
            clear_awaiting(ud)
            ud['awaiting_edit_desc'] = True
            await query.edit_message_text("✍️ اكتب بالصيغة: `node_id|الوصف الجديد`", parse_mode='Markdown', reply_markup=CANCEL_BTN)
            return

        if action == "toggle":
            clear_awaiting(ud)
            ud['awaiting_toggle'] = True
            await query.edit_message_text("✍️ اكتب معرف العنصر (node_id) لتبديل حالته تفعيل/تعطيل:", reply_markup=CANCEL_BTN)
            return

        if action == "delete_node":
            clear_awaiting(ud)
            ud['awaiting_delete_node'] = True
            await query.edit_message_text("✍️ اكتب معرف العنصر (node_id) لحذفه (قابل للاسترجاع):", reply_markup=CANCEL_BTN)
            return

        if action == "restore_node":
            clear_awaiting(ud)
            ud['awaiting_restore_node'] = True
            await query.edit_message_text("✍️ اكتب معرف العنصر (node_id) لاسترجاعه:", reply_markup=CANCEL_BTN)
            return

        if action == "clean":
            db["pending_orders"] = {}
            save_db(db)
            await query.edit_message_text("🧹 تم تنظيف كل الطلبات المعلقة.")
            return

        if action == "toggle_maintenance":
            db['bot_maintenance'] = not db.get('bot_maintenance', False)
            save_db(db)
            state = "مفعّل 🛠️" if db['bot_maintenance'] else "متوقف ✅"
            await query.edit_message_text(f"وضع الصيانة الآن: {state}")
            return

        if action == "admin_notes":
            clear_awaiting(ud)
            ud['awaiting_admin_notes'] = True
            current = safe_md(db.get('admin_notes', '')) or 'لا توجد ملاحظات بعد.'
            await query.edit_message_text(f"📝 الملاحظات الحالية:\n{current}\n\n✍️ اكتب ملاحظات جديدة لتحديثها:", reply_markup=CANCEL_BTN)
            return

        if action == "backup":
            backup_data = json.dumps(db, indent=2, ensure_ascii=False)
            await query.edit_message_text("💾 تم إنشاء نسخة احتياطية.")
            await context.bot.send_document(
                chat_id=user_id,
                document=BufferedInputFile(backup_data.encode('utf-8'), filename='database_backup.json'),
                caption="📂 نسخة احتياطية")
            return

        return

    await query.edit_message_text("⚠️ هذا الزر غير مفعل حالياً.")


# ===================== تشغيل البوت =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("panel", panel_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_photo))
    print("🚀 البوت شغال!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

