# -*- coding: utf-8 -*-
import os
import random
import requests
import feedparser
import time
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

CONTENT_TYPES = ["￱￮￢￥￲￻", "￪￥￩￱", "￮￡￺￿￱￭￥￭￨￥", "￱￲￠￲￨￱￲￨￪￠", "￰￠￧￡￮￰_￬￨￴￠"]
TYPE_INSTRUCTIONS = {
    "￱￮￢￥￲￻": "ￍ￠￯￨￸￨ 3-5 ￯￰￠￪￲￨￷￥￱￪￨￵ ￱￮￢￥￲￮￢ ￤￫￿ ￨￭￢￥￱￲￮￰￠.",
    "￪￥￩￱": "ￍ￠￯￨￸￨ ￪￮￰￮￲￪￳￾ ￨￱￲￮￰￨￾ (￪￥￩￱) ￨￧ ￯￰￠￪￲￨￪￨.",
    "￮￡￺￿￱￭￥￭￨￥": "ￎ￡￺￿￱￭￨ ￯￰￮￱￲￻￬￨ ￱￫￮￢￠￬￨ ￱￫￮￦￭￻￩ ￲￥￰￬￨￭.",
    "￱￲￠￲￨￱￲￨￪￠": "ￍ￠￯￨￸￨ ￯￮￱￲ ￱ ￶￨￴￰￠￬￨ ￨ ￴￠￪￲￠￬￨.",
    "￰￠￧￡￮￰_￬￨￴￠": "ￍ￠￯￨￸￨ ￢ ￴￮￰￬￠￲￥: ￌ￈ￔ ￨ ￐ￅ￀ￋￜￍￎ￑ￒￜ."
}

CATEGORY_BY_HOUR = {10: "real_estate", 12: "finance", 14: "news", 16: "legal", 18: "strategy", 20: "news"}
POST_TYPE_BY_HOUR = {10: "longread", 12: "short", 14: "news", 16: "longread", 18: "short", 20: "news"}

