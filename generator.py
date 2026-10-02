# -*- coding: utf-8 -*-
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# Список бесплатных рабочих моделей на OpenRouter
WORKING_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "qwen/qwen-2.5-7b-instruct:free",
    "microsoft/phi-3-mini-128k-instruct:free"
]

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
    
    for model in WORKING_MODELS:
        try:
            print(f"🔄 Пробуем модель: {model}...")
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=800,
                extra_headers={"HTTP-Referer": "https://t.me/KomInvest_Crimea", "X-Title": "KomInvest Bot"}
            )
            text = response.choices[0].message.content.strip()
            print(f"✅ Модель {model} сработала!")
            return text
        except Exception as e:
            print(f"⚠️ Модель {model} недоступна: {e}. Пробуем следующую...")
            continue
            
    return "⚠️ Все модели временно недоступны. Попробуйте позже."

if __name__ == "__main__":
    print(generate_post())