# -*- coding: utf-8 -*-
import os, random, requests, feedparser, time
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
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

CONTENT_TYPES = ["советы", "кейс", "объяснение", "статистика", "разбор_мифа"]
TYPE_INSTRUCTIONS = {
    "советы": "Напиши 3-5 практических советов.",
    "кейс": "Напиши короткую историю из практики.",
    "объяснение": "Объясни простыми словами сложный термин.",
    "статистика": "Напиши пост с цифрами и фактами.",
    "разбор_мифа": "Напиши в формате: МИФ и РЕАЛЬНОСТЬ."
}

# 4 коротких RSS + 2 лонгрида (обед и вечер)
POST_TYPE_BY_HOUR = {10: "news", 12: "news", 14: "longread", 16: "news", 18: "news", 20: "longread"}

RSS_FEEDS = [
    ("https://cre.ru/rss/rss_news.xml", "CRE.ru"),
    ("https://cre.ru/rss/rss_analitics.xml", "CRE.ru Аналитика"),
    ("https://realty.rbc.ru/rss/news", "РБК Недвижимость"),
]

PHOTO_STYLES = ["luxury", "aerial view", "minimalist", "modern glass", "night lighting", "architectural detail"]
PHOTO_OBJECTS = {
    "real_estate": ["office building", "business center"],
    "finance": ["financial chart", "investment portfolio"],
    "legal": ["legal documents", "contract signing"],
    "strategy": ["strategic meeting", "business planning"],
    "news": ["modern office exterior", "business center skyline"]
}

def get_schedule():
    now = datetime.now(MSK)
    hour = now.hour
    day = now.day
    force = os.getenv("FORCE_POST_TYPE", "")
    ptype = force if force in ("longread", "news") else POST_TYPE_BY_HOUR.get(hour, "news")
    if ptype == "longread":
        if hour < 17:
            cat = ["real_estate", "legal"][day % 2]
        else:
            cat = ["finance", "strategy"][day % 2]
    else:
        cat = "news"
    return ptype, cat

def pick_topic(category):
    return random.choice(ALL_TOPICS.get(category, ALL_TOPICS["real_estate"]))

def generate_photo_query(topic, category):
    obj = random.choice(PHOTO_OBJECTS.get(category, PHOTO_OBJECTS["real_estate"]))
    style = random.choice(PHOTO_STYLES)
    topic_words = topic.lower().replace(":", "").replace("?", "").split()[:3]
    return f"{style} {obj}, {' '.join(topic_words)}"

def fetch_rss_news(history_titles, max_age_hours=168):
    now = datetime.now(MSK)
    candidates = []
    for feed_url, source_name in RSS_FEEDS:
        try:
            r = requests.get(feed_url, headers=HEADERS, timeout=20)
            if r.status_code != 200: continue
            feed = feedparser.parse(r.content)
            for entry in feed.entries[:10]:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                if not title or not url or title in history_titles: continue
                published = None
                for attr in ("published_parsed", "updated_parsed"):
                    st = getattr(entry, attr, None)
                    if st:
                        published = datetime.fromtimestamp(time.mktime(st), tz=timezone.utc)
                        break
                if published and (now - published).total_seconds() / 3600 > max_age_hours: continue
                image_url = None
                mc = getattr(entry, "media_content", None)
                if mc: image_url = mc[0].get("url")
                if not image_url:
                    soup = BeautifulSoup(entry.get("summary", "") or entry.get("description", ""), "html.parser")
                    img = soup.find("img")
                    if img and img.get("src"): image_url = img["src"]
                soup = BeautifulSoup(entry.get("summary", "") or entry.get("description", ""), "html.parser")
                body = soup.get_text(separator=" ", strip=True)[:800]
                candidates.append({"title": title, "url": url, "body": body, "image": image_url, "source": source_name, "published": published})
        except Exception as e:
            print(f"Ошибка ленты {source_name}: {e}")
    if not candidates: return None
    candidates.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return random.choice(candidates[:min(5, len(candidates))])

def clean_ai_text(text):
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        low = line.lower()
        if any(x in low for x in [
            '@kominvest', 'пишите юристу', 'обсудим', 'вашему объекту',
            'нашему юристу', 'получить консультацию', 'связаться',
            't.me/kominvest', 'задать вопрос', 'узнать подробнее'
        ]):
            continue
        cleaned.append(line)
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()
    return '\n'.join(cleaned)

LONGREAD_PROMPT = """
Ты — эксперт по коммерческой недвижимости. Напиши ЛОНГРИД на тему: {topic}
Жанр: {ctype}. Инструкция: {instruction}
Формат: Жирный заголовок с эмодзи -> Суть (жирный термин) -> 3-5 инсайтов с эмодзи -> *Вывод:*
Правила: 900-1400 знаков, жирный ТОЛЬКО через *звёздочки*, без # и _.
ЗАПРЕЩЕНО добавлять призывы, @упоминания и ссылки в конце поста. Пост заканчивается на выводе.
"""

NEWS_PROMPT = """
Ты — главный редактор канала "КомИнвест". Напиши КОРОТКИЙ экспертный пост по рыночному инфоповоду.
Инфоповод: {title}
Факты: {body}

СТРОГИЙ ФОРМАТ:
1) Жирный заголовок с эмодзи (до 50 знаков):
*📈 Заголовок-инсайт*
2) Пустая строка.
3) Суть своими словами: 2 предложения. Не пиши "по данным новостей" и не упоминай источники.
4) Пустая строка.
5) Один пункт для инвестора:
💡 *Вывод для инвестора.* Одно-два предложения с практической пользой.

Правила:
- СТРОГО 450-700 знаков. Это критично: пост публикуется с фотографией, подпись к фото ограничена 1024 символами.
- Жирный ТОЛЬКО через *звёздочки*, без # и _.
- ЗАПРЕЩЕНО: призывы, @упоминания, ссылки t.me, фразы "пишите юристу", "обсудим". Пост заканчивается на выводе для инвестора.
"""

def call_ai(prompt):
    for model in ["openai/gpt-oss-120b", "qwen/qwen3.6-27b", "google/gemma-2-9b-it:free"]:
        try:
            print(f"Пробуем {model}...")
            resp = or_client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}],
                temperature=0.8, max_tokens=1600,
                extra_headers={"HTTP-Referer": CHANNEL_URL, "X-Title": "KomInvest"}
            )
            text = (resp.choices[0].message.content or "").strip()
            if len(text) > 150 and "не могу" not in text.lower():
                print(f"{model} сработал!")
                return text
        except Exception as e:
            print(f"{model} ошибка: {e}")
    return None

def generate_longread(topic, ctype):
    text = call_ai(LONGREAD_PROMPT.format(topic=topic, ctype=ctype, instruction=TYPE_INSTRUCTIONS.get(ctype, "")))
    if not text: raise Exception("AI недоступен (лонгрид)")
    return clean_ai_text(text)

def generate_news(news_data):
    text = call_ai(NEWS_PROMPT.format(title=news_data["title"], body=news_data["body"]))
    if not text: raise Exception("AI недоступен (новость)")
    return clean_ai_text(text).strip(), news_data.get("image")