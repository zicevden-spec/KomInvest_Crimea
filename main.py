# -*- coding: utf-8 -*-
import os
import random
import json
import requests
from dotenv import load_dotenv
from generator import get_schedule, pick_topic, generate_longread, generate_short, CONTENT_TYPES

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_URL = os.getenv("CHANNEL_URL")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")
HISTORY_FILE = "photo_history.json"
MAX_HISTORY = 30

LONG_FOOTER = f"""

━━━━━━━━━━━━━━━━━━━━
🏢 [КомИнвест | Коммерческая недвижимость]({CHANNEL_URL})

⚖️ [Консультация юриста](https://t.me/KomInvest_Crimea_bot)
📞 [Позвонить / Заказать проверку](https://t.me/KomInvest_Crimea_bot)"""

SHORT_FOOTER = f"""

🏢 [КомИнвест | Коммерческая недвижимость Крыма]({CHANNEL_URL})"""

def load_photo_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_photo_history(history):
    # Оставляем только последние MAX_HISTORY записей
    history = history[-MAX_HISTORY:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def get_pexels_image(query, history):
    if not PEXELS_KEY:
        print("⚠️ PEXELS_API_KEY не задан")
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": query, "per_page": 20, "orientation": "landscape"},
            headers={"Authorization": PEXELS_KEY},
            timeout=30
        )
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if not photos:
            # Если по запросу ничего нет — пробуем более общий
            r2 = requests.get(
                "https://api.pexels.com/v1/search",
                params={"query": "commercial real estate", "per_page": 20, "orientation": "landscape"},
                headers={"Authorization": PEXELS_KEY},
                timeout=30
            )
            photos = r2.json().get("photos", [])
        
        # Фильтруем уже использованные
        new_photos = [p for p in photos if p["src"]["large"] not in history]
        if not new_photos:
            new_photos = photos  # Если все уже использованы — берём любые
        
        if new_photos:
            p = random.choice(new_photos)
            url = p["src"]["large"]
            print(f"🖼 Фото найдено по запросу: {query} (новых: {len(new_photos)})")
            return url
    except Exception as e:
        print(f"⚠️ Pexels ошибка: {e}")
    return None

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=60)
        print(f"Telegram sendMessage: {r.status_code}")
        if r.status_code == 200: return True
        print(f"Markdown fallback: {r.text[:200]}")
        payload.pop("parse_mode")
        return requests.post(url, json=payload, timeout=60).status_code == 200
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

def send_photo(photo_url, caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {"chat_id": CHANNEL_ID, "photo": photo_url, "caption": caption, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=90)
        print(f"Telegram sendPhoto: {r.status_code}")
        if r.status_code == 200: return True
        print(f"Markdown fallback: {r.text[:200]}")
        payload.pop("parse_mode")
        return requests.post(url, json=payload, timeout=90).status_code == 200
    except Exception as e:
        print(f"❌ Ошибка фото: {e}")
        return False

if __name__ == "__main__":
    post_type, category = get_schedule()
    topic = pick_topic(category)
    print(f"📅 Тип: {post_type} | Категория: {category} | Тема: {topic}")

    ok = False
    photo_url = None
    
    if post_type == "longread":
        ctype = random.choice(CONTENT_TYPES)
        print(f"🎭 Жанр лонгрида: {ctype}")
        text = generate_longread(topic, ctype)
        ok = send_message(text + LONG_FOOTER)
    else:
        text, query = generate_short(topic, category)
        history = load_photo_history()
        photo_url = get_pexels_image(query, history)
        caption = text + SHORT_FOOTER
        if len(caption) > 1024:
            caption = caption[:1020] + "…"
        if photo_url:
            # Сохраняем использованное фото в историю
            history.append(photo_url)
            save_photo_history(history)
            ok = send_photo(photo_url, caption)
            if not ok:
                ok = send_message(caption)
        else:
            print("⚠️ Фото не найдено, шлем текстом.")
            ok = send_message(caption)

    print("✅ Пост опубликован!" if ok else "❌ Пост НЕ опубликован.")