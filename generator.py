# -*- coding: utf-8 -*-
import os
import random
import feedparser
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY")
CHANNEL_URL = os.getenv("CHANNEL_URL")

groq_client = OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_KEY else None
or_client = OpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None

# RSS источники (РБК Недвижимость, Коммерсантъ)
RSS_FEEDS = [
    "https://realty.rbc.ru/rss/news",
    "https://www.kommersant.ru/rss/theme/12"
]

def get_news():
    """Парсит RSS и возвращает (заголовок, ссылка, текст)"""
    try:
        for url in RSS_FEEDS:
            feed = feedparser.parse(url)
            if feed.entries:
                entry = random.choice(feed.entries[:3])
                title = entry.get("title", "Новость")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                soup = BeautifulSoup(summary, "html.parser")
                text = soup.get_text()[:300]
                return title, link, text
    except Exception as e:
        print(f"RSS Error: {e}")
    return None, None, None

def generate_with_ai(client, model, prompt):
    try:
        print(f"🔄 Пробуем {model}...")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800,
            extra_headers={"HTTP-Referer": CHANNEL_URL, "X-Title": "KomInvest"} if "openrouter" in str(client.base_url) else {}
        )
        text = resp.choices[0].message.content.strip()
        if len(text) > 100: return text
    except Exception as e:
        print(f"⚠️ {model} error: {e}")
    return None

def generate_post():
    # 1. Ищем новость
    n_title, n_url, n_text = get_news()
    
    if n_title and n_url:
        prompt = f"""
        Ты эксперт по коммерческой недвижимости. Напиши пост для Telegram на основе новости:
        Заголовок: {n_title}
        Текст: {n_text}
        
        Требования: 600-900 знаков, деловой стиль.
        Структура: Заголовок -> Суть -> Вывод для инвестора.
        В конце ОБЯЗАТЕЛЬНО добавь: 🔗 Источник: [{n_title}]({n_url})
        Не используй # и *.
        """
    else:
        topics = ["Юридические риски покупки офиса", "Доходность складов vs офисов", "Проверка арендатора", "Ошибки при покупке земли"]
        topic = random.choice(topics)
        prompt = f"""
        Ты эксперт по коммерческой недвижимости. Напиши пост на тему: {topic}.
        Требования: 600-900 знаков, деловой стиль, структура (заголовок -> суть -> 3 пункта -> вывод).
        В конце: "Хотите проверить объект? Пишите нашему юристу."
        Не используй # и *.
        """

    # 2. Пробуем Groq (актуальные модели 2026)
    if groq_client:
        for m in ["llama-3.1-8b-instant", "gemma2-9b-it", "mixtral-8x7b-32768"]:
            res = generate_with_ai(groq_client, m, prompt)
            if res: return res

    # 3. Пробуем OpenRouter (запасной)
    if or_client:
        for m in ["google/gemma-2-9b-it:free", "meta-llama/llama-3.1-8b-instruct:free"]:
            res = generate_with_ai(or_client, m, prompt)
            if res: return res

    # 4. Фоллбэк: Банк статей (если всё упало)
    print("ℹ️ AI недоступен. Берем пост из локального банка.")
    try:
        import json
        with open("posts_bank.json", "r", encoding="utf-8") as f:
            bank = json.load(f)
        return random.choice(bank)["text"]
    except:
        return "⚠️ Все системы временно недоступны. Попробуйте позже."

if __name__ == "__main__":
    print(generate_post())