RSS_FEEDS = [
    ("https://cre.ru/rss/rss_news.xml", "CRE.ru"),
    ("https://cre.ru/rss/rss_analitics.xml", "CRE.ru ￀￭￠￫￨￲￨￪￠"),
    ("https://realty.rbc.ru/rss/news", "￐￁ￊ ￍ￥￤￢￨￦￨￬￮￱￲￼"),
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
            print(f"?? ￎ￸￨￡￪￠ ￫￥￭￲￻ {source_name}: {e}")
    
    if not candidates: return None
    candidates.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return random.choice(candidates[:min(5, len(candidates))])

LONGREAD_PROMPT = """
ￒ￻ ﾗ �￪￱￯￥￰￲ ￯￮ ￪￮￬￬￥￰￷￥￱￪￮￩ ￭￥￤￢￨￦￨￬￮￱￲￨. ￍ￠￯￨￸￨ ￋￎￍￃ￐￈ￄ ￭￠ ￲￥￬￳: {topic}
ￆ￠￭￰: {ctype}. ￈￭￱￲￰￳￪￶￨￿: {instruction}
ￔ￮￰￬￠￲: ￆ￨￰￭￻￩ ￧￠￣￮￫￮￢￮￪ ￱ �￬￮￤￧￨ -> ￑￳￲￼ (￦￨￰￭￻￩ ￲￥￰￬￨￭) -> 3-5 ￨￭￱￠￩￲￮￢ ￱ �￬￮￤￧￨ -> *ￂ￻￢￮￤:* -> ￏ￰￨￧￻￢: "?? ￕ￮￲￨￲￥ ￰￠￧￮￡￰￠￲￼ ￢￠￸￳ ￱￨￲￳￠￶￨￾? ￏ￨￸￨￲￥ ￾￰￨￱￲￳: @KomInvest_Crimea_bot"
ￏ￰￠￢￨￫￠: 900-1400 ￧￭￠￪￮￢, ￦￨￰￭￻￩ ￒￎￋￜￊￎ ￷￥￰￥￧ *￧￢ﾸ￧￤￮￷￪￨*, ￡￥￧ # ￨ _.
"""

SHORT_PROMPT = """
ￒ￻ ﾗ ￬￠￰￪￥￲￮￫￮￣ ￯￮ ￪￮￬￬￥￰￷￥￱￪￮￩ ￭￥￤￢￨￦￨￬￮￱￲￨ ￊ￰￻￬￠. ￍ￠￯￨￸￨ ￊￎ￐ￎￒￊ￈￉ ￯￮￱￲ ￭￠ ￲￥￬￳: {topic}
ￔ￮￰￬￠￲: ￆ￨￰￭￻￩ ￵￳￪ ￱ �￬￮￤￧￨ -> ￏ￰￮￤￠￾￹￨￩ ￠￡￧￠￶ (￦￨￰￭￠￿ ￢￻￣￮￤￠) -> 3 ￡￳￫￫￥￲￠ ￱ ￯￮￤￧￠￣￮￫￮￢￪￠￬￨ -> ￌ￨￭￨-￪￥￩￱ (1 ￯￰￥￤￫￮￦￥￭￨￥) -> ￏ￰￨￧￻￢: "?? [ￏ￮￫￳￷￨￲￼ ￪￮￭￱￳￫￼￲￠￶￨￾ ￾￰￨￱￲￠](https://t.me/KomInvest_Crimea_bot)"
ￏ￰￠￢￨￫￠: 650-850 ￧￭￠￪￮￢, ￦￨￰￭￻￩ ￒￎￋￜￊￎ ￷￥￰￥￧ *￧￢ﾸ￧￤￮￷￪￨*, ￡￥￧ # ￨ _.
"""

NEWS_PROMPT = """
ￒ￻ ﾗ ￣￫￠￢￭￻￩ ￰￥￤￠￪￲￮￰ ￪￠￭￠￫￠ "ￊ￮￬￈￭￢￥￱￲". ￍ￠￯￨￸￨ ￎ￐￈ￃ￈ￍ￀ￋￜￍￛ￉ �￪￱￯￥￰￲￭￻￩ ￯￮￱￲ ￯￮ ￰￻￭￮￷￭￮￬￳ ￨￭￴￮￯￮￢￮￤￳.
￈￭￴￮￯￮￢￮￤: {title}
ￔ￠￪￲￻: {body}

￑ￒ￐ￎￃ￈￉ ￔￎ￐ￌ￀ￒ:
1) ￆ￨￰￭￻￩ ￧￠￣￮￫￮￢￮￪ ￱ �￬￮￤￧￨ (￤￮ 60 ￧￭￠￪￮￢):
*?? ￇ￠￣￮￫￮￢￮￪-￨￭￱￠￩￲*
??
2) ￏ￳￱￲￠￿ ￱￲￰￮￪￠.
3) ￑￳￲￼: 2-3 ￯￰￥￤￫￮￦￥￭￨￿ ￱￢￮￨￬￨ ￱￫￮￢￠￬￨. ￍ￥ ￯￨￸￨ "￯￮ ￤￠￭￭￻￬ ￭￮￢￮￱￲￥￩".
4) ￏ￳￱￲￠￿ ￱￲￰￮￪￠.
5) ￗ￲￮ �￲￮ ￧￭￠￷￨￲ ￤￫￿ ￨￭￢￥￱￲￮￰￠ (2 ￯￳￭￪￲￠):
?? *ￂ￮￧￬￮￦￭￮￱￲￼.* ￊ￠￪ �￲￮ ￨￱￯￮￫￼￧￮￢￠￲￼.
?? *￐￨￱￪.* ￍ￠ ￷￲￮ ￮￡￰￠￲￨￲￼ ￢￭￨￬￠￭￨￥.
6) ￏ￳￱￲￠￿ ￱￲￰￮￪￠.
7) ￝￪￱￯￥￰￲￭￻￩ ￢￻￢￮￤ (1-2 ￯￰￥￤￫￮￦￥￭￨￿).
8) ￏ￳￱￲￠￿ ￱￲￰￮￪￠.
9) ￏ￰￨￧￻￢:
?? ￎ￡￱￳￤￨￬, ￪￠￪ ￯￰￨￬￥￭￨￲￼ �￲￮ ￪ ￢￠￸￥￬￳ ￮￡￺￥￪￲￳? ￏ￨￸￨￲￥ ￾￰￨￱￲￳: @KomInvest_Crimea_bot

ￏ￰￠￢￨￫￠: 700-1000 ￧￭￠￪￮￢, ￦￨￰￭￻￩ ￒￎￋￜￊￎ ￷￥￰￥￧ *￧￢ﾸ￧￤￮￷￪￨*, ￭￨￪￠￪￨￵ ￱￱￻￫￮￪ ￭￠ ￨￱￲￮￷￭￨￪￨.
"""

def call_ai(prompt):
    for model in ["openai/gpt-oss-120b", "qwen/qwen3.6-27b", "google/gemma-2-9b-it:free"]:
        try:
            print(f"?? ￏ￰￮￡￳￥￬ {model}...")
            resp = or_client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}],
                temperature=0.8, max_tokens=1600,
                extra_headers={"HTTP-Referer": CHANNEL_URL, "X-Title": "KomInvest"}
            )
            text = (resp.choices[0].message.content or "").strip()
            if len(text) > 200 and "￭￥ ￬￮￣￳" not in text.lower():
                print(f"? {model} ￱￰￠￡￮￲￠￫!")
                return text
        except Exception as e:
            print(f"?? {model} ￮￸￨￡￪￠: {e}")
    return None

def generate_longread(topic, ctype):
    text = call_ai(LONGREAD_PROMPT.format(topic=topic, ctype=ctype, instruction=TYPE_INSTRUCTIONS.get(ctype, "")))
    if not text: raise Exception("? AI ￭￥￤￮￱￲￳￯￥￭ (￫￮￭￣￰￨￤)")
    return text

def generate_short(topic, category):
    text = call_ai(SHORT_PROMPT.format(topic=topic))
    if not text: raise Exception("? AI ￭￥￤￮￱￲￳￯￥￭ (￪￮￰￮￲￪￨￩)")
    return text.strip(), generate_photo_query(topic, category)

def generate_news(news_data):
    text = call_ai(NEWS_PROMPT.format(title=news_data["title"], body=news_data["body"]))
    if not text: raise Exception("? AI ￭￥￤￮￱￲￳￯￥￭ (￭￮￢￮￱￲￼)")
    return text.strip(), news_data.get("image")