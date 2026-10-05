# -*- coding: utf-8 -*-
import os
import random
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from dotenv import load_dotenv
from topics import ALL_TOPICS

load_dotenv()

OR_KEY = os.getenv("OPENROUTER_API_KEY")
CHANNEL_URL = os.getenv("CHANNEL_URL")
or_client = OpenAI(api_key=OR_KEY, base_url="https://openrouter.ai/api/v1") if OR_KEY else None

MSK = timezone(timedelta(hours=3))

CONTENT_TYPES = ["советы", "кейс", "объяснение", "статистика", "разбор_мифа"]

TYPE_INSTRUCTIONS = {
    "советы": "Напиши 3-5 практических советов для инвестора.",
    "кейс": "Напиши короткую историю (кейс) из практики покупки коммерческой недвижимости.",
    "объяснение": "Объясни простыми словами один сложный термин или механизм.",
    "статистика": "Напиши пост с цифрами, трендами и фактами о рынке.",
    "разбор_мифа": "Напиши в формате: МИФ (популярное заблуждение) и РЕАЛЬНОСТЬ (как на самом деле)."
}

CATEGORY_BY_HOUR = {10: "real_estate", 12: "finance", 16: "legal", 18: "strategy"}
POST_TYPE_BY_HOUR = {10: "longread", 12: "short", 16: "longread", 18: "short"}

# Уникальные прилагательные для разнообразия фото
PHOTO_STYLES = ["luxury", "aerial view", "minimalist", "modern glass", "night lighting", "sunrise", "architectural detail", "interior design", "exterior"]
PHOTO_OBJECTS = {
    "real_estate": ["office building", "business center", "commercial property", "corporate headquarters", "office lobby"],
    "finance": ["financial chart", "investment portfolio", "gold coins", "calculations documents", "money growth"],
    "legal": ["legal documents", "contract signing", "court building", "lawyer office", "legal books"],
    "strategy": ["strategic meeting", "business planning", "whiteboard brainstorming", "team discussion", "business roadmap"]
}

def get_schedule():
    hour = datetime.now(MSK).hour
    if hour in CATEGORY_BY_HOUR:
        return POST_TYPE_BY_HOUR[hour], CATEGORY_BY_HOUR[hour]
    force = os.getenv("FORCE_POST_TYPE", "")
    if force in ("longread", "short"):
        cat = random.choice(list(CATEGORY_BY_HOUR.values()))
        return force, cat
    if 5 <= hour < 11: return "longread", "real_estate"
    if 11 <= hour < 14: return "short", "finance"
    if 14 <= hour < 17: return "longread", "legal"
    return "short", "strategy"

def pick_topic(category):
    return random.choice(ALL_TOPICS.get(category, ALL_TOPICS["real_estate"]))

def generate_photo_query(topic, category):
    """Создаёт уникальный фото-запрос на основе темы и категории"""
    obj = random.choice(PHOTO_OBJECTS.get(category, PHOTO_OBJECTS["real_estate"]))
    style = random.choice(PHOTO_STYLES)
    # Берём ключевое слово из темы (первые 3-4 слова)
    topic_words = topic.lower().replace(":", "").replace("?", "").split()[:3]
    topic_part = " ".join(topic_words) if topic_words else ""
    # Смешиваем: 50% шанс использовать тему, 50% — только стиль
    if random.random() < 0.5 and topic_part:
        return f"{style} {obj}, {topic_part}"
    return f"{style} {obj}"

