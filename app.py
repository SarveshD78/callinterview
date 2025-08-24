import os
import json
import threading
import base64
import audioop
from flask import Flask, request, jsonify, render_template, Response
from flask_socketio import SocketIO
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.rest import Client as TwilioRestClient
from twilio.twiml.voice_response import VoiceResponse, Stream

# Realtime OpenAI client
import websocket
import ssl

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# -----------------------------
# Environment
# -----------------------------
TWILIO_ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")
TWILIO_API_KEY       = os.getenv("TWILIO_API_KEY")
TWILIO_API_SECRET    = os.getenv("TWILIO_API_SECRET")
TWILIO_NUMBER        = os.getenv("TWILIO_NUMBER")
PUBLIC_BASE_URL      = os.getenv("PUBLIC_BASE_URL")
OPENAI_API_KEY       = os.getenv("OPENAI_API_KEY")  # Your OpenAI key

twilio_client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
CONFERENCE_NAME = "interview_room"

openai_ws = None

# -----------------------------
# OpenAI Realtime WS
# -----------------------------
def start_openai_ws():
    global openai_ws
    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"
    headers = [
        f"Authorization: Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta: realtime=v1"
    ]

    def on_open(ws):
        print("[OpenAI] ✅ WebSocket opened")

    def on_message(ws, msg):
        try:
            data = json.loads(msg)
            if "type" in data and data["type"] == "transcript.delta":
                # Emit live transcript to frontend
                socketio.emit("new_transcript", {"text": data["text"]})
        except Exception as e:
            print("[OpenAI] Parse error:", e)

    def on_error(ws, err):
        print("[OpenAI] ❌ WebSocket error:", err)

    def on_close(ws, *_):
        print("[OpenAI] 🔒 WebSocket closed")

    ws = websocket.WebSocketApp(
        url,
        header=headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    openai_ws = ws
    thread = threading.Thread(target=ws.run_forever, daemon=True)
    thread.start()

def init_ws():
    print("[INIT] Starting OpenAI WS…")
    start_openai_ws()

# -----------------------------
# Flask routes
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/token")
def token():
    identity = "browser_user"
    token = AccessToken(
        TWILIO_ACCOUNT_SID,
        TWILIO_API_KEY,
        TWILIO_API_SECRET,
        identity=identity
    )
    voice_grant = VoiceGrant(
        outgoing_application_sid=TWILIO_TWIML_APP_SID,
        incoming_allow=True
    )
    token.add_grant(voice_grant)
    jwt_token = token.to_jwt()
    if hasattr(jwt_token, "decode"):
        jwt_token = jwt_token.decode("utf-8")
    return jsonify({"token": jwt_token})

@app.route("/call", methods=["POST"])
def call_candidate():
    data = request.get_json(force=True)
    to_number = data.get("to")
    if not to_number:
        return jsonify({"error": "Missing 'to' phone number"}), 400

    voice_url = absolute_url("/voice")
    call = twilio_client.calls.create(
        to=to_number,
        from_=TWILIO_NUMBER,
        url=voice_url,
        status_callback=absolute_url("/status"),
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        status_callback_method="POST"
    )
    return jsonify({"call_sid": call.sid})

@app.route("/voice", methods=["POST"])
def voice():
    resp = VoiceResponse()
    resp.start(Stream(url=absolute_url("/media")))
    dial = resp.dial(callerId=TWILIO_NUMBER)
    dial.conference(
        CONFERENCE_NAME,
        record="record-from-start",
        start_conference_on_enter=True,
        end_conference_on_exit=True
    )
    return Response(str(resp), mimetype="text/xml")

@app.route("/media", methods=["POST"])
def media():
    global openai_ws
    try:
        data = request.get_json(force=True)
        if data.get("event") == "media":
            payload_b64 = data["media"]["payload"]

            # Twilio μ-law → PCM16
            ulaw_bytes = base64.b64decode(payload_b64)
            pcm16_bytes = audioop.ulaw2lin(ulaw_bytes, 2)

            # Resample from 8kHz → 16kHz
            pcm16_16k = audioop.ratecv(pcm16_bytes, 2, 1, 8000, 16000, None)[0]

            # Send audio to OpenAI WS
            if openai_ws:
                openai_ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(pcm16_16k).decode("utf-8")
                }))
                openai_ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                openai_ws.send(json.dumps({"type": "response.create"}))
    except Exception as e:
        print("[/media] ERROR:", e)
    return ("", 200)

@app.route("/status", methods=["POST"])
def status():
    print("[/status]", dict(request.values))
    return ("", 200)

def absolute_url(path: str) -> str:
    base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else request.url_root.rstrip("/")
    if not base.startswith("http"):
        base = "https://" + base.lstrip("/")
    return f"{base}{path}"

if __name__ == "__main__":
    init_ws()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
