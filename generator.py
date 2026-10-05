# -*- coding: utf-8 -*-
import os
import random
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from bs4 import BeautifulSoup
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

CATEGORY_BY_HOUR = {10: "real_estate", 12: "finance", 14: "news", 16: "legal", 18: "strategy", 20: "news"}
POST_TYPE_BY_HOUR = {10: "longread", 12: "short", 14: "news", 16: "longread", 18: "short", 20: "news"}

# RSS-ленты cre.ru
RSS_FEEDS = [
    ("https://cre.ru/rss/rss_news.xml", "CRE News"),
    ("https://cre.ru/rss/rss_analitics.xml", "CRE Аналитика"),
    ("https://cre.ru/rss/rss_expert.xml", "CRE Экспертиза"),
    ("https://cre.ru/rss/rss_all.xml", "CRE Все"),
]

PHOTO_STYLES = ["luxury", "aerial view", "minimalist", "modern glass", "night lighting", "sunrise", "architectural detail", "interior design"]
PHOTO_OBJECTS = {
    "real_estate": ["office building", "business center", "commercial property"],
    "finance": ["financial chart", "investment portfolio", "calculations documents"],
    "legal": ["legal documents", "contract signing", "lawyer office"],
    "strategy": ["strategic meeting", "business planning", "whiteboard brainstorming"],
    "news": ["modern office exterior", "business center skyline", "commercial district"]
}

def get_schedule():
    hour = datetime.now(MSK).hour
    force = os.getenv("FORCE_POST_TYPE", "")
    if force in ("longread", "short", "news"):
        cat = CATEGORY_BY_HOUR.get(hour, random.choice(list(CATEGORY_BY_HOUR.values())))
        return force, cat
    if hour in POST_TYPE_BY_HOUR:
        return POST_TYPE_BY_HOUR[hour], CATEGORY_BY_HOUR[hour]
    if 5 <= hour < 11: return "longread", "real_estate"
    if 11 <= hour < 14: return "short", "finance"
    if 14 <= hour < 17: return "longread", "legal"
    return "short", "strategy"

def pick_topic(category):
    return random.choice(ALL_TOPICS.get(category, ALL_TOPICS["real_estate"]))

def generate_photo_query(topic, category):
    obj = random.choice(PHOTO_OBJECTS.get(category, PHOTO_OBJECTS["real_estate"]))
    style = random.choice(PHOTO_STYLES)
    topic_words = topic.lower().replace(":", "").replace("?", "").split()[:3]
    topic_part = " ".join(topic_words) if topic_words else ""
    if random.random() < 0.5 and topic_part:
        return f"{style} {obj}, {topic_part}"
    return f"{style} {obj}"

# ============ RSS ФУНКЦИИ ============

def fetch_rss_news(history_urls, max_age_hours=168):
    """
    Берёт свежую новость из cre.ru RSS.
    Возвращает (title, url, body_text, image_url, source_name) или None.
    Пропускает новости, которые уже были опубликованы (в history_urls).
    """
    now = datetime.now(MSK)
    candidates = []

    for feed_url, source_name in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            if not feed.entries:
                continue
            for entry in feed.entries[:10]:  # смотрим последние 10
                url = entry.get("link")
                if not url or url in history_urls or entry.get("title") in [h.get("title") for h in history_urls if isinstance(h, dict)]:
                    continue

                # Проверка свежести
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    import time
                    published = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    import time
                    published = datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)

                if published:
                    age_hours = (now - published).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        continue

                # Извлекаем картинку
                image_url = None
                if hasattr(entry, "media_content") and entry.media_content:
                    image_url = entry.media_content[0].get("url")
                elif hasattr(entry, "enclosures") and entry.enclosures:
                    for enc in entry.enclosures:
                        if enc.get("type", "").startswith("image/"):
                            image_url = enc.get("url")
                            break

                # Если картинки нет в media — ищем в HTML описания
                if not image_url:
                    html = entry.get("summary", "") or entry.get("description", "")
                    soup = BeautifulSoup(html, "html.parser")
                    img = soup.find("img")
                    if img and img.get("src"):
                        image_url = img["src"]

                # Извлекаем текст
                raw_html = entry.get("summary", "") or entry.get("description", "") or ""
                soup = BeautifulSoup(raw_html, "html.parser")
                body_text = soup.get_text(separator=" ", strip=True)[:800]

                title = entry.get("title", "Новость рынка коммерческой недвижимости")
                candidates.append({
                    "title": title,
                    "url": url,
                    "body": body_text,
                    "image": image_url,
                    "source": source_name,
                    "published": published
                })
        except Exception as e:
            print(f"⚠️ Ошибка парсинга {feed_url}: {e}")
            continue

    if not candidates:
        return None

    # Сортируем по свежести и берём из топ-5 свежих
    candidates.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return random.choice(candidates[:min(5, len(candidates))])

