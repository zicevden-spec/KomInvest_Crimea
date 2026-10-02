# -*- coding: utf-8 -*-
import os
import random
import feedparser
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
CHANNEL_URL = os.getenv("CHANNEL_URL")

client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1"
) if API_KEY else None

# Список RSS источников (пока тестовые, потом заменим на твои)
RSS_FEEDS = [
    "https://realty.rbc.ru/rss/news",       # РБК Недвижимость
    "https://www.kommersant.ru/rss/theme/12" # Коммерсантъ Недвижимость
]

def get_latest_news():
    """Парсит RSS и возвращает (заголовок, ссылка, краткое описание)"""
    try:
        for feed_url in RSS_FEEDS:
            feed = feedparser.parse(feed_url)
            if feed.entries:
                entry = random.choice(feed.entries[:5]) # Берем одну из последних 5
                title = entry.get("title", "Новость о недвижимости")
                link = entry.get("link", "")
                summary = entry.get("summary", entry.get("description", ""))
                # Очищаем HTML теги из описания
                soup = BeautifulSoup(summary, "html.parser")
                clean_summary = soup.get_text()[:300] # Первые 300 знаков
                return title, link, clean_summary
    except Exception as e:
        print(f"Ошибка парсинга RSS: {e}")
    return None, None, None

def generate_post():
    # 1. Пробуем найти новость
    news_title, news_link, news_summary = get_latest_news()
    
    prompt = ""
    if news_title and news_link:
        # Режим НОВОСТИ
        prompt = f"""
        Ты — эксперт по коммерческой недвижимости. 
        Напиши пост для Telegram-канала на основе этой новости:
        Заголовок: {news_title}
        Текст: {news_summary}
        
        Требования:
        - Объем: 600-900 знаков.
        - Стиль: деловой, аналитический.
        - Структура: 
          1. Цепляющий заголовок (на основе новости).
          2. Суть новости (своими словами).
          3. Вывод: что это значит для инвестора.
        - В конце ОБЯЗАТЕЛЬНО добавь строку:
          🔗 Источник: [{news_title}]({news_link})
        - Не используй символы # и *.
        """
    else:
        # Режим ЭКСПЕРТНЫЙ ПОСТ (если новостей нет)
        topics = [
            "Юридические риски при покупке склада",
            "Как проверить арендатора перед сделкой",
            "Доходность офисов vs стрит-ритейл",
            "Ошибки при покупке земли под коммерцию"
        ]
        topic = random.choice(topics)
        prompt = f"""
        Ты — эксперт по коммерческой недвижимости и юрист. 
        Напиши пост для Telegram-канала "КомИнвест".
        Тема: {topic}
        
        Требования:
        - Объем: 600-900 знаков.
        - Стиль: деловой, спокойный, экспертный.
        - Структура: Заголовок -> Суть -> 3 пункта -> Вывод.
        - В конце добавь: "Хотите проверить объект? Пишите нашему юристу."
        - Не используй символы # и *.
        """

    if not client:
        return "⚠️ Ошибка: Не задан OPENROUTER_API_KEY"

    # Список моделей для перебора (бесплатные/дешевые на OpenRouter)
    models = [
        "google/gemma-2-9b-it:free",
        "meta-llama/llama-3.1-8b-instruct:free",
        "mistralai/mistral-7b-instruct:free"
    ]

    for model in models:
        try:
            print(f"🔄 Генерация через {model}...")
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=800,
                extra_headers={"HTTP-Referer": CHANNEL_URL, "X-Title": "KomInvest Bot"}
            )
            text = response.choices[0].message.content.strip()
            
            # Проверка на отказ модели
            if "I cannot" in text or "не могу" in text or len(text) < 100:
                continue
                
            print(f"✅ Пост сгенерирован!")
            return text
            
        except Exception as e:
            print(f"⚠️ Модель {model} ошибка: {e}")
            continue
            
    return "⚠️ Все модели AI временно недоступны. Попробуйте позже."

if __name__ == "__main__":
    print(generate_post())