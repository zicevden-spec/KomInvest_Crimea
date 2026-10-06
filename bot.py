# -*- coding: utf-8 -*-
import os, json, io, traceback
from datetime import datetime
from telegram import (Update, ReplyKeyboardMarkup, KeyboardButton,
                      InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto)
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
BOT_USERNAME = ""

OBJ_TYPES = ["офис", "склад", "стрит-ритейл", "торговый центр", "земельный участок", "другое"]
EDIT_FIELDS = {"title": "Заголовок", "desc": "Описание", "price": "Цена",
               "loc": "Локация", "area": "Площадь"}

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

def load_objects():
    return gh_store.read_local("objects.json", [])

def save_objects(objs):
    gh_store.push("objects.json", objs)

def is_super(uid):
    return uid in load_admins().get("super", [])

def is_admin_uid(uid):
    d = load_admins()
    return uid in d.get("super", []) or uid in d.get("admins", [])

# ---------- Клиент ----------

def main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📝 Оставить заявку для юриста")],
         [KeyboardButton("ℹ️ О компании"), KeyboardButton("📰 Наш канал")]],
        resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_states.pop(uid, None)
    context.user_data["source"] = context.args[0] if context.args else "direct"
    await update.message.reply_text(
        "Здравствуйте! 👋 Это бот «КомИнвест» — коммерческая недвижимость Крыма.\n\n"
        "Помогаем находить доходные объекты, проверять их юридическую чистоту "
        "и безопасно выходить на сделку.\n\n"
        "Нажмите кнопку ниже 👇",
        reply_markup=keyboard_for(update.effective_user.id))

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏢 «КомИнвест» — подбор и проверка коммерческой недвижимости в Крыму.\n\n"
        "✅ Офисы, склады, стрит-ритейл, земельные участки\n"
        "✅ Юридическая проверка объекта перед покупкой\n"
        "✅ Сопровождение сделки «под ключ»\n\n"
        "Больше полезного — в нашем канале: " + CHANNEL_URL,
        reply_markup=keyboard_for(update.effective_user.id))

async def channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 Подписывайтесь на наш канал:\n" + CHANNEL_URL,
                                    reply_markup=keyboard_for(update.effective_user.id))

async def lead_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = "name"
    await update.message.reply_text("Отлично! 🙌\nКак к вам обращаться?",
                                    reply_markup=keyboard_for(update.effective_user.id))

async def finish_lead(update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str):
    uid = update.effective_user.id
    name = context.user_data.get("name", "Без имени")
    lead = {"id": len(load_leads()) + 1, "name": name, "phone": phone,
            "source": context.user_data.get("source", "direct"),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "status": "новая"}
    save_lead(lead)
    user_states.pop(uid, None)
    context.user_data.pop("name", None)
    await update.message.reply_text(
        f"Спасибо, {name}! ✅\n\nВаша заявка принята. Юрист свяжется с вами "
        "в ближайшее время.\n\nА пока — загляните в наш канал:\n" + CHANNEL_URL,
        reply_markup=keyboard_for(update.effective_user.id))
    try:
        await context.bot.send_message(ADMIN_ID,
            f"🔥 НОВАЯ ЗАЯВКА #{lead['id']}\n\n👤 {name}\n📞 {phone}\n"
            f"📍 Источник: {lead['source']}\n\n/admin — админка | /export — Excel")
    except Exception as e:
        print(f"Не удалось уведомить админа: {e}")

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await finish_lead(update, context, update.message.contact.phone_number)

# ---------- Объекты: карточка и меню ----------

def obj_card(o):
    return (f"🏢 {o['title']}\n\n{o['description']}\n\n"
            f"💰 Цена: {o['price']}\n📍 Локация: {o['location']}\n"
            f"📐 Площадь: {o.get('area', '-')}\n🏷 Тип: {o.get('type', '-')}\n"
            f"🖼 Обложка: {'есть' if o.get('cover') else 'нет'}\n"
            f"{'✅ Опубликован' if o.get('published') else '⏳ Не опубликован'}")

def obj_view_kb(oid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Опубликовать в канал", callback_data=f"obj_pub_{oid}")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"obj_edit_{oid}")],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"obj_del_{oid}")],
        [InlineKeyboardButton("⬅️ Список", callback_data="obj_list")],
    ])

