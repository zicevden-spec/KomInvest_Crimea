# -*- coding: utf-8 -*-
import json
import os
import random
from datetime import datetime

BANK_FILE = "posts_bank.json"
HISTORY_FILE = "post_history.json"

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

def generate_post():
    bank = load_bank()
    history = load_history()
    
    if not bank:
        return "⚠️ Банк статей пуст. Добавьте посты в posts_bank.json"
    
    # Выбираем пост, который еще не публиковали сегодня
    today = datetime.now().strftime("%Y-%m-%d")
    used_topics = {h["topic"] for h in history if h["date"] == today}
    
    available = [p for p in bank if p["topic"] not in used_topics]
    
    if not available:
        # Если все посты на сегодня использованы, берем случайный из банка
        print("ℹ️ Все посты на сегодня опубликованы. Берем случайный из банка.")
        available = bank
    
    post = random.choice(available)
    
    # Сохраняем в историю
    history.append({"topic": post["topic"], "date": today, "ts": datetime.now().isoformat()})
    save_history(history)
    
    print(f"✅ Выбран пост из банка: {post['topic']}")
    return post["text"]

if __name__ == "__main__":
    print(generate_post())