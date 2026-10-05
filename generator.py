# -*- coding: utf-8 -*-
import os
import random
import json
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from topics import ALL_TOPICS, SCHEDULE_MAP

load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY")
CHANNEL_URL = os.getenv("CHANNEL_URL")

groq_client = OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_KEY else None
or_client = OpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None

# Типы контента (из АнтиДолга, адаптированы)
CONTENT_TYPES = ["советы", "кейс", "объяснение", "новость", "статистика", "разбор_мифа"]

TYPE_INSTRUCTIONS = {
    "советы": "Напиши 3-5 практических советов для инвестора.",
    "кейс": "Напиши короткую историю (кейс) из практики покупки коммерческой недвижимости.",
    "объяснение": "Объясни простыми словами один сложный термин или механизм.",
    "новость": "Напиши пост на основе предоставленной новости. В конце ОБЯЗАТЕЛЬНО добавь: 🔗 Источник: [Заголовок](Ссылка).",
    "статистика": "Напиши пост с цифрами, трендами и фактами о рынке.",
    "разбор_мифа": "Напиши в формате: МИФ (популярное заблуждение) и РЕАЛЬНОСТЬ (как на самом деле)."
}

# RSS источники
RSS_FEEDS = ["https://realty.rbc.ru/rss/news", "https://www.kommersant.ru/rss/theme/12"]

def get_news():
    try:
        for url in RSS_FEEDS:
            feed = feedparser.parse(url)
            if feed.entries:
                entry = random.choice(feed.entries[:3])
                return entry.get("title"), entry.get("link"), BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()[:300]
    except: pass
    return None, None, None

def get_topic_and_type():
    hour = datetime.now().hour
    if 5 <= hour < 11: category = "real_estate"
    elif 11 <= hour < 14: category = "finance"
    elif 14 <= hour < 17: category = "legal"
    else: category = "strategy"
    
    topic = random.choice(ALL_TOPICS.get(category, ALL_TOPICS["real_estate"]))
    ctype = random.choice(CONTENT_TYPES)
    
    # Если выпала новость, ищем новость
    news_title, news_link, news_body = None, None, None
    if ctype == "новость":
        news_title, news_link, news_body = get_news()
        if not news_title: ctype = "советы" # Фоллбэк, если новостей нет
        
    return topic, ctype, news_title, news_link, news_body

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
    topic, ctype, n_title, n_link, n_body = get_topic_and_type()
    instruction = TYPE_INSTRUCTIONS.get(ctype, "Напиши экспертный пост.")
    
    context = f"Тема: {topic}. Тип: {ctype}. Инструкция: {instruction}"
    if ctype == "новость" and n_title:
        context += f"\nНовость: {n_title}\nТекст: {n_body}\nСсылка: {n_link}"

    prompt = f"""
    Ты эксперт по коммерческой недвижимости. Напиши пост для Telegram.
    {context}
    
    Требования:
    - Объем: 600-900 знаков.
    - Стиль: деловой, экспертный, без воды.
    - Структура: Заголовок -> Суть -> Инсайты -> Вывод.
    - В конце (если это не новость): "Хотите разобрать ситуацию? Пишите юристу: @KomInvest_Crimea_bot"
    - Не используй # и *.
    """

    # 1. Groq (модели из АнтиДолга)
    if groq_client:
        for m in ["llama-3.1-8b-instant", "groq/compound", "mixtral-8x7b-32768"]:
            res = generate_with_ai(groq_client, m, prompt)
            if res: return res

    # 2. OpenRouter (запасной)
    if or_client:
        for m in ["openai/gpt-oss-120b", "google/gemma-2-9b-it:free", "meta-llama/llama-3.1-8b-instruct:free"]:
            res = generate_with_ai(or_client, m, prompt)
            if res: return res

    raise Exception("❌ Все AI-модели недоступны.")

if __name__ == "__main__":
    print(generate_post())