def obj_edit_kb(oid):
    rows = [[InlineKeyboardButton(f"✏️ {label}", callback_data=f"oe_{f}_{oid}")]
            for f, label in EDIT_FIELDS.items()]
    rows.append([InlineKeyboardButton("🏷 Тип", callback_data=f"oe_type_{oid}")])
    rows.append([InlineKeyboardButton("🖼 Заменить обложку", callback_data=f"oe_cover_{oid}")])
    rows.append([InlineKeyboardButton("⬅️ К карточке", callback_data=f"obj_view_{oid}")])
    return InlineKeyboardMarkup(rows)

# ---------- Фото (обложка и доп. фото) ----------

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = user_states.get(uid)
    if not (isinstance(st, dict) and is_admin_uid(uid)):
        await update.message.reply_text("Сейчас не жду фото 😅", reply_markup=keyboard_for(update.effective_user.id))
        return
    step = st.get("step")
    fid = update.message.photo[-1].file_id

    if step == "obj_cover":
        st["cover"] = fid
        st["photos"] = []
        st["step"] = "obj_photos"
        await update.message.reply_text(
            "🖼 Обложка принята!\n\nТеперь пришлите дополнительные фото (до 9, по одной "
            "или альбомом) — или напишите «далее», если хватит обложки.")
    elif step == "obj_photos":
        if len(st["photos"]) >= 9:
            await update.message.reply_text("Максимум 9 доп. фото. Напишите «далее».")
            return
        st["photos"].append(fid)
        await update.message.reply_text(f"📸 Доп. фото: {len(st['photos'])}/9. Ещё или «далее».")
    elif step == "obj_edit_cover":
        objs = load_objects()
        o = next((x for x in objs if x["id"] == st["oid"]), None)
        if o:
            o["cover"] = fid
            save_objects(objs)
        user_states.pop(uid, None)
        await update.message.reply_text("✅ Обложка заменена!", reply_markup=obj_view_kb(st["oid"]))
    else:
        await update.message.reply_text("Сейчас не жду фото 😅", reply_markup=keyboard_for(update.effective_user.id))

