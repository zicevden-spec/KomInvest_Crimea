# -*- coding: utf-8 -*-
import os, random, json, requests
from dotenv import load_dotenv
from generator import get_schedule, pick_topic, generate_longread, generate_short, generate_news, fetch_rss_news, generate_photo_query, CONTENT_TYPES

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_URL = os.getenv("CHANNEL_URL")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")

PHOTO_HISTORY_FILE = "photo_history.json"
NEWS_HISTORY_FILE = "news_history.json"
MAX_HISTORY = 50
TELEGRAM_CAPTION_LIMIT = 1024

LONG_FOOTER = f"\n\n━━━━━━━━━━━━━━━━━━━━\n⚖️ [Подобрать недвижимость с юристом](https://t.me/KomInvest_Crimea_bot)\n📞 [Оставить заявку для юриста](https://t.me/KomInvest_Crimea_bot)"
SHORT_FOOTER = f"\n\n━━━━━━━━━━━━━━━━━━━━\n⚖️ [Подобрать недвижимость с юристом](https://t.me/KomInvest_Crimea_bot)\n📞 [Оставить заявку для юриста](https://t.me/KomInvest_Crimea_bot)"
NEWS_FOOTER = f"\n🌊\n\n━━━━━━━━━━━━━━━━━━━━\n⚖️ [Подобрать недвижимость с юристом](https://t.me/KomInvest_Crimea_bot)\n📞 [Оставить заявку для юриста](https://t.me/KomInvest_Crimea_bot)"

def load_json(path):
    if not os.path.exists(path): return []
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data[-MAX_HISTORY:], f, ensure_ascii=False, indent=2)

def get_pexels_image(query, history):
    if not PEXELS_KEY: return None
    try:
        r = requests.get("https://api.pexels.com/v1/search", params={"query": query, "per_page": 20, "orientation": "landscape"}, headers={"Authorization": PEXELS_KEY}, timeout=30)
        if r.status_code == 200:
            photos = [p for p in r.json().get("photos", []) if p["src"]["large"] not in history]
            if not photos: photos = r.json().get("photos", [])
            if photos:
                print(f"🖼 Фото: {query} (новых: {len(photos)})")
                return random.choice(photos)["src"]["large"]
    except Exception as e: print(f"⚠️ Pexels ошибка: {e}")
    return None

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=60)
        if r.status_code == 200: return True
        payload.pop("parse_mode")
        return requests.post(url, json=payload, timeout=60).status_code == 200
    except Exception as e:
        print(f"❌ Ошибка: {e}"); return False

def send_photo(photo_url, caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {"chat_id": CHANNEL_ID, "photo": photo_url, "caption": caption, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=90)
        if r.status_code == 200: return True
        payload.pop("parse_mode")
        return requests.post(url, json=payload, timeout=90).status_code == 200
    except Exception as e:
        print(f"❌ Ошибка фото: {e}"); return False

def smart_send(text, photo_url=None):
    if photo_url and len(text) <= TELEGRAM_CAPTION_LIMIT:
        print(f"📸 Отправляем С ФОТО (длина {len(text)} <= {TELEGRAM_CAPTION_LIMIT})")
        if send_photo(photo_url, text): return True
    print(f"📝 Отправляем ТЕКСТОМ (длина {len(text)})")
    return send_message(text)

if __name__ == "__main__":
    post_type, category = get_schedule()
    print(f"📅 Тип: {post_type} | Категория: {category}")
    ok = False

    if post_type == "news":
        news_history = load_json(NEWS_HISTORY_FILE)
        news_data = fetch_rss_news(news_history)
        if news_data:
            print(f"📰 Новость: {news_data['title'][:60]}...")
            text, news_image = generate_news(news_data)
            full_text = text + NEWS_FOOTER
            news_history.append(news_data["title"])
            save_json(NEWS_HISTORY_FILE, news_history)
            
            query = generate_photo_query(news_data["title"], "news")
            photo_history = load_json(PHOTO_HISTORY_FILE)
            final_image = get_pexels_image(query, photo_history) or news_image
            if final_image:
                photo_history.append(final_image)
                save_json(PHOTO_HISTORY_FILE, photo_history)
            ok = smart_send(full_text, final_image)
        else:
            print("⚠️ Свежих новостей нет, фоллбэк на короткий пост.")
            post_type, category = "short", random.choice(["finance", "strategy"])

    if post_type == "longread":
        topic = pick_topic(category)
        text = generate_longread(topic, random.choice(CONTENT_TYPES))
        ok = smart_send(text + LONG_FOOTER)
    elif post_type == "short":
        topic = pick_topic(category)
        text, query = generate_short(topic, category)
        photo_history = load_json(PHOTO_HISTORY_FILE)
        photo_url = get_pexels_image(query, photo_history)
        if photo_url:
            photo_history.append(photo_url)
            save_json(PHOTO_HISTORY_FILE, photo_history)
        ok = smart_send(text + SHORT_FOOTER, photo_url)

    print("✅ Пост опубликован!" if ok else "❌ Пост НЕ опубликован.")