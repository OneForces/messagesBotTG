# gui/main_window.py

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QTabWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QTextEdit,
    QSpinBox, QHBoxLayout, QListWidget
)
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.templates import parse_template
from PyQt5.QtWidgets import QMenu
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import QInputDialog
from telethon.errors import SessionPasswordNeededError
from PyQt5.QtWidgets import QComboBox
import base64
from telethon.sessions import MemorySession
import json
import sys
import os
import asyncio
from core.account_manager import check_account_status
from telethon import TelegramClient, errors
import random
import time
import threading
from datetime import datetime
import csv
import threading
import asyncio


def append_report(account, recipient, status, message):
    os.makedirs("logs", exist_ok=True)
    path = "logs/report.csv"
    write_header = not os.path.exists(path)

    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["account", "recipient", "status", "message", "time"])
        writer.writerow([
            os.path.basename(account),
            f"@{recipient}",
            "✅" if status else "❌",
            message,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])


API_ID = 12345678  # ← замени на свой
API_HASH = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'  # ← замени на свой

def write_log(file, text):
    with open(file, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — {text}\n")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telegram Sender")
        self.setGeometry(200, 200, 900, 600)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Основные переменные
        self.account_list_widget = QListWidget()
        self.recipients_list_widget = QListWidget()

        self.proxies = []
        self.recipients = []
        self.accounts = []
        self.media_path = None
        self.stop_flag = False

        # Новый элемент: тип медиа
        self.media_type = None  # будет создан в init_message_tab()

        # Инициализация вкладок
        self.init_accounts_tab()
        self.init_proxies_tab()
        self.init_recipients_tab()
        self.init_message_tab()
        self.init_settings_tab()
        self.init_send_tab()
        self.init_log_tab()

        # Загрузка логов и конфигурации
        self.load_logs()
        self.load_config()

        # Автосохранение конфигурации при закрытии
        self.destroyed.connect(self.save_config)

    def init_log_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        self.send_log = QTextEdit()
        self.send_log.setReadOnly(True)
        layout.addWidget(QLabel("📤 Отправленные сообщения"))
        layout.addWidget(self.send_log)

        self.errors_log = QTextEdit()
        self.errors_log.setReadOnly(True)
        layout.addWidget(QLabel("❌ Ошибки"))
        layout.addWidget(self.errors_log)

        self.accounts_log = QTextEdit()
        self.accounts_log.setReadOnly(True)
        layout.addWidget(QLabel("👤 Аккаунты"))
        layout.addWidget(self.accounts_log)

        refresh_btn = QPushButton("🔄 Обновить логи")
        refresh_btn.clicked.connect(self.load_logs)
        layout.addWidget(refresh_btn)

        export_btn = QPushButton("📤 Экспортировать отчёт (report.csv)")
        export_btn.clicked.connect(self.export_report)
        layout.addWidget(export_btn)

        tab.setLayout(layout)
        self.tabs.addTab(tab, "Лог")
        

    def load_logs(self):
        def read_log(file_path):
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            return "Файл не найден."

        self.send_log.setPlainText(read_log("logs/send.log"))
        self.errors_log.setPlainText(read_log("logs/errors.log"))
        self.accounts_log.setPlainText(read_log("logs/accounts.log"))

    def init_accounts_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Импорт Telegram аккаунтов (.session)"))

        btns = QHBoxLayout()
        load_btn = QPushButton("📂 Загрузить и проверить")
        load_btn.clicked.connect(self.load_accounts)
        refresh_btn = QPushButton("🔁 Повторная проверка")
        refresh_btn.clicked.connect(self.recheck_accounts)
        btns.addWidget(load_btn)
        btns.addWidget(refresh_btn)
        layout.addLayout(btns)

        layout.addWidget(QLabel("Загруженные аккаунты со статусом:"))

        # 👉 Контекстное меню по ПКМ
        self.account_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.account_list_widget.customContextMenuRequested.connect(self.show_account_context_menu)

        layout.addWidget(self.account_list_widget)

        # ✅ Добавляем кнопку для ручного переноса из временного бана
        move_btn = QPushButton("⬆ Переместить из временного бана")
        move_btn.clicked.connect(self.move_from_temp_ban)
        layout.addWidget(move_btn)

        tab.setLayout(layout)
        self.tabs.addTab(tab, "Аккаунты")

    def move_from_temp_ban(self):
        selected_items = self.account_list_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            session_name = item.text().split(" — ")[0]
            if session_name in self.accounts:
                acc = self.accounts[session_name]
                if acc.get("status") == "temp_ban":
                    acc["status"] = "active"
                    item.setText(f"{session_name} — ✅ активный (ручной перевод)")


    def show_account_context_menu(self, position: QPoint):
        item = self.account_list_widget.itemAt(position)
        if item is None:
            return

        menu = QMenu()
        mark_active = menu.addAction("✅ Пометить как активный")
        action = menu.exec_(self.account_list_widget.mapToGlobal(position))

        if action == mark_active:
            text = item.text()
            if "теневой бан" in text or "⚠️" in text:
                updated = text.replace("⚠️ теневой бан", "✅ активен")
                updated = updated.replace("⚠️", "✅")
                item.setText(updated)
                write_log("logs/accounts.log", f"{updated} — вручную помечен как активный")


    def init_proxies_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Импорт списка прокси (ip:port:user:pass)"))
        load_btn = QPushButton("Загрузить прокси")
        load_btn.clicked.connect(self.load_proxies)
        layout.addWidget(load_btn)

        layout.addWidget(QLabel("Прокси будут отображаться и проверяться здесь..."))
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Прокси")

    def init_recipients_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Импорт списка получателей (@username)"))
        load_btn = QPushButton("Загрузить и проверить получателей")
        load_btn.clicked.connect(self.load_recipients)
        layout.addWidget(load_btn)

        layout.addWidget(QLabel("Результат проверки:"))
        layout.addWidget(self.recipients_list_widget)

        tab.setLayout(layout)
        self.tabs.addTab(tab, "Получатели")

    def init_message_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Введите шаблон сообщения:"))
        self.message_edit = QTextEdit()
        layout.addWidget(self.message_edit)

        layout.addWidget(QLabel("Добавить медиа (необязательно):"))
        media_btn = QPushButton("Выбрать файл")
        media_btn.clicked.connect(self.choose_media)
        layout.addWidget(media_btn)

        self.media_label = QLabel("Выбранный файл: (путь появится здесь)")
        layout.addWidget(self.media_label)

        layout.addWidget(QLabel("Тип медиа:"))
        self.media_type = QComboBox()
        self.media_type.addItems([
            "Фото/видео", 
            "Голосовое сообщение", 
            "Кружок (VideoNote)"
        ])
        layout.addWidget(self.media_type)

        tab.setLayout(layout)
        self.tabs.addTab(tab, "Сообщение")


    def init_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Настройки задержек и лимитов:"))

        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Задержка между сообщениями (сек):"))
        self.min_delay = QSpinBox()
        self.min_delay.setMinimum(1)
        self.min_delay.setMaximum(60)
        self.min_delay.setValue(17)
        self.max_delay = QSpinBox()
        self.max_delay.setMinimum(1)
        self.max_delay.setMaximum(60)
        self.max_delay.setValue(24)
        h1.addWidget(self.min_delay)
        h1.addWidget(QLabel("до"))
        h1.addWidget(self.max_delay)
        layout.addLayout(h1)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Макс. сообщений на аккаунт:"))
        self.msg_limit_min = QSpinBox()
        self.msg_limit_min.setValue(1)
        self.msg_limit_max = QSpinBox()
        self.msg_limit_max.setValue(5)
        h2.addWidget(self.msg_limit_min)
        h2.addWidget(QLabel("до"))
        h2.addWidget(self.msg_limit_max)
        layout.addLayout(h2)

        h3 = QHBoxLayout()
        h3.addWidget(QLabel("Потоков:"))
        self.thread_count = QSpinBox()
        self.thread_count.setValue(5)
        h3.addWidget(self.thread_count)
        layout.addLayout(h3)

        # 👉 Добавляем кнопку сохранения
        save_btn = QPushButton("💾 Сохранить настройки")
        save_btn.clicked.connect(self.save_config)
        layout.addWidget(save_btn)

        tab.setLayout(layout)
        self.tabs.addTab(tab, "Настройки")


    def init_send_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        start_btn = QPushButton("▶ Начать рассылку")
        start_btn.clicked.connect(self.start_sending)
        stop_btn = QPushButton("⛔ Остановить")
        stop_btn.clicked.connect(self.stop_sending)

        layout.addWidget(start_btn)
        layout.addWidget(stop_btn)

        layout.addWidget(QLabel("Сообщение:"))
        self.message_edit = QTextEdit()
        layout.addWidget(self.message_edit)

        self.send_log_widget = QTextEdit()
        self.send_log_widget.setReadOnly(True)
        self.send_log_widget.setPlaceholderText("Здесь будет отображаться лог отправки...")
        layout.addWidget(self.send_log_widget)

        tab.setLayout(layout)
        self.tabs.addTab(tab, "Рассылка")



    def load_accounts(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с аккаунтами (.session + .json)", "./sessions")
        if not folder:
            return

        self.account_list_widget.clear()
        self.accounts.clear()

        session_files = [f for f in os.listdir(folder) if f.endswith(".session")]
        json_files = [f for f in os.listdir(folder) if f.endswith(".json")]

        loaded = set()

        # Загрузка .session аккаунтов
        for file in session_files:
            session_path = os.path.join(folder, file)
            if os.path.getsize(session_path) > 0:
                self.accounts.append({
                    "type": "session",
                    "path": session_path,
                    "filename": file
                })
                self.account_list_widget.addItem(f"{file}: ✅ .session")
                loaded.add(file.replace(".session", ""))

        # Загрузка .json аккаунтов и авторизация
        for json_file in json_files:
            name = json_file.replace(".json", "")
            if name in loaded:
                continue  # уже загружен как .session

            json_path = os.path.join(folder, json_file)
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                self.account_list_widget.addItem(f"{json_file}: ❌ Ошибка чтения JSON: {e}")
                continue

            phone = data.get("phone")
            api_id = data.get("app_id") or API_ID
            api_hash = data.get("app_hash") or API_HASH

            if not phone:
                self.account_list_widget.addItem(f"{json_file}: ❌ Нет номера телефона")
                continue

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.authorize_json_account(phone, api_id, api_hash, folder))
                self.accounts.append({
                    "type": "json",
                    "session": os.path.join(folder, phone),
                    "api_id": api_id,
                    "api_hash": api_hash,
                    "filename": json_file
                })
                self.account_list_widget.addItem(f"{json_file}: ✅ Авторизован через JSON")
            except Exception as e:
                self.account_list_widget.addItem(f"{json_file}: ❌ Ошибка авторизации: {str(e)}")
            finally:
                loop.close()



    def load_proxies(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл с прокси", "", "Text Files (*.txt)")
        if not path:
            return

        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            self.proxies = []

            for idx, line in enumerate(lines, 1):
                parts = line.strip().split(":")
                if len(parts) < 2:
                    print(f"⚠️ Строка {idx} — недостаточно данных: {line}")
                    continue

                ip = parts[0]
                port = int(parts[1])
                user = parts[2] if len(parts) > 2 else ""
                pwd = parts[3] if len(parts) > 3 else ""
                proxy_type = parts[4] if len(parts) > 4 else "http"

                if proxy_type not in ("http", "socks5"):
                    print(f"⚠️ Строка {idx} — неизвестный тип: {proxy_type}")
                    continue

                self.proxies.append((ip, port, user, pwd, proxy_type))

        print(f"✅ Загружено прокси: {len(self.proxies)}")

    def load_recipients(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл с получателями", "", "Text Files (*.txt)")
        if not path:
            return

        with open(path, "r", encoding="utf-8") as f:
            self.recipients = [line.strip().lstrip('@') for line in f if line.strip()]

        self.recipients_list_widget.clear()
        if not self.recipients:
            self.recipients_list_widget.addItem("❌ Список получателей пуст.")
            return

        if self.account_list_widget.count() == 0:
            self.recipients_list_widget.addItem("❌ Нет загруженных аккаунтов.")
            return

        session_file = self.account_list_widget.item(0).text().split(":")[0]
        session_path = os.path.join("sessions", session_file)

        threading.Thread(
            target=self.run_check_recipients_thread,
            args=(session_path, self.recipients),
            daemon=True
        ).start()


    def run_check_recipients_thread(self, session_path, recipients):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.check_recipient_access(session_path, recipients))
        loop.close()



    async def check_recipient_access(self, session_path, usernames):
        try:
            client = TelegramClient(session_path.replace(".session", ""), API_ID, API_HASH)
            await client.connect()

            for username in usernames:
                if not await client.is_user_authorized():
                    self.recipients_list_widget.addItem(f"❌ @{username} — не авторизован")
                    continue

                try:
                    user = await client.get_entity(username)
                    self.recipients_list_widget.addItem(f"✅ @{username} — доступно")
                except Exception as e:
                    self.recipients_list_widget.addItem(f"❌ @{username} — {str(e)}")

            await client.disconnect()

        except Exception as e:
            self.recipients_list_widget.addItem(f"❌ Ошибка запуска клиента: {str(e)}")

    def choose_media(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите медиафайл", "", "All Files (*)")
        if file_path:
            self.media_path = file_path
            self.media_label.setText(f"Выбранный файл: {file_path}")

    def stop_sending(self):
        self.stop_flag = True

    def start_sending(self):
        self.stop_flag = False
        thread = threading.Thread(target=self.run_sending)
        thread.start()

    def run_sending(self):
        self.send_log_widget.append("🚀 Запуск рассылки...")
        self.stop_flag = False  # если нужен флаг остановки

        threading.Thread(
            target=self._run_sending_thread,
            daemon=True
        ).start()

    def _run_sending_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._run_sending_async())
        loop.close()

    async def _run_sending_async(self):
        message = self.message_edit.toPlainText()
        min_delay = self.min_delay.value()
        max_delay = self.max_delay.value()
        limit_min = self.msg_limit_min.value()
        limit_max = self.msg_limit_max.value()

        for acc in self.accounts:
            if self.stop_flag:
                break

            session_name = os.path.basename(acc["path"]) if acc["type"] == "session" else acc["filename"]

            try:
                if acc["type"] == "session":
                    client = TelegramClient(acc["path"].replace(".session", ""), API_ID, API_HASH)
                elif acc["type"] == "json":
                    client = TelegramClient(acc["session"], acc["api_id"], acc["api_hash"])
                else:
                    raise Exception(f"Неизвестный тип аккаунта: {acc}")

                await client.start()

                send_limit = random.randint(limit_min, limit_max)
                targets = random.sample(self.recipients, min(send_limit, len(self.recipients)))

                for username in targets:
                    if self.stop_flag:
                        break
                    try:
                        user = await client.get_entity(username)

                        if self.media_path:
                            media_type = self.media_type.currentText() if self.media_type else "Фото/видео"
                            if "Голос" in media_type:
                                await client.send_file(user, self.media_path, voice_note=True)
                            elif "Кружок" in media_type:
                                await client.send_file(user, self.media_path, video_note=True)
                            else:
                                await client.send_file(user, self.media_path, caption=message)
                        else:
                            await client.send_message(user, message)

                        write_log("logs/send.log", f"{session_name} → @{username}")
                        append_report(session_name, username, True, "OK")
                        self.send_log_widget.append(f"✅ {session_name} → @{username}")

                        await asyncio.sleep(random.uniform(min_delay, max_delay))

                    except Exception as e:
                        write_log("logs/errors.log", f"{session_name} → @{username}: {str(e)}")
                        append_report(session_name, username, False, str(e))
                        self.send_log_widget.append(f"❌ {session_name} → @{username}: {str(e)}")

                await client.disconnect()

            except SessionPasswordNeededError:
                pwd, ok = QInputDialog.getText(
                    self, "2FA Защита", f"Введите 2FA-пароль для аккаунта:\n{session_name}"
                )
                if ok and pwd:
                    try:
                        await client.sign_in(password=pwd)
                    except Exception as e:
                        write_log("logs/errors.log", f"{session_name}: ошибка входа с 2FA: {str(e)}")
                else:
                    write_log("logs/errors.log", f"{session_name}: 2FA-пароль не введён.")
            except Exception as e:
                write_log("logs/errors.log", f"Ошибка аккаунта {session_name}: {str(e)}")
                self.send_log_widget.append(f"🔥 Ошибка аккаунта {session_name}: {str(e)}")

        self.send_log_widget.append("📬 Рассылка завершена.")


    def recheck_accounts(self):
        if not self.accounts:
            self.account_list_widget.addItem("⚠️ Нет аккаунтов для повторной проверки.")
            return

        self.account_list_widget.clear()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for idx, acc in enumerate(self.accounts):
            # Получаем путь сессии
            if isinstance(acc, dict):
                session_path = acc.get("path") if acc["type"] == "session" else acc.get("session")
                account_name = acc.get("filename") or os.path.basename(session_path)
            else:
                # старый формат (строка)
                session_path = acc
                account_name = os.path.basename(session_path)

            # Подставляем прокси
            proxy = self.proxies[idx] if idx < len(self.proxies) else None

            try:
                status_code, display_text = loop.run_until_complete(check_account_status(session_path, proxy=proxy))
                self.account_list_widget.addItem(f"{display_text}")
                write_log("logs/accounts.log", f"{account_name}: {display_text}")
            except Exception as e:
                error_text = f"{account_name}: ❌ Ошибка: {str(e)}"
                self.account_list_widget.addItem(error_text)
                write_log("logs/errors.log", error_text)



    def export_report(self):
        source_path = "logs/report.csv"
        if not os.path.exists(source_path):
            print("❌ Файл отчёта не найден.")
            return

        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить отчёт как",
            "report.csv",
            "CSV Files (*.csv)"
        )
        if target_path:
            try:
                with open(source_path, "rb") as src, open(target_path, "wb") as dst:
                    dst.write(src.read())
                print(f"✅ Отчёт сохранён в: {target_path}")
            except Exception as e:
                print(f"❌ Ошибка при сохранении отчёта: {e}")


    def load_config(self):
        if not os.path.exists("config.json"):
            return

        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)

            self.min_delay.setValue(config.get("min_delay", 1))
            self.max_delay.setValue(config.get("max_delay", 5))
            self.msg_limit_min.setValue(config.get("msg_limit_min", 1))
            self.msg_limit_max.setValue(config.get("msg_limit_max", 5))
            self.thread_count.setValue(config.get("thread_count", 1))
            self.message_edit.setPlainText(config.get("message_text", ""))
            self.media_path = config.get("media_path", None)

        except Exception as e:
            print(f"Ошибка при загрузке config.json: {e}")


    def save_config(self):
        config = {
            "min_delay": self.min_delay.value(),
            "max_delay": self.max_delay.value(),
            "msg_limit_min": self.msg_limit_min.value(),
            "msg_limit_max": self.msg_limit_max.value(),
            "thread_count": self.thread_count.value(),
            "message_text": self.message_edit.toPlainText(),
            "media_path": self.media_path
        }

        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка при сохранении config.json: {e}")


    def closeEvent(self, event):
        self.save_config()
        event.accept()

def launch_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
