# -*- coding: utf-8 -*-
import os, json, base64, requests

REPO = os.getenv("GH_REPO", "zicevden-spec/KomInvest_Crimea")
TOKEN = os.getenv("GITHUB_PAT", "")
BRANCH = "main"
API = f"https://api.github.com/repos/{REPO}/contents/data"

def _headers():
    return {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}

def local_path(name):
    os.makedirs("data", exist_ok=True)
    return os.path.join("data", name)

def read_local(name, default):
    p = local_path(name)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return default

def write_local(name, data):
    with open(local_path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def pull(name, default):
    if not TOKEN: return read_local(name, default)
    try:
        r = requests.get(f"{API}/{name}", headers=_headers(), timeout=30)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode("utf-8")
            data = json.loads(content)
            write_local(name, data)
            print(f"☁️ Синхронизировано с GitHub: data/{name}")
            return data
    except Exception as e:
        print(f"⚠️ gh pull {name}: {e}")
    return read_local(name, default)

def push(name, data):
    write_local(name, data)
    if not TOKEN:
        print("⚠️ Нет GITHUB_PAT — сохранено только локально")
        return False
    sha = None
    try:
        r = requests.get(f"{API}/{name}", headers=_headers(), timeout=30)
        if r.status_code == 200: sha = r.json()["sha"]
    except Exception: pass
    payload = {
        "message": f"data: update {name} [skip ci]",
        "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")).decode(),
        "branch": BRANCH,
    }
    if sha: payload["sha"] = sha
    try:
        r = requests.put(f"{API}/{name}", headers=_headers(), json=payload, timeout=30)
        if r.status_code in (200, 201):
            print(f"☁️ Сохранено в GitHub: data/{name}")
            return True
        print(f"⚠️ gh push {name}: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"⚠️ gh push {name}: {e}")
    return False

def sync_all(defaults):
    for name, default in defaults.items():
        pull(name, default)