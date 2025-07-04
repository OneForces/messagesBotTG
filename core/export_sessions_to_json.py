import os
import base64
import json
from telethon.sync import TelegramClient
from telethon.sessions import SQLiteSession

# Задай свои API ID и HASH
API_ID = 123456  # ← замени на свои
API_HASH = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # ← замени на свои

SESSIONS_FOLDER = "sessions"

os.makedirs(SESSIONS_FOLDER, exist_ok=True)
session_files = [f for f in os.listdir(SESSIONS_FOLDER) if f.endswith(".session")]

if not session_files:
    print("❌ Нет .session файлов в папке sessions/")
    exit()

for file in session_files:
    session_name = os.path.splitext(file)[0]
    session_path = os.path.join(SESSIONS_FOLDER, session_name)

    try:
        client = TelegramClient(session_path, API_ID, API_HASH)
        client.connect()
        session: SQLiteSession = client.session

        if not session.auth_key:
            print(f"⚠️ Пропущено {file} — нет ключа авторизации.")
            continue

        export_data = {
            "api_id": API_ID,
            "api_hash": API_HASH,
            "phone": client.get_me().phone if client.get_me() else None,
            "auth_key": base64.b64encode(session.auth_key.key).decode(),
            "dc_id": session.dc_id
        }

        output_path = os.path.join(SESSIONS_FOLDER, f"{session_name}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Экспортировано: {output_path}")
        client.disconnect()

    except Exception as e:
        print(f"❌ Ошибка при экспорте {file}: {e}")