LONGREAD_PROMPT = """
Ты — эксперт по коммерческой недвижимости и редактор делового Telegram-канала "КомИнвест".
Напиши ЛОНГРИД на тему: {topic}
Жанр: {ctype}. Инструкция: {instruction}

СТРОГИЙ ФОРМАТ ОТВЕТА:
1) Первая строка — жирный заголовок с одним эмодзи в начале, до 60 знаков:
*🏢 Пример заголовка*
2) Пустая строка.
3) Абзац сути (2-3 предложения). Ключевой термин выдели жирным через *звёздочки*.
4) Пустая строка.
5) Блок инсайтов: 3-5 пунктов, каждый с новой строки, начинается с эмодзи (🔹 ✅ ⚠️ 📊 💡) и жирного подзаголовка:
🔹 *Подзаголовок.* Раскрытие мысли одним-двумя предложениями.
6) Пустая строка.
7) Вывод: начни с жирного *Вывод:* и дай 1-2 предложения.
8) Пустая строка.
9) Финальная строка-призыв:
⚖️ Хотите разобрать вашу ситуацию? Пишите юристу: @KomInvest_Crimea_bot

ПРАВИЛА:
- Объем 900-1400 знаков.
- Жирный текст ТОЛЬКО через *звёздочки*. Символы # и _ не используй вообще.
- Эмодзи умеренно: 4-7 штук на весь пост.
- Стиль деловой, экспертный, без воды.
- Закончи пост завершённой мыслью, без обрывов.
"""

SHORT_PROMPT = """
Ты — маркетолог и эксперт по коммерческой недвижимости Крыма.
Напиши КОРОТКИЙ продающий пост на тему: {topic}

СТРОГИЙ ФОРМАТ ОТВЕТА:
1) Первая строка — жирный хук с эмодзи, до 55 знаков:
*💰 Пример хука*
2) Пустая строка.
3) Продающий абзац (2-3 предложения): опиши проблему или возможность, главную выгоду выдели жирным через *звёздочки*.
4) Пустая строка.
5) Блок из 3 буллетов с жирными подзаголовками (каждый даёт конкретную пользу с цифрами или фактами):
🔹 *Подзаголовок 1.* Короткое раскрытие.
✅ *Подзаголовок 2.* Короткое раскрытие.
📊 *Подзаголовок 3.* Короткое раскрытие.
6) Пустая строка.
7) Короткий мини-кейс (1 предложение): пример из практики или реалистичная ситуация инвестора.
8) Пустая строка.
9) Строка-призыв со ссылкой в markdown:
👉 [Получить консультацию юриста](https://t.me/KomInvest_Crimea_bot)

ПРАВИЛА:
- Объем 650-850 знаков.
- Тон энергичный и уверенный, без крика и капса.
- Жирный ТОЛЬКО через *звёздочки*. Символы # и _ не используй.
- Эмодзи: 4-6 штук.
- Буллеты должны давать конкретную пользу с цифрами, а не общие слова.
- Мини-кейс должен быть реалистичным и коротким (1 предложение).
- Закончи пост завершённой мыслью.
"""

def call_ai(prompt):
    models = ["openai/gpt-oss-120b", "qwen/qwen3.6-27b", "google/gemma-2-9b-it:free"]
    for model in models:
        try:
            print(f"🔄 Пробуем {model}...")
            resp = or_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=1600,
                extra_headers={"HTTP-Referer": CHANNEL_URL, "X-Title": "KomInvest"}
            )
            text = resp.choices[0].message.content.strip()
            if len(text) > 200 and "I cannot" not in text and "не могу" not in text.lower():
                print(f"✅ {model} сработал!")
                return text
        except Exception as e:
            print(f"⚠️ {model} ошибка: {e}")
    return None

def generate_longread(topic, ctype):
    instruction = TYPE_INSTRUCTIONS.get(ctype, "Напиши экспертный пост.")
    text = call_ai(LONGREAD_PROMPT.format(topic=topic, ctype=ctype, instruction=instruction))
    if not text:
        raise Exception("❌ AI недоступен (лонгрид). Пост НЕ опубликован.")
    return text

def generate_short(topic, category):
    text = call_ai(SHORT_PROMPT.format(topic=topic))
    if not text:
        raise Exception("❌ AI недоступен (короткий пост). Пост НЕ опубликован.")
    photo_query = generate_photo_query(topic, category)
    return text.strip(), photo_query