# ---------- Текст ----------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    st = user_states.get(uid)
    step = st.get("step") if isinstance(st, dict) else st

    # --- Мастер объекта ---
    if isinstance(st, dict) and str(step).startswith("obj_") and is_admin_uid(uid):
        if step == "obj_photos":
            st["step"] = "obj_title"
            await update.message.reply_text("Теперь напишите ЗАГОЛОВОК объекта:")
            return
        if step == "obj_title":
            st["title"] = text; st["step"] = "obj_desc"
            await update.message.reply_text("📝 Описание объекта:")
            return
        if step == "obj_desc":
            st["description"] = text; st["step"] = "obj_price"
            await update.message.reply_text("💰 Цена (например: 12 500 000 ₽):")
            return
        if step == "obj_price":
            st["price"] = text; st["step"] = "obj_location"
            await update.message.reply_text("📍 Локация (город, район, улица):")
            return
        if step == "obj_location":
            st["location"] = text; st["step"] = "obj_area"
            await update.message.reply_text("📐 Площадь (например: 120 м²):")
            return
        if step == "obj_area":
            st["area"] = text; st["step"] = "obj_type"
            rows = [[InlineKeyboardButton(t, callback_data=f"ots_{i}_new")] for i, t in enumerate(OBJ_TYPES)]
            await update.message.reply_text("🏷 Выберите тип объекта:", reply_markup=InlineKeyboardMarkup(rows))
            return
        # --- Редактирование полей ---
        if step == "obj_edit":
            objs = load_objects()
            o = next((x for x in objs if x["id"] == st["oid"]), None)
            if o:
                key = {"title": "title", "desc": "description", "price": "price",
                       "loc": "location", "area": "area"}[st["field"]]
                o[key] = text
                save_objects(objs)
            user_states.pop(uid, None)
            await update.message.reply_text("✅ Сохранено! Карточка обновлена:",
                                            reply_markup=obj_view_kb(st["oid"]))
            if o:
                await update.message.reply_photo(photo=o.get("cover") or (o.get("photos") or [None])[0],
                                                 caption=obj_card(o)[:1024]) if (o.get("cover") or o.get("photos")) else None
            return

    # --- Супер-админ: админы ---
    if step in ("add_admin", "del_admin") and is_super(uid):
        try:
            target = (await context.bot.get_chat(text)).id if text.startswith("@") else int(text)
        except Exception:
            await update.message.reply_text("Не распознал. Пришли числовой ID или @username.",
                                            reply_markup=keyboard_for(update.effective_user.id))
            return
        d = load_admins()
        if step == "add_admin":
            if target not in d["admins"] and target not in d["super"]:
                d["admins"].append(target); save_admins(d); msg = f"✅ Админ добавлен: {target}"
            else: msg = "Этот человек уже админ."
        else:
            if target in d["admins"]:
                d["admins"].remove(target); save_admins(d); msg = f"🗑 Админ снят: {target}"
            else: msg = "Этого человека нет в админах."
        user_states.pop(uid, None)
        await update.message.reply_text(msg, reply_markup=admin_menu(uid))
        return

    # --- Клиент ---
    if text in ("📝 Оставить заявку", "📝 Оставить заявку для юриста"):
        return await lead_start(update, context)
    if text == "ℹ️ О компании": return await about(update, context)
    if text == "📰 Наш канал": return await channel(update, context)
    if text == "🛠 Админка":
        return await admin_cmd(update, context)

    if step == "name":
        context.user_data["name"] = text
        user_states[uid] = "phone"
        kb = ReplyKeyboardMarkup([[KeyboardButton("📱 Отправить мой номер", request_contact=True)]],
                                 resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            f"Приятно познакомиться, {text}! 😊\n\nОтправьте телефон кнопкой ниже или "
            "напишите в формате +79991234567", reply_markup=kb)
    elif step == "phone":
        await finish_lead(update, context, text)
    else:
        await update.message.reply_text(
            "Я пока понимаю только кнопки 😅\nНажмите «📝 Оставить заявку для юриста».",
            reply_markup=keyboard_for(update.effective_user.id))

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
        await update.message.reply_text("Этот раздел доступен только администраторам КомИнвест.",
                                        reply_markup=keyboard_for(update.effective_user.id))
        return
    await update.message.reply_text("🛠 Админ-панель КомИнвест:", reply_markup=admin_menu(uid))

