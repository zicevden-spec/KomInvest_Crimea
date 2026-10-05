# -*- coding: utf-8 -*-
import random
import time
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

MSK = timezone(timedelta(hours=3))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}

RSS_FEEDS = [
    ("https://cre.ru/rss/rss_news.xml", "CRE.ru"),
    ("https://cre.ru/rss/rss_analitics.xml", "CRE.ru Аналитика"),
    ("https://cre.ru/rss/rss_all.xml", "CRE.ru"),
    ("https://realty.rbc.ru/rss/news", "РБК Недвижимость"),
    ("https://www.kommersant.ru/rss/theme/12", "Коммерсантъ Недвижимость"),
]

def fetch_rss_news(history_titles, max_age_hours=168):
    """
    history_titles: список заголовков уже опубликованных новостей.
    Возвращает dict(title, url, body, image, source, published) или None.
    """
    now = datetime.now(MSK)
    candidates = []

    for feed_url, source_name in RSS_FEEDS:
        try:
            r = requests.get(feed_url, headers=HEADERS, timeout=20)
            print(f"📡 Лента {source_name}: HTTP {r.status_code}, байт: {len(r.content)}")
            if r.status_code != 200:
                continue
            feed = feedparser.parse(r.content)
            entries = feed.entries
            print(f"   записей в ленте: {len(entries)}")

            skipped_history = 0
            skipped_old = 0

            for entry in entries[:10]:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                if not title or not url:
                    continue
                # Дедупликация ПО ЗАГОЛОВКУ (у cre.ru битые link)
                if title in history_titles:
                    skipped_history += 1
                    continue

                published = None
                for attr in ("published_parsed", "updated_parsed"):
                    st = getattr(entry, attr, None)
                    if st:
                        published = datetime.fromtimestamp(time.mktime(st), tz=timezone.utc)
                        break
                if published:
                    age = (now - published).total_seconds() / 3600
                    if age > max_age_hours:
                        skipped_old += 1
                        continue

                # Картинка: media_content -> enclosures -> <img> в описании
                image_url = None
                mc = getattr(entry, "media_content", None)
                if mc:
                    image_url = mc[0].get("url")
                if not image_url and getattr(entry, "enclosures", None):
                    for enc in entry.enclosures:
                        if (enc.get("type") or "").startswith("image/"):
                            image_url = enc.get("url")
                            break
                if not image_url:
                    soup = BeautifulSoup(entry.get("summary", "") or entry.get("description", ""), "html.parser")
                    img = soup.find("img")
                    if img and img.get("src"):
                        image_url = img["src"]

                soup = BeautifulSoup(entry.get("summary", "") or entry.get("description", ""), "html.parser")
                body = soup.get_text(separator=" ", strip=True)[:800]

                candidates.append({
                    "title": title, "url": url, "body": body,
                    "image": image_url, "source": source_name, "published": published
                })

            print(f"   пропущено: уже публиковали={skipped_history}, старые={skipped_old}, прошло={len(candidates)}")
        except Exception as e:
            print(f"⚠️ Ошибка ленты {source_name}: {e}")
            continue

    if not candidates:
        print("⚠️ RSS: свежих уникальных новостей не найдено ни в одной ленте")
        return None

    candidates.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    pick = random.choice(candidates[:min(5, len(candidates))])
    print(f"✅ Выбрана новость: {pick['title'][:60]}... ({pick['source']})")
    return pick