# -*- coding: utf-8 -*-
import os
import random
import json
import requests
from dotenv import load_dotenv
from generator import (get_schedule, pick_topic, generate_longread,
                       generate_short, generate_news,
                       generate_photo_query, CONTENT_TYPES)
from rss_news import fetch_rss_news

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_URL = os.getenv("CHANNEL_URL")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")

PHOTO_HISTORY_FILE = "photo_history.json"
NEWS_HISTORY_FILE = "news_history.json"
MAX_PHOTO_HISTORY = 30
MAX_NEWS_HISTORY = 100

# Telegram ограничение: caption к фото максимум 1024 символа
TELEGRAM_CAPTION_LIMIT = 1024

LONG_FOOTER = f"""

━━━━━━━━━━━━━━━━━━━━
🏢 [КомИнвест | Коммерческая недвижимость]({CHANNEL_URL})

⚖️ [Консультация юриста](https://t.me/KomInvest_Crimea_bot)
📞 [Позвонить / Заказать проверку](https://t.me/KomInvest_Crimea_bot)"""

SHORT_FOOTER = f"""

🏢 [КомИнвест | Коммерческая недвижимость Крыма]({CHANNEL_URL})"""

NEWS_FOOTER = f"""

━━━━━━━━━━━━━━━━━━━━
🏢 [КомИнвест | Коммерческая недвижимость]({CHANNEL_URL})" + "\u200B🌊"""

def load_json(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_pexels_image(query, history):
    if not PEXELS_KEY:
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
            r2 = requests.get(
                "https://api.pexels.com/v1/search",
                params={"query": "commercial real estate", "per_page": 20, "orientation": "landscape"},
                headers={"Authorization": PEXELS_KEY},
                timeout=30
            )
            photos = r2.json().get("photos", [])

        new_photos = [p for p in photos if p["src"]["large"] not in history]
        if not new_photos:
            new_photos = photos

        if new_photos:
            p = random.choice(new_photos)
            url = p["src"]["large"]
            print(f"🖼 Фото: {query} (новых: {len(new_photos)})")
            return url
    except Exception as e:
        print(f"⚠️ Pexels ошибка: {e}")
    return None

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=60)
        print(f"sendMessage: {r.status_code}")
        if r.status_code == 200: return True
        print(f"Markdown fallback: {r.text[:200]}")
        payload.pop("parse_mode")
        return requests.post(url, json=payload, timeout=60).status_code == 200
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def send_photo(photo_url, caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {"chat_id": CHANNEL_ID, "photo": photo_url, "caption": caption, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=90)
        print(f"sendPhoto: {r.status_code}")
        if r.status_code == 200: return True
        print(f"Markdown fallback: {r.text[:200]}")
        payload.pop("parse_mode")
        return requests.post(url, json=payload, timeout=90).status_code == 200
    except Exception as e:
        print(f"❌ Ошибка фото: {e}")
        return False

def smart_send(text, photo_url=None):
    """
    Умная отправка: если есть фото и текст влезает в 1024 символа — отправляем с фото.
    Если текст слишком длинный — отправляем просто текстом, чтобы не обрезать.
    """
    text_len = len(text)

    if photo_url and text_len <= TELEGRAM_CAPTION_LIMIT:
        print(f"📸 Отправляем С ФОТО (длина {text_len} ≤ {TELEGRAM_CAPTION_LIMIT})")
        ok = send_photo(photo_url, text)
        if ok:
            return True
        # Если фото не отправилось — фоллбэк на текст
        print("⚠️ Фото не ушло, фоллбэк на текст")
        return send_message(text)

    if photo_url:
        print(f"📝 Пост слишком длинный для фото ({text_len} > {TELEGRAM_CAPTION_LIMIT}), отправляем ТЕКСТОМ без картинки")
    else:
        print(f"📝 Отправляем текстом (длина {text_len})")

    return send_message(text)

if __name__ == "__main__":
    post_type, category = get_schedule()
    print(f"📅 Тип: {post_type} | Категория: {category}")

    ok = False

    # ====== НОВОСТИ ======
    if post_type == "news":
        news_history = load_json(NEWS_HISTORY_FILE)
        news_data = fetch_rss_news(news_history)

        if news_data:
            print(f"📰 Новость: {news_data['title'][:60]}...")
            text, news_image, news_url = generate_news(news_data)
            full_text = text + NEWS_FOOTER

            news_history.append(news_data["title"])
            save_json(NEWS_HISTORY_FILE, news_history[-MAX_NEWS_HISTORY:])

            # Если нет картинки в новости — берём из Pexels
            final_image = news_image
            if not final_image:
                query = generate_photo_query(news_data["title"], "news")
                photo_history = load_json(PHOTO_HISTORY_FILE)
                final_image = get_pexels_image(query, photo_history)
                if final_image:
                    photo_history.append(final_image)
                    save_json(PHOTO_HISTORY_FILE, photo_history[-MAX_PHOTO_HISTORY:])

            ok = smart_send(full_text, final_image)
        else:
            print("⚠️ Свежих новостей нет, фоллбэк на короткий пост.")
            post_type = "short"
            category = random.choice(["finance", "strategy", "real_estate"])

    # ====== ЛОНГРИД ======
    if post_type == "longread":
        topic = pick_topic(category)
        print(f"📖 Лонгрид: {topic}")
        ctype = random.choice(CONTENT_TYPES)
        text = generate_longread(topic, ctype)
        full_text = text + LONG_FOOTER
        # Лонгрид почти всегда длиннее 1024 → отправится текстом (без фото)
        ok = smart_send(full_text)

    # ====== КОРОТКИЙ ПОСТ ======
    elif post_type == "short":
        topic = pick_topic(category)
        print(f"🖼 Короткий: {topic}")
        text, query = generate_short(topic, category)
        caption = text + SHORT_FOOTER
        photo_history = load_json(PHOTO_HISTORY_FILE)
        photo_url = get_pexels_image(query, photo_history)
        if photo_url:
            photo_history.append(photo_url)
            save_json(PHOTO_HISTORY_FILE, photo_history[-MAX_PHOTO_HISTORY:])
        # Если caption влезает в 1024 — будет с фото, иначе — просто текст
        ok = smart_send(caption, photo_url)

    print("✅ Пост опубликован!" if ok else "❌ Пост НЕ опубликован.")