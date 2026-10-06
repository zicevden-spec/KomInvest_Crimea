# -*- coding: utf-8 -*-
import os, json, base64, requests
from datetime import datetime, timezone, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

REPO = os.getenv("GH_REPO", "zicevden-spec/KomInvest_Crimea")
TOKEN = os.getenv("GITHUB_PAT", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))
MSK = timezone(timedelta(hours=3))
API = f"https://api.github.com/repos/{REPO}/contents/data"

def fetch_json(name, default):
    if not TOKEN: return default
    try:
        r = requests.get(f"{API}/{name}",
                         headers={"Authorization": f"token {TOKEN}"}, timeout=30)
        if r.status_code == 200:
            return json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
    except Exception as e:
        print(f"fetch error {name}: {e}")
    return default

def main():
    leads = fetch_json("leads.json", [])
    fresh = [l for l in leads if l.get("status", "new") in ("new", "новая", "")]
    if not fresh:
        print("Неотработанных лидов нет — напоминание не отправляем.")
        return

    now = datetime.now(MSK)
    lines = [f"⏰ 19:00 — неотработанных лидов: {len(fresh)}", ""]
    for l in fresh[-10:]:
        age = ""
        try:
            dt = datetime.strptime(l["date"], "%Y-%m-%d %H:%M").replace(tzinfo=MSK)
            h = int((now - dt).total_seconds() // 3600)
            age = f" | ждёт {h} ч"
        except Exception:
            pass
        lines.append(f"#{l['id']} | {l['name']} | {l['phone']}{age}")
    lines.append("")
    lines.append("Открой бота: /admin → 📋 Лиды → поставь статус после звонка.")
    text = "\n".join(lines)

    admins = fetch_json("admins.json", {"super": [ADMIN_ID], "admins": []})
    uids = list(dict.fromkeys(admins.get("super", []) + admins.get("admins", [])))
    for uid in uids:
        try:
            r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                              json={"chat_id": uid, "text": text}, timeout=30)
            print(f"Отправлено админу {uid}: {r.status_code}")
        except Exception as e:
            print(f"send error {uid}: {e}")
    print(f"Напоминание отправлено {len(uids)} админам.")

main()