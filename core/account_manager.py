# core/account_manager.py

import asyncio
from telethon import TelegramClient, errors

API_ID = 12345678  # ← замени на свой
API_HASH = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'  # ← замени на свой


async def check_account_status(session_path, proxy=None):
    try:
        # Настройка прокси
        proxy_config = None
        if proxy:
            ip, port, user, pwd = proxy
            proxy_config = ('socks5', ip, port, True, user, pwd) if user else ('socks5', ip, port)

        # Запуск клиента
        client = TelegramClient(session_path.replace('.session', ''), API_ID, API_HASH, proxy=proxy_config)
        await client.connect()

        # Проверка авторизации
        if not await client.is_user_authorized():
            return '⛔ Не авторизован'

        me = await client.get_me()
        result = f"{me.first_name or ''} ({me.username or me.phone})"

        # Проверка статуса у @SpamBot
        try:
            entity = await client.get_entity("SpamBot")
            await client.send_message(entity, "/start")
            await asyncio.sleep(2)  # ждём ответа

            messages = await client.get_messages(entity, limit=1)
            text = messages[0].message.lower()

            if "ограничения отсутствуют" in text:
                result += " — ✅ Активный"
            elif "временные ограничения" in text:
                result += " — ⚠️ Временный бан"
            elif "вы больше не можете использовать telegram" in text:
                result += " — ⛔ Перманентный бан"
            else:
                result += " — ❓ Неизвестный статус"
        except Exception as e:
            result += f" — ⚠️ Ошибка при проверке: {str(e)}"

        await client.disconnect()
        return result

    except errors.UserDeactivatedBanError:
        return "⛔ Аккаунт заблокирован"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"
