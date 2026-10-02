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

# Типы контента (как в АнтиДолге)
CONTENT_TYPES = ["советы", "разбор_мифа", "кейс", "объяснение", "статистика"]

TYPE_INSTRUCTIONS = {
    "советы": "Напиши 3-5 практических советов по теме.",
    "разбор_мифа": "Напиши пост в формате 'Миф vs Реальность'. Развей популярное заблуждение.",
    "кейс": "Напиши короткую историю (кейс) из практики инвестора или юриста по этой теме.",
    "объяснение": "Объясни простыми словами один сложный термин или механизм по теме.",
    "статистика": "Напиши пост с упором на цифры, тренды и статистику по теме."
}

def get_topic_and_type():
    """Выбирает тему и тип контента на основе текущего часа"""
    hour = datetime.now().hour
    if 5 <= hour < 11: category = "real_estate"
    elif 11 <= hour < 14: category = "finance"
    elif 14 <= hour < 17: category = "legal"
    else: category = "strategy"
    
    topics = ALL_TOPICS.get(category, ALL_TOPICS["real_estate"])
    topic = random.choice(topics)
    content_type = random.choice(CONTENT_TYPES)
    return topic, content_type, category

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
    topic, content_type, category = get_topic_and_type()
    instruction = TYPE_INSTRUCTIONS.get(content_type, "Напиши экспертный пост.")
    
    prompt = f"""
    Ты эксперт по коммерческой недвижимости. Напиши пост для Telegram-канала "КомИнвест".
    Тема: {topic}
    Тип контента: {content_type}
    Инструкция: {instruction}
    
    Требования:
    - Объем: 600-900 знаков.
    - Стиль: деловой, экспертный, без воды.
    - Структура: Цепляющий заголовок -> Суть -> Инсайты по инструкции -> Вывод.
    - В конце добавь: "Хотите разобрать вашу ситуацию? Пишите нашему юристу."
    - Не используй символы # и *.
    """

    # 1. Пробуем Groq
    if groq_client:
        for m in ["llama-3.1-8b-instant", "gemma2-9b-it"]:
            res = generate_with_ai(groq_client, m, prompt)
            if res: return res

    # 2. Пробуем OpenRouter
    if or_client:
        for m in ["google/gemma-2-9b-it:free", "meta-llama/llama-3.1-8b-instruct:free"]:
            res = generate_with_ai(or_client, m, prompt)
            if res: return res

    # 3. Фоллбэк: Шаблонный пост (если AI совсем недоступен)
    print("ℹ️ AI недоступен. Генерируем шаблонный пост.")
    return f"""
🏢 {topic}

Разбираем ключевые аспекты темы для инвесторов и предпринимателей.

🔹 Важно учитывать текущие рыночные условия и юридические нюансы.
🔹 Доходность зависит от множества факторов: локация, состояние, арендаторы.
🔹 Безопасность сделки — приоритет номер один.

Каждый объект требует индивидуального подхода и глубокой проверки.

⚖️ Хотите разобрать вашу ситуацию? Пишите нашему юристу: @KomInvest_Crimea_bot

━━━━━━━━━━━━━━━━━━━━
🏢 КомИнвест | Коммерческая недвижимость
{CHANNEL_URL}
"""

if __name__ == "__main__":
    print(generate_post())