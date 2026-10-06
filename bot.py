# -*- coding: utf-8 -*-
import os, json, io
from datetime import datetime
from telegram import (Update, ReplyKeyboardMarkup, KeyboardButton,
                      InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)
from dotenv import load_dotenv
import gh_store

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/KomInvest_Crimea")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@KomInvest_Crimea")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL", "")
PORT = int(os.getenv("PORT", "8080"))
LEADS_FILE = "leads.json"
ADMINS_FILE = "admins.json"

user_states = {}

# ---------- Хранилище ----------

def load_leads():
    return gh_store.read_local("leads.json", [])

def save_lead(lead):
    leads = load_leads()
    leads.append(lead)
    gh_store.push("leads.json", leads)

def load_admins():
    return gh_store.read_local("admins.json", {"super": [ADMIN_ID], "admins": []})

def save_admins(data):
    gh_store.push("admins.json", data)

def is_super(uid):
    return uid in load_admins().get("super", [])

def is_admin_uid(uid):
    d = load_admins()
    return uid in d.get("super", []) or uid in d.get("admins", [])

# ---------- Клиентская часть ----------

def main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📝 Оставить заявку для юриста")],
         [KeyboardButton("ℹ️ О компании"), KeyboardButton("📰 Наш канал")]],
        resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_states.pop(uid, None)
    source = context.args[0] if context.args else "direct"
    context.user_data["source"] = source
    await update.message.reply_text(
        "Здравствуйте! 👋 Это бот «КомИнвест» — коммерческая недвижимость Крыма.\n\n"
        "Помогаем находить доходные объекты, проверять их юридическую чистоту "
        "и безопасно выходить на сделку.\n\n"
        "Нажмите кнопку ниже 👇",
        reply_markup=main_keyboard())

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏢 «КомИнвест» — подбор и проверка коммерческой недвижимости в Крыму.\n\n"
        "✅ Офисы, склады, стрит-ритейл, земельные участки\n"
        "✅ Юридическая проверка объекта перед покупкой\n"
        "✅ Сопровождение сделки «под ключ»\n\n"
        "Больше полезного — в нашем канале: " + CHANNEL_URL,
        reply_markup=main_keyboard())

async def channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 Подписывайтесь на наш канал:\n" + CHANNEL_URL,
                                    reply_markup=main_keyboard())

async def lead_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_states[uid] = "name"
    await update.message.reply_text("Отлично! 🙌\nКак к вам обращаться?",
                                    reply_markup=main_keyboard())

