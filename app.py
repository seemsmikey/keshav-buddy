"""Flask web server for the Keshav Mahavidyalaya RAG helpdesk chatbot."""

from __future__ import annotations

import json

from flask import Flask, Response, jsonify, request, send_from_directory

import config
from rag import RAGEngine

app = Flask(__name__, static_folder=str(config.STATIC_DIR), static_url_path="")
engine = RAGEngine()


@app.get("/")
def index():
    return send_from_directory(config.STATIC_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "college": config.COLLEGE_NAME,
        "chat_model": config.CHAT_MODEL,
        "embed_model": config.EMBED_MODEL,
    })


@app.get("/api/faqs")
def faqs():
    return jsonify({
        "college": config.COLLEGE_NAME,
        "questions": config.SUGGESTED_QUESTIONS,
    })


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "A non-empty 'question' field is required."}), 400

    try:
        result = engine.answer(question)
    except Exception as exc:  # noqa: BLE001 - surface a friendly error to the client
        return jsonify({"error": f"Failed to generate an answer: {exc}"}), 500

    return jsonify(result)


@app.post("/api/chat/stream")
def chat_stream():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "A non-empty 'question' field is required."}), 400

    def generate():
        try:
            for event in engine.stream_answer(question):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return Response(generate(), mimetype="text/event-stream", headers=headers)


if __name__ == "__main__":
    print(f"Starting {config.COLLEGE_NAME} helpdesk chatbot ...")
    print("Warming up the vector index ...")
    engine._store_or_build()

    print("\nIndex ready. Open the app on any device using one of these URLs:\n")
    print(f"  This PC      : http://localhost:{config.PORT}")
    lan_ips = config.local_ipv4_addresses()
    for ip in lan_ips:
        print(f"  Other devices: http://{ip}:{config.PORT}")
    if not lan_ips:
        print("  (No LAN address detected - check your network connection.)")
    print("\nPhones/tablets must be on the same Wi-Fi/network as this PC.")
    print("If other devices cannot connect, allow the port through Windows Firewall.\n")

    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)
