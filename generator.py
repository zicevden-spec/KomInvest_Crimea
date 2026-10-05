# -*- coding: utf-8 -*-
import os, random, requests, feedparser, time, json
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

CATEGORY_BY_HOUR = {10: "real_estate", 12: "finance", 14: "news", 16: "legal", 18: "strategy", 20: "news"}
POST_TYPE_BY_HOUR = {10: "longread", 12: "short", 14: "news", 16: "longread", 18: "short", 20: "news"}

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
    hour = datetime.now(MSK).hour
    force = os.getenv("FORCE_POST_TYPE", "")
    if force in ("longread", "short", "news"):
        return force, CATEGORY_BY_HOUR.get(hour, "real_estate")
    if hour in POST_TYPE_BY_HOUR:
        return POST_TYPE_BY_HOUR[hour], CATEGORY_BY_HOUR[hour]
    return "short", "finance"

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
            print(f"⚠️ Ошибка ленты {source_name}: {e}")
    
    if not candidates: return None
    candidates.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return random.choice(candidates[:min(5, len(candidates))])

LONGREAD_PROMPT = """
Ты — эксперт по коммерческой недвижимости. Напиши ЛОНГРИД на тему: {topic}
Жанр: {ctype}. Инструкция: {instruction}
Формат: Жирный заголовок с эмодзи -> Суть (жирный термин) -> 3-5 инсайтов с эмодзи -> *Вывод:*
Правила: 900-1400 знаков, жирный ТОЛЬКО через *звёздочки*, без # и _.
ЗАПРЕЩЕНО добавлять призывы, @упоминания и ссылки в конце поста. Пост заканчивается на выводе.
"""

SHORT_PROMPT = """
Ты — маркетолог по коммерческой недвижимости Крыма. Напиши КОРОТКИЙ пост на тему: {topic}
Формат: Жирный хук с эмодзи -> Продающий абзац (жирная выгода) -> 3 буллета с подзаголовками -> Мини-кейс (1 предложение)
Правила: 650-850 знаков, жирный ТОЛЬКО через *звёздочки*, без # и _.
ЗАПРЕЩЕНО добавлять призывы, @упоминания и ссылки в конце поста. Пост заканчивается на мини-кейсе.
"""

NEWS_PROMPT = """
Ты — главный редактор канала "КомИнвест". Напиши ОРИГИНАЛЬНЫЙ экспертный пост по рыночному инфоповоду.
Инфоповод: {title}
Факты: {body}

СТРОГИЙ ФОРМАТ:
1) Жирный заголовок с эмодзи (до 60 знаков):
*📈 Заголовок-инсайт*
🌊
2) Пустая строка.
3) Суть: 2-3 предложения своими словами. Не пиши "по данным новостей".
4) Пустая строка.
5) Что это значит для инвестора (2 пункта):
💡 *Возможность.* Как это использовать.
⚠️ *Риск.* На что обратить внимание.
6) Пустая строка.
7) Экспертный вывод (1-2 предложения).
8) Пустая строка.
9) Призыв:
⚖️ Обсудим, как применить это к вашему объекту? Пишите юристу: @KomInvest_Crimea_bot

Правила: 700-1000 знаков, жирный ТОЛЬКО через *звёздочки*, никаких ссылок на источники.
ВАЖНО: Пост ДОЛЖЕН заканчиваться экспертным выводом. ЗАПРЕЩЕНО добавлять в конце: призывы, @упоминания бота, ссылки t.me, фразы типа "пишите юристу", "обсудим вашу ситуацию" и подобные. Никаких CTA — футер добавляется отдельно системой.
"""


def clean_ai_text(text):
    """Удаляет из текста AI любые мусорные призывы, @упоминания и ссылки"""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        low = line.lower()
        # Пропускаем строки с мусором
        if any(x in low for x in [
            '@kominvest', 'пишите юристу', 'обсудим', 'вашему объекту',
            'нашему юристу', 'получить консультацию', 'связаться',
            't.me/kominvest', 'задать вопрос', 'узнать подробнее'
        ]):
            continue
        cleaned.append(line)
    
    # Убираем пустые строки в конце
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()
    
    return '\n'.join(cleaned)\n\ndef call_ai(prompt):
    for model in ["openai/gpt-oss-120b", "qwen/qwen3.6-27b", "google/gemma-2-9b-it:free"]:
        try:
            print(f"🔄 Пробуем {model}...")
            resp = or_client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}],
                temperature=0.8, max_tokens=1600,
                extra_headers={"HTTP-Referer": CHANNEL_URL, "X-Title": "KomInvest"}
            )
            text = (resp.choices[0].message.content or "").strip()
            if len(text) > 200 and "не могу" not in text.lower():
                print(f"✅ {model} сработал!")
                return text
        except Exception as e:
            print(f"⚠️ {model} ошибка: {e}")
    return None

def generate_longread(topic, ctype):
    text = call_ai(LONGREAD_PROMPT.format(topic=topic, ctype=ctype, instruction=TYPE_INSTRUCTIONS.get(ctype, "")))
    if not text: raise Exception("❌ AI недоступен (лонгрид)")
    return text

def generate_short(topic, category):
    text = call_ai(SHORT_PROMPT.format(topic=topic))
    if not text: raise Exception("❌ AI недоступен (короткий)")
    return text.strip(), generate_photo_query(topic, category)

def generate_news(news_data):
    text = call_ai(NEWS_PROMPT.format(title=news_data["title"], body=news_data["body"]))
    if not text: raise Exception("❌ AI недоступен (новость)")
    return text.strip(), news_data.get("image")