import feedparser
from datetime import datetime, timezone, timedelta

RSS_FEEDS = [
    "https://cre.ru/rss/rss_news.xml",
    "https://cre.ru/rss/rss_analitics.xml",
    "https://cre.ru/rss/rss_expert.xml",
    "https://cre.ru/rss/rss_all.xml"
]

MSK = timezone(timedelta(hours=3))
now = datetime.now(MSK)

for url in RSS_FEEDS:
    print(f"\n=== Тестируем {url} ===")
    try:
        feed = feedparser.parse(url)
        if not feed.entries:
            print("❌ Пустая лента")
            continue
        
        print(f"✅ Найдено записей: {len(feed.entries)}")
        
        # Показываем первые 3 записи
        for i, entry in enumerate(feed.entries[:3]):
            title = entry.get("title", "Без заголовка")
            link = entry.get("link", "")
            
            # Проверяем дату
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                import time
                published = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
                age_hours = (now - published).total_seconds() / 3600
                age_str = f"{age_hours:.1f} ч. назад"
            else:
                age_str = "дата неизвестна"
            
            print(f"  {i+1}. {title[:60]}... ({age_str})")
            print(f"     {link}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")