async def publish_object(context, o):
    """Публикация в канал. Бросает исключение при ошибке."""
    link = f"https://t.me/{BOT_USERNAME}?start=lead_obj_{o['id']}" if BOT_USERNAME else CHANNEL_URL
    caption = (f"🏢 {o['title']}\n\n{o['description'][:700]}\n\n"
               f"💰 Цена: {o['price']}\n📍 {o['location']}\n"
               f"📐 {o.get('area', '-')} | 🏷 {o.get('type', '-')}\n\n"
               f"✍️ Оставить заявку: {link}")[:1024]
    media_ids = ([o["cover"]] if o.get("cover") else []) + o.get("photos", [])
    media_ids = media_ids[:10]
    if len(media_ids) > 1:
        media = [InputMediaPhoto(p) for p in media_ids]
        media[0].caption = caption
        await context.bot.send_media_group(CHANNEL_ID, media=media)
    elif len(media_ids) == 1:
        await context.bot.send_photo(CHANNEL_ID, photo=media_ids[0], caption=caption)
    else:
        await context.bot.send_message(CHANNEL_ID, text=caption)

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        await q.answer()
    except Exception:
        pass
    uid = q.from_user.id
    if not is_admin_uid(uid):
        await q.edit_message_text("❌ Недоступно.")
        return
    data = q.data

    try:
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
                await q.edit_message_text("Экспортировать нечего.", reply_markup=admin_menu(uid))
                return
            wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Заявки"
            ws.append(["№", "Имя", "Телефон", "Источник", "Дата", "Статус"])
            for cell in ws[1]: cell.font = Font(bold=True)
            for l in leads:
                ws.append([l["id"], l["name"], l["phone"], l["source"], l["date"], l["status"]])
            buf = io.BytesIO(); wb.save(buf); buf.seek(0)
            await q.message.reply_document(document=buf,
                filename=f"kominvest_leads_{datetime.now().strftime('%d%m%Y')}.xlsx",
                caption=f"📥 Выгрузка заявок: {len(leads)} шт.")
            await q.edit_message_text("✅ Файл отправлен выше.", reply_markup=admin_menu(uid))

        elif data == "adm_objects":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏢 Коммерческая недвижимость", callback_data="obj_cat_com")],
                [InlineKeyboardButton("🏠 Гражданское жильё", callback_data="obj_cat_civ")],
                [InlineKeyboardButton("⬅️ В меню", callback_data="adm_back")],
            ])
            await q.edit_message_text("🏢 Выберите категорию объектов:", reply_markup=kb)

        elif data == "obj_cat_civ":
            await q.edit_message_text("🏠 Гражданское жильё: категория откроется в следующем обновлении.",
                                      reply_markup=InlineKeyboardMarkup(
                                          [[InlineKeyboardButton("⬅️ Категории", callback_data="adm_objects")]]))

        elif data == "obj_cat_com":
            objs = [o for o in load_objects() if o.get("category") == "commercial"]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Добавить объект", callback_data="obj_add")],
                [InlineKeyboardButton(f"📋 Список объектов ({len(objs)})", callback_data="obj_list")],
                [InlineKeyboardButton("⬅️ Категории", callback_data="adm_objects")],
            ])
            await q.edit_message_text("🏢 Коммерческая недвижимость:", reply_markup=kb)

        elif data == "obj_add":
            user_states[uid] = {"step": "obj_cover"}
            await q.edit_message_text(
                "🖼 Шаг 1/7: пришлите ОБЛОЖКУ объекта — главное фото, которое увидят первым.")

        elif data == "obj_list":
            objs = [o for o in load_objects() if o.get("category") == "commercial"]
            if not objs:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Добавить первый объект", callback_data="obj_add")],
                    [InlineKeyboardButton("⬅️ Назад", callback_data="obj_cat_com")]])
                await q.edit_message_text("Объектов пока нет.", reply_markup=kb)
                return
            rows = [[InlineKeyboardButton(f"{o['id']}. {o['title'][:26]} | {o['price'][:14]}",
                      callback_data=f"obj_view_{o['id']}")] for o in objs[-12:]]
            rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="obj_cat_com")])
            await q.edit_message_text("📋 Объекты:", reply_markup=InlineKeyboardMarkup(rows))

        elif data.startswith("obj_view_"):
            oid = int(data.split("_")[-1])
            o = next((x for x in load_objects() if x["id"] == oid), None)
            if not o:
                await q.edit_message_text("Объект не найден.", reply_markup=admin_menu(uid))
                return
            pic = o.get("cover") or (o.get("photos") or [None])[0]
            if pic:
                await q.message.reply_photo(photo=pic, caption=obj_card(o)[:1024])
            else:
                await q.message.reply_text(obj_card(o))
            await q.edit_message_text(f"Карточка #{oid} — выше.", reply_markup=obj_view_kb(oid))

        elif data.startswith("obj_pub_"):
            oid = int(data.split("_")[-1])
            objs = load_objects()
            o = next((x for x in objs if x["id"] == oid), None)
            if not o:
                await q.edit_message_text("Объект не найден.", reply_markup=admin_menu(uid))
                return
            try:
                await publish_object(context, o)
                o["published"] = True
                save_objects(objs)
                await q.edit_message_text(f"✅ Объект #{oid} опубликован в канале!",
                                          reply_markup=admin_menu(uid))
            except Exception as e:
                traceback.print_exc()
                await q.edit_message_text(
                    f"❌ Ошибка публикации #{oid}: {e}\n\n(подробности в логах Render)",
                    reply_markup=obj_view_kb(oid))

        elif data.startswith("obj_del_"):
            oid = int(data.split("_")[-1])
            objs = [x for x in load_objects() if x["id"] != oid]
            save_objects(objs)
            await q.edit_message_text(f"🗑 Объект #{oid} удалён.", reply_markup=admin_menu(uid))

        elif data.startswith("obj_edit_"):
            oid = int(data.split("_")[-1])
            await q.edit_message_text(f"✏️ Редактирование объекта #{oid}. Выберите поле:",
                                      reply_markup=obj_edit_kb(oid))

        elif data.startswith("oe_cover_"):
            oid = int(data.split("_")[-1])
            user_states[uid] = {"step": "obj_edit_cover", "oid": oid}
            await q.edit_message_text("🖼 Пришлите новую обложку одним фото:")

        elif data.startswith("oe_type_"):
            oid = int(data.split("_")[-1])
            rows = [[InlineKeyboardButton(t, callback_data=f"ots_{i}_{oid}")] for i, t in enumerate(OBJ_TYPES)]
            await q.edit_message_text("🏷 Выберите новый тип:", reply_markup=InlineKeyboardMarkup(rows))

        elif data.startswith("oe_"):
            _, field, oid = data.split("_")
            user_states[uid] = {"step": "obj_edit", "oid": int(oid), "field": field}
            await q.edit_message_text(f"Пришите новое значение для поля «{EDIT_FIELDS[field]}»:")

        elif data.startswith("ots_"):
            _, idx, target = data.split("_")
            idx = int(idx)
            objs = load_objects()
            if target == "new":
                st = user_states.get(uid)
                if not (isinstance(st, dict) and st.get("step") == "obj_type"):
                    return
                st["type"] = OBJ_TYPES[idx]
                oid = max([o["id"] for o in objs], default=0) + 1
                obj = {"id": oid, "category": "commercial", "cover": st.get("cover"),
                       "photos": st.get("photos", []), "title": st["title"],
                       "description": st["description"], "price": st["price"],
                       "location": st["location"], "area": st["area"], "type": st["type"],
                       "status": "active", "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                       "published": False}
                objs.append(obj)
                save_objects(objs)
                user_states.pop(uid, None)
                await q.edit_message_text(f"✅ Объект #{oid} «{obj['title']}» сохранён!",
                                          reply_markup=obj_view_kb(oid))
            else:
                oid = int(target)
                o = next((x for x in objs if x["id"] == oid), None)
                if o:
                    o["type"] = OBJ_TYPES[idx]
                    save_objects(objs)
                user_states.pop(uid, None)
                await q.edit_message_text(f"✅ Тип обновлён: {OBJ_TYPES[idx]}",
                                          reply_markup=obj_view_kb(oid))

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

    except Exception as e:
        traceback.print_exc()
        try:
            await q.edit_message_text(f"⚠️ Ошибка: {e}", reply_markup=admin_menu(uid))
        except Exception:
            pass

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
    objs = load_objects()
    await update.message.reply_text(
        f"📊 Статистика КомИнвест:\n\nВсего заявок: {len(leads)}\n"
        f"Сегодня: {sum(1 for l in leads if l['date'].startswith(today))}\n"
        f"Объектов: {len(objs)} | Опубликовано: {sum(1 for o in objs if o.get('published'))}")

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_uid(update.effective_user.id): return
    import openpyxl
    from openpyxl.styles import Font
    leads = load_leads()
    if not leads:
        await update.message.reply_text("Экспортировать нечего.")
        return
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Заявки"
    ws.append(["№", "Имя", "Телефон", "Источник", "Дата", "Статус"])
    for cell in ws[1]: cell.font = Font(bold=True)
    for l in leads:
        ws.append([l["id"], l["name"], l["phone"], l["source"], l["date"], l["status"]])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    await update.message.reply_document(document=buf,
        filename=f"kominvest_leads_{datetime.now().strftime('%d%m%Y')}.xlsx",
        caption=f"📥 Выгрузка заявок: {len(leads)} шт.")

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
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_URL:
        async def webhook_handler(request):
            try:
                d = await request.json()
            except Exception:
                return web.Response(status=400, text="bad json")
            upd = Update.de_json(d, app.bot)
            if upd is not None:
                await app.update_queue.put(upd)
            return web.Response(text="OK")

        async def health_handler(request):
            return web.Response(text="OK")

        async def main():
            global BOT_USERNAME
            gh_store.sync_all({"leads.json": [], "objects.json": [],
                               "admins.json": {"super": [ADMIN_ID], "admins": []}})
            await app.initialize()
            await app.start()
            BOT_USERNAME = app.bot.username
            print(f"CHANNEL_ID={CHANNEL_ID} | BOT=@{BOT_USERNAME}")
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