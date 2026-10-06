# -*- coding: utf-8 -*-
import os, json, io, asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          ContextTypes, filters)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/KomInvest_Crimea")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL", "")
PORT = int(os.getenv("PORT", "8080"))
LEADS_FILE = "leads.json"

user_states = {}

def load_leads():
    if not os.path.exists(LEADS_FILE): return []
    try:
        with open(LEADS_FILE, encoding="utf-8") as f: return json.load(f)
    except Exception: return []

def save_lead(lead):
    leads = load_leads()
    leads.append(lead)
    with open(LEADS_FILE, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)

def main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📝 Оставить заявку")],
         [KeyboardButton("ℹ️ О компании"), KeyboardButton("📰 Наш канал")]],
        resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_states.pop(uid, None)
    source = context.args[0] if context.args else "direct"
    context.user_data["source"] = source
    print(f"Новый пользователь: {uid}, источник: {source}")
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
        "Больше полезного — в нашем канале: " + CHANNEL_URL)

async def channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 Подписывайтесь на наш канал:\n" + CHANNEL_URL)

async def lead_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_states[uid] = "name"
    await update.message.reply_text("Отлично! 🙌\nКак к вам обращаться?")

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
            f"/leads — все заявки | /export — выгрузка в Excel")
    except Exception as e:
        print(f"Не удалось уведомить админа: {e}")

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    await finish_lead(update, context, contact.phone_number)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    state = user_states.get(uid)

    if text == "📝 Оставить заявку":
        return await lead_start(update, context)
    if text == "ℹ️ О компании":
        return await about(update, context)
    if text == "📰 Наш канал":
        return await channel(update, context)

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
            "Я пока понимаю только кнопки 😅\nНажмите «📝 Оставить заявку», "
            "чтобы связаться с юристом.",
            reply_markup=main_keyboard())

def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

async def leads_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    leads = load_leads()
    if not leads:
        await update.message.reply_text("📋 Заявок пока нет.")
        return
    lines = [f"📋 Заявки: всего {len(leads)}\n"]
    for l in leads[-15:]:
        lines.append(f"#{l['id']} | {l['name']} | {l['phone']} | {l['source']} | {l['date']}")
    lines.append("\n/export — выгрузить всё в Excel")
    await update.message.reply_text("\n".join(lines))

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    leads = load_leads()
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = sum(1 for l in leads if l["date"].startswith(today))
    await update.message.reply_text(
        f"📊 Статистика КомИнвест:\n\n"
        f"Всего заявок: {len(leads)}\n"
        f"Сегодня: {today_count}")

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    import openpyxl
    from openpyxl.styles import Font
    leads = load_leads()
    if not leads:
        await update.message.reply_text("Экспортировать нечего — заявок нет.")
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Заявки"
    headers = ["№", "Имя", "Телефон", "Источник", "Дата", "Статус"]
    ws.append(headers)
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

if __name__ == "__main__":
    import asyncio
    from aiohttp import web

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("leads", leads_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_URL:
        async def webhook_handler(request):
            try:
                data = await request.json()
            except Exception:
                return web.Response(status=400, text="bad json")
            update = Update.de_json(data, app.bot)
            if update is not None:
                await app.update_queue.put(update)
            return web.Response(text="OK")

        async def health_handler(request):
            return web.Response(text="OK")

        async def main():
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
            print(f"Webhook mode. URL: {WEBHOOK_URL} (GET / отвечает 200 OK)")
            await asyncio.Event().wait()

        print("Запускаю webhook-сервер...")
        asyncio.run(main())
    else:
        print("Polling mode (локально)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)