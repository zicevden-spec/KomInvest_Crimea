# -*- coding: utf-8 -*-
import os
import random
import requests
from duckduckgo_search import DDGS
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY")
CHANNEL_URL = os.getenv("CHANNEL_URL")

# Клиенты
groq_client = OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_KEY else None
or_client = OpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None

def get_news():
    """Ищет свежую новость про коммерческую недвижимость"""
    try:
        with DDGS() as ddgs:
            # Ищем новости по Крыму и коммерции
            results = list(ddgs.news("коммерческая недвижимость Крым инвестиции офис склад", max_results=1))
            if results:
                r = results[0]
                return r.get("title"), r.get("url"), r.get("body", "")[:300]
    except Exception as e:
        print(f"News search error: {e}")
    return None, None, None

def generate_with_ai(client, model_name, prompt):
    try:
        print(f"🔄 Пробуем {model_name}...")
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800,
            extra_headers={"HTTP-Referer": CHANNEL_URL, "X-Title": "KomInvest"} if "openrouter" in str(client.base_url) else {}
        )
        text = resp.choices[0].message.content.strip()
        if len(text) > 100 and "не могу" not in text.lower():
            return text
    except Exception as e:
        print(f"⚠️ {model_name} error: {e}")
    return None

def generate_post():
    # 1. Ищем новость
    n_title, n_url, n_body = get_news()
    
    if n_title and n_url:
        # Режим НОВОСТИ (как в АнтиДолге)
        prompt = f"""
        Ты эксперт по коммерческой недвижимости. Напиши пост для Telegram на основе новости:
        Заголовок: {n_title}
        Текст: {n_body}
        
        Требования: 600-900 знаков, деловой стиль.
        Структура: Заголовок -> Суть -> Вывод для инвестора.
        В конце ОБЯЗАТЕЛЬНО добавь строку:
        🔗 Источник: [{n_title}]({n_url})
        Не используй # и *.
        """
    else:
        # Режим ЭКСПЕРТНЫЙ ПОСТ
        topics = ["Юридические риски покупки офиса", "Доходность складов vs офисов", "Проверка арендатора", "Ошибки при покупке земли"]
        topic = random.choice(topics)
        prompt = f"""
        Ты эксперт по коммерческой недвижимости. Напиши пост на тему: {topic}.
        Требования: 600-900 знаков, деловой стиль, структура (заголовок -> суть -> 3 пункта -> вывод).
        В конце: "Хотите проверить объект? Пишите нашему юристу."
        Не используй # и *.
        """

    # 2. Пробуем Groq (лучшие бесплатные модели из АнтиДолга)
    if groq_client:
        for m in ["llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]:
            res = generate_with_ai(groq_client, m, prompt)
            if res: return res

    # 3. Пробуем OpenRouter (запасной)
    if or_client:
        for m in ["google/gemma-2-9b-it:free", "meta-llama/llama-3.1-8b-instruct:free"]:
            res = generate_with_ai(or_client, m, prompt)
            if res: return res

    return "⚠️ Все AI-модели временно недоступны. Попробуйте позже."

if __name__ == "__main__":
    print(generate_post())