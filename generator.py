# -*- coding: utf-8 -*-
import os
import random
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

def get_topic_and_type():
    hour = datetime.now().hour
    if 5 <= hour < 11: category = "real_estate"
    elif 11 <= hour < 14: category = "finance"
    elif 14 <= hour < 17: category = "legal"
    else: category = "strategy"
    
    topics = ALL_TOPICS.get(category, ALL_TOPICS["real_estate"])
    topic = random.choice(topics)
    types = ["советы", "разбор_мифа", "кейс", "объяснение"]
    content_type = random.choice(types)
    return topic, content_type

def generate_post():
    topic, content_type = get_topic_and_type()
    
    prompt = f"""
    Ты эксперт по коммерческой недвижимости. Напиши пост для Telegram.
    Тема: {topic}
    Тип: {content_type}
    
    Требования:
    - Объем: 600-900 знаков.
    - Стиль: деловой, экспертный.
    - Структура: Заголовок -> Суть -> 2-3 инсайта -> Вывод.
    - В конце: "Хотите разобрать ситуацию? Пишите юристу: @KomInvest_Crimea_bot"
    - Не используй # и *.
    """

    # 1. Пробуем Groq
    if groq_client:
        try:
            print("🔄 Пробуем Groq (llama-3.1-8b-instant)...")
            resp = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=800
            )
            text = resp.choices[0].message.content.strip()
            if len(text) > 100:
                print("✅ Groq сработал!")
                return text
        except Exception as e:
            print(f"⚠️ Groq ошибка: {e}")

    # 2. Пробуем OpenRouter
    if or_client:
        try:
            print("🔄 Пробуем OpenRouter (gemma-2-9b-it)...")
            resp = or_client.chat.completions.create(
                model="google/gemma-2-9b-it",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=800,
                extra_headers={"HTTP-Referer": CHANNEL_URL, "X-Title": "KomInvest"}
            )
            text = resp.choices[0].message.content.strip()
            if len(text) > 100:
                print("✅ OpenRouter сработал!")
                return text
        except Exception as e:
            print(f"⚠️ OpenRouter ошибка: {e}")

    # 3. Если всё упало — возвращаем ошибку, а не заглушку!
    raise Exception("❌ Все AI-модели недоступны. Пост не опубликован.")

if __name__ == "__main__":
    print(generate_post())