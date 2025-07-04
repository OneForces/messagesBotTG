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
        layout.addWidget(QLabel("Лог отправки будет отображаться здесь..."))

        tab.setLayout(layout)
        self.tabs.addTab(tab, "Рассылка")

    # gui/main_window.py


    def load_accounts(self):
        session_folder = QFileDialog.getExistingDirectory(self, "Выберите папку с аккаунтами (.session или .json)", "./")
        if not session_folder:
            return

        self.account_list_widget.clear()
        self.accounts.clear()

        def load_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # === .session ===
            session_files = [f for f in os.listdir(session_folder) if f.endswith(".session")]
            for idx, file in enumerate(session_files):
                full_path = os.path.join(session_folder, file)
                proxy = self.proxies[idx] if idx < len(self.proxies) else None
                try:
                    status = loop.run_until_complete(check_account_status(full_path, proxy=proxy))
                    account_name = os.path.basename(full_path)
                    display_text = f"{account_name}: {status}"
                    self.account_list_widget.addItem(display_text)
                    self.accounts.append({
                        "type": "session",
                        "path": full_path
                    })
                    write_log("logs/accounts.log", display_text)
                except Exception as e:
                    error_text = f"{file}: ❌ Ошибка: {str(e)}"
                    self.account_list_widget.addItem(error_text)
                    write_log("logs/errors.log", error_text)

            # === .json ===
            json_files = [f for f in os.listdir(session_folder) if f.endswith(".json")]
            for file in json_files:
                try:
                    with open(os.path.join(session_folder, file), "r", encoding="utf-8") as f:
                        data = json.load(f)

                    session = MemorySession()
                    session.set_dc(data["dc_id"], "149.154.167.50", 443)
                    session.auth_key = base64.b64decode(data["auth_key"])
                    session._dc_id = data["dc_id"]

                    client = TelegramClient(session, data["api_id"], data["api_hash"])
                    loop.run_until_complete(client.connect())

                    if not loop.run_until_complete(client.is_user_authorized()):
                        raise Exception("Не авторизован")

                    account_name = file.replace(".json", "")
                    display_text = f"{account_name} (json): ✅ авторизован"
                    self.account_list_widget.addItem(display_text)
                    self.accounts.append({
                        "type": "json",
                        "session": session,
                        "api_id": data["api_id"],
                        "api_hash": data["api_hash"],
                        "filename": file
                    })
                    write_log("logs/accounts.log", display_text)
                    loop.run_until_complete(client.disconnect())

                except Exception as e:
                    error_text = f"{file}: ❌ Ошибка JSON: {str(e)}"
                    self.account_list_widget.addItem(error_text)
                    write_log("logs/errors.log", error_text)

        threading.Thread(target=load_thread).start()




    def load_proxies(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл с прокси", "", "Text Files (*.txt)")
        if not path:
            return

        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            self.proxies = []

            for line in lines:
                parts = line.strip().split(":")
                if len(parts) >= 2:
                    ip, port = parts[0], int(parts[1])
                    user = parts[2] if len(parts) > 2 else None
                    pwd = parts[3] if len(parts) > 3 else None
                    self.proxies.append((ip, port, user, pwd))

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

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.check_recipient_access(session_path, self.recipients))

    async def check_recipient_access(self, session_path, usernames):
        try:
            client = TelegramClient(session_path.replace(".session", ""), API_ID, API_HASH)
            await client.start()

            for username in usernames:
                try:
                    user = await client.get_entity(username)
                    await client.send_message(user.id, "test")
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
        message = self.message_edit.toPlainText()
        min_delay = self.min_delay.value()
        max_delay = self.max_delay.value()
        limit_min = self.msg_limit_min.value()
        limit_max = self.msg_limit_max.value()

        for acc in self.accounts:
            if self.stop_flag:
                break

            try:
                if acc["type"] == "session":
                    client = TelegramClient(acc["path"].replace(".session", ""), API_ID, API_HASH)
                    session_name = os.path.basename(acc["path"])
                else:  # JSON
                    client = TelegramClient(
                        acc["session"],
                        acc["api_id"],
                        acc["api_hash"]
                    )
                    session_name = acc["filename"]

                client.connect()

                if not client.is_user_authorized():
                    try:
                        client.start()
                    except SessionPasswordNeededError:
                        pwd, ok = QInputDialog.getText(
                            self,
                            "2FA Защита",
                            f"Введите 2FA-пароль для аккаунта:\n{session_name}"
                        )
                        if not ok or not pwd:
                            raise Exception("2FA-пароль не введён.")
                        client.sign_in(password=pwd)

                send_limit = random.randint(limit_min, limit_max)
                targets = random.sample(self.recipients, min(send_limit, len(self.recipients)))

                for username in targets:
                    if self.stop_flag:
                        break
                    try:
                        user = client.get_entity(username)

                        if self.media_path:
                            media_type = self.media_type.currentText() if self.media_type else "Фото/видео"

                            if "Голос" in media_type:
                                client.send_file(user, self.media_path, voice_note=True)
                            elif "Кружок" in media_type:
                                client.send_file(user, self.media_path, video_note=True)
                            else:
                                client.send_file(user, self.media_path, caption=message)
                        else:
                            client.send_message(user, message)

                        write_log("logs/send.log", f"{session_name} → @{username}")
                        append_report(session_name, username, True, "OK")
                        time.sleep(random.uniform(min_delay, max_delay))
                    except Exception as e:
                        write_log("logs/errors.log", f"{session_name} → @{username}: {str(e)}")
                        append_report(session_name, username, False, str(e))

                client.disconnect()

            except Exception as e:
                write_log("logs/errors.log", f"Ошибка аккаунта {session_name}: {str(e)}")





    def recheck_accounts(self):
        if not self.accounts:
            self.account_list_widget.addItem("⚠️ Нет аккаунтов для повторной проверки.")
            return

        self.account_list_widget.clear()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for idx, path in enumerate(self.accounts):
            proxy = self.proxies[idx] if idx < len(self.proxies) else None
            try:
                status = loop.run_until_complete(check_account_status(path, proxy=proxy))
                account_name = os.path.basename(path)
                display_text = f"{account_name}: {status}"
                self.account_list_widget.addItem(display_text)
                write_log("logs/accounts.log", display_text)
            except Exception as e:
                error_text = f"{os.path.basename(path)}: ❌ Ошибка: {str(e)}"
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