# ============ ПРОМПТЫ ============

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
5) Блок инсайтов: 3-5 пунктов с эмодзи (🔹 ✅ ⚠️ 📊 💡) и жирным подзаголовком:
🔹 *Подзаголовок.* Раскрытие мысли.
6) Пустая строка.
7) Вывод: начни с жирного *Вывод:* и дай 1-2 предложения.
8) Пустая строка.
9) Финальная строка-призыв:
⚖️ Хотите разобрать вашу ситуацию? Пишите юристу: @KomInvest_Crimea_bot

ПРАВИЛА:
- Объем 900-1400 знаков.
- Жирный текст ТОЛЬКО через *звёздочки*. Символы # и _ не используй.
- Эмодзи умеренно: 4-7 штук.
- Стиль деловой, экспертный.
"""

SHORT_PROMPT = """
Ты — маркетолог и эксперт по коммерческой недвижимости Крыма.
Напиши КОРОТКИЙ продающий пост на тему: {topic}

СТРОГИЙ ФОРМАТ ОТВЕТА:
1) Жирный хук с эмодзи, до 55 знаков:
*💰 Пример хука*
2) Пустая строка.
3) Продающий абзац (2-3 предложения), главную выгоду выдели жирным.
4) Пустая строка.
5) 3 буллета с жирными подзаголовками и конкретикой:
🔹 *Подзаголовок 1.* Раскрытие.
✅ *Подзаголовок 2.* Раскрытие.
📊 *Подзаголовок 3.* Раскрытие.
6) Пустая строка.
7) Мини-кейс (1 предложение): реалистичная ситуация инвестора.
8) Пустая строка.
9) Призыв со ссылкой:
👉 [Получить консультацию юриста](https://t.me/KomInvest_Crimea_bot)

ПРАВИЛА:
- Объем 650-850 знаков.
- Жирный ТОЛЬКО через *звёздочки*. Символы # и _ не используй.
- Эмодзи: 4-6 штук.
"""

NEWS_PROMPT = """
Ты — опытный редактор делового Telegram-канала "КомИнвест" и эксперт по коммерческой недвижимости.
Тебе дали свежую новость с портала CRE.ru. Перепиши её для Telegram — своими словами, с экспертной оценкой.

Заголовок: {title}
Текст новости: {body}

СТРОГИЙ ФОРМАТ ОТВЕТА:
1) Первая строка — жирный заголовок с эмодзи 📰 или 📈 или 🏢 (одним), до 70 знаков:
*📰 Заголовок новости своими словами*
2) Пустая строка.
3) Краткая суть новости (2-3 предложения, своими словами, без копирования фраз источника).
4) Пустая строка.
5) Блок "Что это значит для инвестора" — 2-3 пункта с эмодзи и жирными подзаголовками:
💡 *Возможность.* Как инвестор может использовать эту информацию.
⚠️ *Риск.* На что обратить внимание.
📊 *Тренд.* Какое направление рынка подтверждает новость.
6) Пустая строка.
7) Короткий экспертный вывод (1-2 предложения от лица редакции КомИнвест).
8) Пустая строка.
9) Финальный призыв:
⚖️ Обсудим, как применить это к вашему объекту? @KomInvest_Crimea_bot

ПРАВИЛА:
- Объем 700-1100 знаков.
- Жирный ТОЛЬКО через *звёздочки*. Символы # и _ не используй.
- Перепиши новость своими словами, НЕ копируй фразы из источника.
- Добавь экспертную ценность — почему это важно для инвестора.
- Стиль деловой, уверенный.
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
            text = (resp.choices[0].message.content or '').strip()
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

def generate_news(news_data):
    text = call_ai(NEWS_PROMPT.format(title=news_data["title"], body=news_data["body"]))
    if not text:
        raise Exception("❌ AI недоступен (новость). Пост НЕ опубликован.")

    # Добавляем строку с источником в Markdown
    source_line = f"\n\n🔗 Источник: [{news_data['source']}]({news_data['url']})"
    return (text + source_line).strip(), news_data.get("image"), news_data["url"]