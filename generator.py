# -*- coding: utf-8 -*-
import os
import random
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from topics import ALL_TOPICS

load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY")
CHANNEL_URL = os.getenv("CHANNEL_URL")

groq_client = OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_KEY else None
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

def generate_with_ai(client, model, prompt):
    try:
        print(f"🔄 Пробуем {model}...")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1600,
            extra_headers={"HTTP-Referer": CHANNEL_URL, "X-Title": "KomInvest"} if "openrouter" in str(client.base_url) else {}
        )
        text = resp.choices[0].message.content.strip()
        if len(text) > 200 and "I cannot" not in text and "не могу" not in text.lower():
            print(f"✅ {model} сработал!")
            return text
    except Exception as e:
        print(f"⚠️ {model} ошибка: {e}")
    return None

def generate_post():
    topic, ctype = get_topic_and_type()
    instruction = TYPE_INSTRUCTIONS.get(ctype, "Напиши экспертный пост.")
    
    prompt = f"""
    Ты эксперт по коммерческой недвижимости. Напиши пост для Telegram.
    Тема: {topic}
    Тип: {ctype}
    Инструкция: {instruction}
    
    Требования:
    - Объем: 600-900 знаков.
    - Стиль: деловой, экспертный, без воды.
    - Структура: Заголовок -> Суть -> Инсайты -> Вывод.
    - В конце: "Хотите разобрать ситуацию? Пишите юристу: @KomInvest_Crimea_bot"
    - Не используй символы # и *.
    - Обязательно закончи пост завершённой мыслью.
    """

    # 1. Groq — актуальные модели 2026 года
    if groq_client:
        for m in [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "qwen/qwen3-32b",
            "llama-3.3-70b-versatile"
        ]:
            res = generate_with_ai(groq_client, m, prompt)
            if res: return res

    # 2. OpenRouter — модели, которые работали в АнтиДолге
    if or_client:
        for m in [
            "openai/gpt-oss-120b",
            "qwen/qwen3.6-27b",
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.1-8b-instruct:free"
        ]:
            res = generate_with_ai(or_client, m, prompt)
            if res: return res

    # 3. КРИТИЧЕСКАЯ ОШИБКА — никакого фоллбэка на заглушку!
    raise Exception("❌ Все AI-модели недоступны. Пост НЕ будет опубликован.")

if __name__ == "__main__":
    print(generate_post())