async def finish_lead(update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str):
    uid = update.effective_user.id
    name = context.user_data.get("name", "Без имени")
    lead = {
        "id": len(load_leads()) + 1,
        "name": name,
        "phone": phone,
        "source": context.user_data.get("source", "direct"),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "новая"
    }
    save_lead(lead)
    user_states.pop(uid, None)
    context.user_data.pop("name", None)
    await update.message.reply_text(
        f"Спасибо, {name}! ✅\n\nВаша заявка принята. Юрист свяжется с вами "
        "в ближайшее время.\n\nА пока — загляните в наш канал, там каждый день "
        "разборы объектов и новости рынка:\n" + CHANNEL_URL,
        reply_markup=main_keyboard())
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🔥 НОВАЯ ЗАЯВКА #{lead['id']}\n\n"
            f"👤 {name}\n📞 {phone}\n📍 Источник: {lead['source']}\n\n"
            f"/admin — админка | /export — выгрузка в Excel")
    except Exception as e:
        print(f"Не удалось уведомить админа: {e}")

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await finish_lead(update, context, update.message.contact.phone_number)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    state = user_states.get(uid)

    # --- Служебные состояния супер-админа ---
    if state in ("add_admin", "del_admin") and is_super(uid):
        try:
            if text.startswith("@"):
                target = (await context.bot.get_chat(text)).id
            else:
                target = int(text)
        except Exception:
            await update.message.reply_text(
                "Не распознал. Пришли числовой ID или @username.",
                reply_markup=main_keyboard())
            return
        d = load_admins()
        if state == "add_admin":
            if target not in d["admins"] and target not in d["super"]:
                d["admins"].append(target)
                save_admins(d)
                msg = f"✅ Админ добавлен: {target}"
            else:
                msg = "Этот человек уже админ."
        else:
            if target in d["admins"]:
                d["admins"].remove(target)
                save_admins(d)
                msg = f"🗑 Админ снят: {target}"
            else:
                msg = "Этого человека нет в админах."
        user_states.pop(uid, None)
        await update.message.reply_text(msg, reply_markup=admin_menu(uid))
        return

    # --- Кнопки клиента ---
    if text in ("📝 Оставить заявку", "📝 Оставить заявку для юриста"):
        return await lead_start(update, context)
    if text == "ℹ️ О компании":
        return await about(update, context)
    if text == "📰 Наш канал":
        return await channel(update, context)

    # --- Воронка лида ---
    if state == "name":
        context.user_data["name"] = text
        user_states[uid] = "phone"
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Отправить мой номер", request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            f"Приятно познакомиться, {text}! 😊\n\n"
            "Теперь отправьте ваш телефон — нажмите кнопку ниже или напишите "
            "номер в формате +79991234567",
            reply_markup=kb)
    elif state == "phone":
        await finish_lead(update, context, text)
    else:
        await update.message.reply_text(
            "Я пока понимаю только кнопки 😅\nНажмите «📝 Оставить заявку для юриста», "
            "чтобы связаться с юристом.",
            reply_markup=main_keyboard())

# ---------- Админка ----------

def admin_menu(uid):
    rows = [
        [InlineKeyboardButton("📋 Лиды", callback_data="adm_leads")],
        [InlineKeyboardButton("📥 Экспорт в Excel", callback_data="adm_export")],
        [InlineKeyboardButton("🏢 Объекты", callback_data="adm_objects")],
    ]
    if is_super(uid):
        rows.append([InlineKeyboardButton("👥 Админы", callback_data="adm_admins")])
    return InlineKeyboardMarkup(rows)

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin_uid(uid):
        await update.message.reply_text(
            "Этот раздел доступен только администраторам КомИнвест.",
            reply_markup=main_keyboard())
        return
    await update.message.reply_text("🛠 Админ-панель КомИнвест:", reply_markup=admin_menu(uid))

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if not is_admin_uid(uid):
        await q.edit_message_text("❌ Недоступно.")
        return
    data = q.data

    if data == "adm_leads":
        leads = load_leads()
        if not leads:
            text = "📋 Заявок пока нет."
        else:
            lines = [f"📋 Заявки: всего {len(leads)}", ""]
            for l in leads[-15:]:
                lines.append(f"#{l['id']} | {l['name']} | {l['phone']} | {l['source']} | {l['date']}")
            text = "\n".join(lines)
        await q.edit_message_text(text, reply_markup=admin_menu(uid))

    elif data == "adm_export":
        import openpyxl
        from openpyxl.styles import Font
        leads = load_leads()
        if not leads:
            await q.edit_message_text("Экспортировать нечего — заявок нет.", reply_markup=admin_menu(uid))
            return
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Заявки"
        ws.append(["№", "Имя", "Телефон", "Источник", "Дата", "Статус"])
        for cell in ws[1]: cell.font = Font(bold=True)
        for l in leads:
            ws.append([l["id"], l["name"], l["phone"], l["source"], l["date"], l["status"]])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        await q.message.reply_document(
            document=buf,
            filename=f"kominvest_leads_{datetime.now().strftime('%d%m%Y')}.xlsx",
            caption=f"📥 Выгрузка заявок: {len(leads)} шт.")
        await q.edit_message_text("✅ Файл отправлен выше.", reply_markup=admin_menu(uid))

    elif data == "adm_objects":
        await q.edit_message_text(
            "🏢 Объекты: модуль каталога появится в следующем обновлении "
            "(сейчас подключаем надёжное хранилище).",
            reply_markup=admin_menu(uid))

    elif data == "adm_admins":
        if not is_super(uid):
            await q.edit_message_text("❌ Только для супер-админа.")
            return
        d = load_admins()
        text = ("👥 Состав админки:\n\n"
                f"👑 Супер: {', '.join(map(str, d['super'])) or '-'}\n"
                f"🛡 Админы: {', '.join(map(str, d['admins'])) or '-'}")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить админа", callback_data="adm_add_admin")],
            [InlineKeyboardButton("➖ Снять админа", callback_data="adm_del_admin")],
            [InlineKeyboardButton("⬅️ В меню", callback_data="adm_back")],
        ])
        await q.edit_message_text(text, reply_markup=kb)

    elif data == "adm_add_admin":
        user_states[uid] = "add_admin"
        await q.edit_message_text("Пришли Telegram ID или @username нового админа:")

    elif data == "adm_del_admin":
        user_states[uid] = "del_admin"
        await q.edit_message_text("Пришли Telegram ID или @username админа, которого снять:")

    elif data == "adm_back":
        await q.edit_message_text("🛠 Админ-панель КомИнвест:", reply_markup=admin_menu(uid))

