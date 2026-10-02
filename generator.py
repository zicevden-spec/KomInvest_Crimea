# -*- coding: utf-8 -*-
import os
from openai import OpenAI
from dotenv import load_dotenv

# Эта строка заставляет Python читать файл .env
load_dotenv()

# Берем ключ из переменной окружения
API_KEY = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

def generate_post():
    prompt = """
    Ты — эксперт по коммерческой недвижимости и юрист. 
    Пишешь пост для Telegram-канала "КомИнвест" (Коммерческая недвижимость Крыма).
    
    Тема поста (выбери одну случайно): 
    1. Юридические риски при покупке офиса/склада в Крыму.
    2. Как проверить объект до внесения аванса.
    3. Доходность коммерческой недвижимости vs жилая.
    4. Ошибки инвесторов при покупке стрит-ритейла.
    
    Требования:
    - Объем: 600-900 знаков.
    - Стиль: деловой, спокойный, экспертный, без воды и капса.
    - Структура: Цепляющий заголовок -> Суть проблемы -> 3 пункта решения/риска -> Вывод.
    - В конце добавь призыв: "Хотите проверить объект или подобрать вариант? Пишите нашему юристу."
    - Не используй символы # и *.
    """
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Ошибка генерации контента: {e}. Проверьте API ключ в настройках."

if __name__ == "__main__":
    print(generate_post())