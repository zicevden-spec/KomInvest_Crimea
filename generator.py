# -*- coding: utf-8 -*-
import os
import json
import random
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
BANK_FILE = "posts_bank.json"
HISTORY_FILE = "post_history.json"

client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1"
) if API_KEY else None

# Модели, которые еще могут работать бесплатно или дешево
MODELS_TO_TRY = [
    "google/gemma-2-9b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free"
]

def load_bank():
    try:
        with open(BANK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)

def get_post_from_bank():
    bank = load_bank()
    history = load_history()
    today = datetime.now().strftime("%Y-%m-%d")
    used_topics = {h["topic"] for h in history if h["date"] == today}
    available = [p for p in bank if p["topic"] not in used_topics]
    if not available:
        available = bank
    post = random.choice(available)
    history.append({"topic": post["topic"], "date": today, "ts": datetime.now().isoformat()})
    save_history(history)
    return post["text"]

def generate_post():
    # Сначала пробуем AI, е    if client:
        prompt = """
        Ты — эксперт по коммерческой недвижимости и юрист. 
        Пишешь пост для Telegram-канала "КомИнвест" (Коммерческая недвижимость Крыма).
        Тема: Юридические риски при покупке офиса/склада.
        Требования: 600-900 знаков, деловой стиль, без воды, структура (заголовок -> суть -> 3 пункта -> вывод).
        В конце: "Хотите проверить объект? Пишите нашему юристу."
        Не используй # и *.
        """
        for model in MODELS_TO_TRY:
            try:
                print(f"🔄 Пробуем модель: {model}...")
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=800,
                    extra_headers={"HTTP-Referer": "https://t.me/KomInvest_Crimea", "X-Title": "KomInvest Bot"}
                )
                text = response.choices[0].message.content.strip()
                print(f"✅ Модель {model} сработала!")
                return text
            except Exception as e:
                print(f"⚠️ Модель {model} недоступна: {e}. Пробуем следующую...")
                continue
    
    # Если AI не сработал — берем из банка
    print("ℹ️ AI недоступен или ошибся. Берем пост из локального банка.")
    return get_post_from_bank()

if __name__ == "__main__":
    print(generate_post())