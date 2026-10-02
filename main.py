# -*- coding: utf-8 -*-
import os
import requests
from dotenv import load_dotenv
from generator import generate_post

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_URL = os.getenv("CHANNEL_URL")

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        print(f"Telegram API response: {r.status_code}")
        if r.status_code != 200:
            print(f"Error details: {r.text}")
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

if __name__ == "__main__":
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ Ошибка: Проверьте .env")
    else:
        print("🔄 Генерация поста для КомИнвест...")
        text = generate_post()
        
        footer = f"""

━━━━━━━━━━━━━━━━━━━━
🏢 [КомИнвест | Коммерческая недвижимость]({CHANNEL_URL})

⚖️ [Консультация юриста](https://t.me/KomInvest_Crimea_bot)
📞 [Позвонить / Заказать проверку](https://t.me/KomInvest_Crimea_bot)"""
        
        full_text = text + footer
        
        print("📤 Отправляем в Telegram канал...")
        if send_message(full_text):
            print("✅ Пост успешно опубликован!")
        else:
            print("❌ Не удалось отправить пост.")