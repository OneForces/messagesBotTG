# core/account_manager.py

import asyncio
from telethon import TelegramClient, errors

API_ID = 12345678  # ← замени на свой
API_HASH = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'  # ← замени на свой

async def check_account_status(session_path, proxy=None):
    try:
        proxy_config = None
        if proxy:
            ip, port, user, pwd, ptype = proxy
            if ptype == "socks5":
                proxy_config = ('socks5', ip, port, True, user, pwd) if user else ('socks5', ip, port)

        client = TelegramClient(session_path.replace('.session', ''), API_ID, API_HASH, proxy=proxy_config)
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return 'not_authorized', '⛔ Не авторизован'

        me = await client.get_me()
        result_text = f"{me.first_name or ''} ({me.username or me.phone})"

        try:
            entity = await client.get_entity("SpamBot")
            await client.send_message(entity, "/start")
            await asyncio.sleep(2)

            messages = await client.get_messages(entity, limit=1)
            text = messages[0].message.lower()

            if "ограничения отсутствуют" in text:
                await client.disconnect()
                return 'active', f"{result_text} — ✅ Активный"
            elif "временные ограничения" in text:
                await client.disconnect()
                return 'temp_ban', f"{result_text} — ⚠️ Временный бан"
            elif "вы больше не можете использовать telegram" in text:
                await client.disconnect()
                return 'banned', f"{result_text} — ⛔ Перманентный бан"
            else:
                await client.disconnect()
                return 'unknown', f"{result_text} — ❓ Неизвестный статус"

        except Exception as e:
            await client.disconnect()
            return 'error', f"{result_text} — ⚠️ Ошибка при проверке: {str(e)}"

    except errors.UserDeactivatedBanError:
        return 'banned', "⛔ Аккаунт заблокирован"
    except Exception as e:
        return 'error', f"❌ Ошибка: {str(e)}"