async def leads_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_uid(update.effective_user.id): return
    leads = load_leads()
    if not leads:
        await update.message.reply_text("📋 Заявок пока нет.")
        return
    lines = [f"📋 Заявки: всего {len(leads)}\n"]
    for l in leads[-15:]:
        lines.append(f"#{l['id']} | {l['name']} | {l['phone']} | {l['source']} | {l['date']}")
    await update.message.reply_text("\n".join(lines))

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_uid(update.effective_user.id): return
    leads = load_leads()
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = sum(1 for l in leads if l["date"].startswith(today))
    await update.message.reply_text(
        f"📊 Статистика КомИнвест:\n\nВсего заявок: {len(leads)}\nСегодня: {today_count}")

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_uid(update.effective_user.id): return
    import openpyxl
    from openpyxl.styles import Font
    leads = load_leads()
    if not leads:
        await update.message.reply_text("Экспортировать нечего — заявок нет.")
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Заявки"
    ws.append(["№", "Имя", "Телефон", "Источник", "Дата", "Статус"])
    for cell in ws[1]: cell.font = Font(bold=True)
    for l in leads:
        ws.append([l["id"], l["name"], l["phone"], l["source"], l["date"], l["status"]])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    await update.message.reply_document(
        document=buf,
        filename=f"kominvest_leads_{datetime.now().strftime('%d%m%Y')}.xlsx",
        caption=f"📥 Выгрузка заявок КомИнвест: {len(leads)} шт.")

# ---------- Запуск ----------

if __name__ == "__main__":
    import asyncio
    from aiohttp import web

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("leads", leads_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_URL:
        async def webhook_handler(request):
            try:
                data = await request.json()
            except Exception:
                return web.Response(status=400, text="bad json")
            upd = Update.de_json(data, app.bot)
            if upd is not None:
                await app.update_queue.put(upd)
            return web.Response(text="OK")

        async def health_handler(request):
            return web.Response(text="OK")

        async def main():
            gh_store.sync_all({"leads.json": [], "objects.json": [], "admins.json": {"super": [ADMIN_ID], "admins": []}})
            await app.initialize()
            await app.start()
            try:
                await app.bot.set_webhook(WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
                print(f"Webhook зарегистрирован: {WEBHOOK_URL}")
            except Exception as e:
                print(f"Не удалось зарегистрировать webhook: {e}")
            web_app = web.Application()
            web_app.router.add_post("/", webhook_handler)
            web_app.router.add_get("/", health_handler)
            runner = web.AppRunner(web_app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", PORT)
            await site.start()
            print(f"Webhook mode. URL: {WEBHOOK_URL} (GET / = 200 OK)")
            await asyncio.Event().wait()

        print("Запускаю webhook-сервер...")
        asyncio.run(main())
    else:
        print("Polling mode (локально)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)