# -*- coding: utf-8 -*-
import os
import random
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from topics import ALL_TOPICS

load_dotenv()

OR_KEY = os.getenv("OPENROUTER_API_KEY")
CHANNEL_URL = os.getenv("CHANNEL_URL")

# Используем только OpenRouter — Groq ключ устарел
or_client = OpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None

CONTENT_TYPES = ["советы", "кейс", "объяснение", "статистика", "разбор_мифа"]

TYPE_INSTRUCTIONS = {
    "советы": "Напиши 3-5 практических советов для инвестора.",
    "кейс": "Напиши короткую историю (кейс) из практики покупки коммерческой недвижимости.",
    "объяснение": "Объясни простыми словами один сложный термин или механизм.",
    "статистика": "Напиши пост с цифрами, трендами и фактами о рынке.",
    "разбор_мифа": "Напиши в формате: МИФ (популярное заблуждение) и РЕАЛЬНОСТЬ (как на самом деле)."
}

def get_topic_and_type():
    hour = datetime.now().hour
    if 5 <= hour < 11: category = "real_estate"
    elif 11 <= hour < 14: category = "finance"
    elif 14 <= hour < 17: category = "legal"
    else: category = "strategy"
    
    topic = random.choice(ALL_TOPICS.get(category, ALL_TOPICS["real_estate"]))
    ctype = random.choice(CONTENT_TYPES)
    return topic, ctype

def generate_post():
    topic, ctype = get_topic_and_type()
    instruction = TYPE_INSTRUCTIONS.get(ctype, "Напиши экспертный пост.")
    
    prompt = f"""
    Ты эксперт по коммерческой недвижимости. Напиши пост для Telegram.
    Тема: {topic}
    Тип: {ctype}
    Инструкция: {instruction}
    
    Требования:
    - Объем: 700-1000 знаков.
    - Стиль: деловой, экспертный, без воды.
    - Структура: Заголовок -> Суть -> Инсайты -> Вывод.
    - В конце: "Хотите разобрать ситуацию? Пишите юристу: @KomInvest_Crimea_bot"
    - Не используй символы # и *.
    - Обязательно закончи пост завершённой мыслью и призывом к действию.
    """

    if not or_client:
        raise Exception("❌ OPENROUTER_API_KEY не задан")

    # Только рабочие модели (из лога и АнтиДолга)
    working_models = [
        "openai/gpt-oss-120b",        # ✅ Основная (сработала)
        "qwen/qwen3.6-27b",            # ✅ Запасная (работала в АнтиДолге)
        "google/gemma-2-9b-it:free"    # ✅ Третий вариант
    ]

    for model in working_models:
        try:
            print(f"🔄 Пробуем {model}...")
            resp = or_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1600,
                extra_headers={"HTTP-Referer": CHANNEL_URL, "X-Title": "KomInvest"}
            )
            text = resp.choices[0].message.content.strip()
            if len(text) > 200 and "I cannot" not in text and "не могу" not in text.lower():
                print(f"✅ {model} сработал!")
                return text
        except Exception as e:
            print(f"⚠️ {model} ошибка: {e}")
            continue

    raise Exception("❌ Все AI-модели недоступны. Пост НЕ будет опубликован.")

if __name__ == "__main__":
    print(generate_post())