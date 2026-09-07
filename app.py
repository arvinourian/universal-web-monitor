import json
import time
from flask import Flask, render_template, request, jsonify, Response
from monitor_engine import MonitorEngine

app = Flask(__name__, template_folder="templates", static_folder="static")
engine = MonitorEngine()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/test-selector", methods=["POST"])
def test_selector():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    selector_type = data.get("selector_type", "xpath")
    selector = data.get("selector", "").strip()

    if not url:
        return jsonify({"success": False, "error": "URL is required"}), 400
    if not selector and selector_type != "full_text":
        return jsonify({"success": False, "error": "Selector is required"}), 400

    result = engine.test_selector(url, selector_type, selector)
    return jsonify(result)

@app.route("/api/test-telegram", methods=["POST"])
def test_telegram():
    data = request.get_json() or {}
    bot_token = data.get("bot_token", "").strip()
    chat_id = data.get("chat_id", "").strip()

    if not bot_token:
        return jsonify({"success": False, "error": "Bot token is required"}), 400

    result = engine.test_telegram(bot_token, chat_id)
    return jsonify(result)

@app.route("/api/start", methods=["POST"])
def start_monitor():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    selector_type = data.get("selector_type", "xpath")
    selector = data.get("selector", "").strip()
    interval = int(data.get("interval", 30))

    if not url:
        return jsonify({"success": False, "error": "URL is required"}), 400
    if not selector and selector_type != "full_text":
        return jsonify({"success": False, "error": "Selector is required"}), 400

    config = {
        "url": url,
        "selector_type": selector_type,
        "selector": selector,
        "interval": max(interval, 3),
        "enable_desktop_notifications": bool(data.get("enable_desktop_notifications", True)),
        "enable_sound": bool(data.get("enable_sound", True)),
        "enable_telegram": bool(data.get("enable_telegram", False)),
        "telegram_bot_token": data.get("telegram_bot_token", "").strip(),
        "telegram_chat_id": data.get("telegram_chat_id", "").strip(),
    }

    result = engine.start(config)
    return jsonify(result)

@app.route("/api/stop", methods=["POST"])
def stop_monitor():
    result = engine.stop()
    return jsonify(result)

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify(engine.get_status())

@app.route("/api/logs/stream")
def stream_logs():
    def event_stream():
        log_queue = engine.subscribe_logs()
        try:
            while True:
                try:
                    # Non-blocking pop with timeout to send keep-alive
                    log_entry = log_queue.get(timeout=20)
                    yield f"data: {json.dumps(log_entry)}\n\n"
                except Exception:
                    # Keep-alive ping
                    yield ": ping\n\n"
        finally:
            engine.unsubscribe_logs(log_queue)

    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/api/logs/clear", methods=["POST"])
def clear_logs():
    with engine.lock:
        engine.logs_history.clear()
    return jsonify({"success": True})

if __name__ == "__main__":
    print("🚀 Universal Web Monitor server starting on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
