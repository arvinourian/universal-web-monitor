import time
import datetime
import threading
import queue
import re
import subprocess
import base64
import html as html_lib
import urllib3
import requests
from bs4 import BeautifulSoup
from lxml import html

# Disable insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Platform audio support
try:
    import winsound
    def play_sound(pattern="alert"):
        if pattern == "startup":
            freq_list = [(800, 150), (1200, 200)]
        elif pattern == "alert":
            freq_list = [(1000, 200), (1200, 200), (1500, 400)]
        else:
            freq_list = [(1000, 150)]
        for freq, dur in freq_list:
            winsound.Beep(freq, dur)
            time.sleep(0.04)
except ImportError:
    def play_sound(pattern="alert"):
        print("\a", end="", flush=True)

class MonitorEngine:
    def __init__(self):
        self.is_running = False
        self.thread = None
        self.stop_event = threading.Event()
        
        # Configuration
        self.config = {
            "url": "",
            "selector_type": "xpath",  # xpath, full_xpath, css, regex, full_text
            "selector": "",
            "interval": 30,
            "enable_desktop_notifications": True,
            "enable_sound": True,
            "enable_telegram": False,
            "telegram_bot_token": "",
            "telegram_chat_id": ""
        }
        
        # State
        self.last_value = None
        self.start_time = None
        self.check_count = 0
        self.change_count = 0
        self.last_check_time = None
        self.last_error = None
        
        # SSE Log Subscribers
        self.log_subscribers = []
        self.logs_history = []
        self.lock = threading.Lock()

    def add_log(self, level: str, message: str, details: dict = None):
        """Records a log entry and dispatches it to all SSE subscribers."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "level": level,  # 'info', 'success', 'warning', 'error', 'alert'
            "message": message,
            "details": details or {}
        }
        with self.lock:
            self.logs_history.append(log_entry)
            if len(self.logs_history) > 500:
                self.logs_history.pop(0)

            # Dispatch to active SSE subscriber queues
            for q in list(self.log_subscribers):
                try:
                    q.put_nowait(log_entry)
                except queue.Full:
                    pass

    def subscribe_logs(self):
        """Returns a queue for an SSE client."""
        q = queue.Queue(maxsize=100)
        with self.lock:
            # Replay recent history
            for entry in self.logs_history[-50:]:
                q.put_nowait(entry)
            self.log_subscribers.append(q)
        return q

    def unsubscribe_logs(self, q):
        """Removes an SSE client queue."""
        with self.lock:
            if q in self.log_subscribers:
                self.log_subscribers.remove(q)

    @staticmethod
    def send_desktop_notification(title: str, message: str):
        """Sends native Windows Toast notification."""
        try:
            esc_title = html_lib.escape(title)
            esc_msg = html_lib.escape(message)
            ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = '<toast><visual><binding template="ToastGeneric"><text>{esc_title}</text><text>{esc_msg}</text></binding></visual></toast>'
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Universal Web Monitor').Show($toast)
"""
            encoded = base64.b64encode(ps_script.encode('utf-16le')).decode('utf-8')
            subprocess.Popen(
                ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-EncodedCommand', encoded],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"Desktop notification failed: {e}")

    @staticmethod
    def extract_content(html_content: str, selector_type: str, selector: str) -> str:
        """Extracts content from HTML based on selector type."""
        selector_type = selector_type.lower()
        
        if selector_type in ["xpath", "full_xpath"]:
            tree = html.fromstring(html_content)
            results = tree.xpath(selector)
            if not results:
                raise ValueError(f"XPath '{selector}' did not match any elements.")
            
            # If string or attribute result
            if isinstance(results[0], str):
                return results[0].strip()
            # If HTML element
            return results[0].text_content().strip()

        elif selector_type == "css":
            soup = BeautifulSoup(html_content, "html.parser")
            elem = soup.select_one(selector)
            if not elem:
                raise ValueError(f"CSS Selector '{selector}' did not match any elements.")
            return elem.get_text(separator=" ", strip=True)

        elif selector_type == "regex":
            match = re.search(selector, html_content, re.DOTALL)
            if not match:
                raise ValueError(f"Regex pattern '{selector}' found no matches.")
            if match.groups():
                return match.group(1).strip()
            return match.group(0).strip()

        elif selector_type == "full_text":
            soup = BeautifulSoup(html_content, "html.parser")
            return soup.get_text(separator=" ", strip=True)[:500]

        else:
            raise ValueError(f"Unsupported selector type: {selector_type}")

    def fetch_url(self, url: str) -> str:
        """Fetches page HTML with standard browser headers."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=20, verify=False)
        resp.raise_for_status()
        return resp.text

    def test_selector(self, url: str, selector_type: str, selector: str) -> dict:
        """One-shot test of URL fetching and element extraction."""
        try:
            html_text = self.fetch_url(url)
            value = self.extract_content(html_text, selector_type, selector)
            return {
                "success": True,
                "value": value,
                "html_length": len(html_text)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def resolve_telegram_chat_id(self, bot_token: str, custom_chat_id: str = "") -> str | None:
        """Resolves the chat ID from the bot or getUpdates."""
        if custom_chat_id and custom_chat_id.strip():
            return custom_chat_id.strip()

        if not bot_token:
            return None

        try:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            resp = requests.get(url, timeout=6)
            data = resp.json()
            if data.get("ok") and data.get("result"):
                last_update = data["result"][-1]
                chat_id = str(last_update.get("message", {}).get("chat", {}).get("id") or 
                              last_update.get("channel_post", {}).get("chat", {}).get("id"))
                if chat_id:
                    return chat_id
        except Exception as e:
            self.add_log("warning", f"Telegram getUpdates check: {e}")
        return None

    def send_telegram_msg(self, bot_token: str, chat_id: str, message: str) -> bool:
        """Sends a message via Telegram bot."""
        if not bot_token or not chat_id:
            return False
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            else:
                self.add_log("warning", f"Telegram API returned error {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            self.add_log("error", f"Failed to send Telegram message: {e}")
            return False

    def test_telegram(self, bot_token: str, custom_chat_id: str = "") -> dict:
        """Tests Telegram connection and sends a test message."""
        try:
            # 1. Check getMe
            getme_url = f"https://api.telegram.org/bot{bot_token}/getMe"
            r = requests.get(getme_url, timeout=8)
            bot_data = r.json()
            if not bot_data.get("ok"):
                return {"success": False, "error": f"Invalid Bot Token: {bot_data.get('description', 'Unknown error')}"}
            
            bot_username = bot_data["result"].get("username", "your bot")
            
            # 2. Check Chat ID
            resolved_id = self.resolve_telegram_chat_id(bot_token, custom_chat_id)
            if not resolved_id:
                return {
                    "success": False,
                    "error": (
                        f"Connected to @{bot_username}, but no messages found yet! "
                        f"Please open Telegram, open @{bot_username} (https://t.me/{bot_username}), "
                        f"and press 'START' or send any message to it, then try again."
                    ),
                    "bot_username": bot_username
                }

            # 3. Send test message
            test_msg = f"✅ *Telegram Connection Test Successful!*\n\nBot: @{bot_username}\nReady to send website change alerts."
            sent = self.send_telegram_msg(bot_token, resolved_id, test_msg)
            if sent:
                return {
                    "success": True,
                    "message": f"Test message sent to Telegram chat ID: {resolved_id} via @{bot_username}",
                    "chat_id": resolved_id,
                    "bot_username": bot_username
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to deliver test message. Check bot permissions or Chat ID."
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start(self, config: dict) -> dict:
        """Starts the monitoring thread."""
        if self.is_running:
            return {"success": False, "error": "Monitor is already running."}

        self.config = config
        self.is_running = True
        self.stop_event.clear()
        self.start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.check_count = 0
        self.change_count = 0
        self.last_value = None
        self.last_error = None

        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        
        self.add_log("info", f"Started monitoring {self.config['url']}", {
            "selector_type": self.config["selector_type"],
            "selector": self.config["selector"],
            "interval": self.config["interval"]
        })
        return {"success": True, "start_time": self.start_time}

    def stop(self) -> dict:
        """Stops the monitoring thread."""
        if not self.is_running:
            return {"success": False, "error": "Monitor is not running."}

        self.stop_event.set()
        self.is_running = False
        self.add_log("info", "Monitoring stopped by user.")
        return {"success": True}

    def get_status(self) -> dict:
        """Returns current engine status."""
        return {
            "is_running": self.is_running,
            "start_time": self.start_time,
            "last_value": self.last_value,
            "last_check_time": self.last_check_time,
            "check_count": self.check_count,
            "change_count": self.change_count,
            "last_error": self.last_error,
            "config": self.config
        }

    def _monitor_loop(self):
        """Background loop that periodically polls the webpage."""
        session = requests.Session()
        bot_token = self.config.get("telegram_bot_token", "").strip()
        chat_id = self.config.get("telegram_chat_id", "").strip()
        enable_tg = self.config.get("enable_telegram", False) and bool(bot_token)
        enable_desktop = self.config.get("enable_desktop_notifications", True)
        enable_sound = self.config.get("enable_sound", True)
        interval = max(int(self.config.get("interval", 30)), 3)

        # Initial fetch
        self.add_log("info", "Performing initial webpage check...")
        try:
            html_text = self.fetch_url(self.config["url"])
            initial_val = self.extract_content(
                html_text, 
                self.config["selector_type"], 
                self.config["selector"]
            )
            self.last_value = initial_val
            self.check_count += 1
            self.last_check_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.add_log("success", f"Initial value detected: '{initial_val}'", {"value": initial_val})

            # Initial desktop notification
            if enable_desktop:
                self.send_desktop_notification(
                    "Universal Web Monitor Started",
                    f"Monitoring active!\nInitial value: {initial_val}"
                )
            if enable_sound:
                play_sound("startup")

            # Initial Telegram notification
            if enable_tg:
                resolved_chat = self.resolve_telegram_chat_id(bot_token, chat_id)
                if resolved_chat:
                    chat_id = resolved_chat
                    tg_start_msg = (
                        f"🚀 *Web Monitor Started*\n\n"
                        f"• *URL:* {self.config['url']}\n"
                        f"• *Initial Value:* `{initial_val}`\n"
                        f"• *Interval:* {interval}s\n\n"
                        f"_You will receive an alert whenever this value changes._"
                    )
                    if self.send_telegram_msg(bot_token, chat_id, tg_start_msg):
                        self.add_log("success", "Initial Telegram notification dispatched.")
                else:
                    self.add_log("warning", "Telegram alerts enabled, but bot hasn't received a message yet to get Chat ID. Send a message to your bot!")

        except Exception as e:
            self.last_error = str(e)
            self.add_log("error", f"Initial check failed: {e}")

        # Polling Loop
        while not self.stop_event.is_set():
            # Wait for interval or stop event
            if self.stop_event.wait(interval):
                break

            self.check_count += 1
            self.last_check_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Check if Telegram chat_id was acquired in the meantime
            if enable_tg and not chat_id:
                resolved = self.resolve_telegram_chat_id(bot_token)
                if resolved:
                    chat_id = resolved
                    self.add_log("success", f"Telegram Chat Connected! (ID: {chat_id})")

            try:
                html_text = self.fetch_url(self.config["url"])
                current_val = self.extract_content(
                    html_text, 
                    self.config["selector_type"], 
                    self.config["selector"]
                )
                self.last_error = None

                if self.last_value is None:
                    self.last_value = current_val
                    self.add_log("success", f"First value detected: '{current_val}'", {"value": current_val})
                elif current_val != self.last_value:
                    # VALUE CHANGED!
                    self.change_count += 1
                    prev = self.last_value
                    self.last_value = current_val

                    self.add_log("alert", f"🚨 CHANGE DETECTED! '{prev}' ➔ '{current_val}'", {
                        "previous": prev,
                        "new": current_val
                    })

                    # Desktop Notification
                    if enable_desktop:
                        self.send_desktop_notification(
                            "🚨 Web Monitor: Change Detected!",
                            f"Previous: {prev}\nNew: {current_val}"
                        )
                    if enable_sound:
                        play_sound("alert")

                    # Telegram Notification
                    if enable_tg and chat_id:
                        tg_change_msg = (
                            f"🚨 *Website Change Detected!*\n\n"
                            f"• *Previous Value:* {prev}\n"
                            f"• *New Value:* {current_val}\n"
                            f"• *Time:* {self.last_check_time}\n\n"
                            f"🔗 [Open Target Website]({self.config['url']})"
                        )
                        self.send_telegram_msg(bot_token, chat_id, tg_change_msg)
                else:
                    self.add_log("info", f"Check #{self.check_count}: No change (Value: '{current_val}')")

            except Exception as e:
                self.last_error = str(e)
                self.add_log("error", f"Check #{self.check_count} error: {e}")

        self.is_running = False
