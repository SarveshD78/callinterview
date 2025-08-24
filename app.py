import os
import json
import threading
import base64
import websocket
import audioop
from flask import Flask, request, jsonify, render_template, Response
from flask_socketio import SocketIO
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.rest import Client as TwilioRestClient
from twilio.twiml.voice_response import VoiceResponse, Dial, Stream  # <-- Stream added

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# -----------------------------
# 🔑 Environment variables
# -----------------------------
TWILIO_ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")
TWILIO_API_KEY       = os.getenv("TWILIO_API_KEY")
TWILIO_API_SECRET    = os.getenv("TWILIO_API_SECRET")
TWILIO_NUMBER        = os.getenv("TWILIO_NUMBER")
PUBLIC_BASE_URL      = os.getenv("PUBLIC_BASE_URL")
ASSEMBLYAI_API_KEY   = os.getenv("ASSEMBLYAI_API_KEY")

twilio_client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
CONFERENCE_NAME = "interview_room"

# -----------------------------
# AssemblyAI WebSocket session
# -----------------------------
assemblyai_ws = None

def start_assemblyai_ws():
    global assemblyai_ws
    url = "wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"

    def on_open(ws):
        print("[AssemblyAI] ✅ WebSocket opened")

    def on_message(ws, msg):
        try:
            data = json.loads(msg)
            if "text" in data:
                socketio.emit("new_transcript", data)
        except Exception as e:
            print("[AssemblyAI] Parse error:", e)

    def on_error(ws, err):
        print("[AssemblyAI] ❌ WebSocket error:", err)

    def on_close(ws, *_):
        print("[AssemblyAI] 🔒 WebSocket closed")

    ws = websocket.WebSocketApp(
        url,
        header=[f"Authorization: {ASSEMBLYAI_API_KEY}"],
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    assemblyai_ws = ws
    thread = threading.Thread(target=ws.run_forever, daemon=True)
    thread.start()

def init_ws():
    print("[INIT] Starting AssemblyAI WS…")
    start_assemblyai_ws()

# -----------------------------
# Routes
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

    # Stream Twilio audio to /media (AssemblyAI)
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
    global assemblyai_ws
    try:
        data = request.get_json(force=True)
        if data.get("event") == "media":
            payload_b64 = data["media"]["payload"]

            # Decode Twilio μ-law audio
            ulaw_bytes = base64.b64decode(payload_b64)
            pcm16_bytes = audioop.ulaw2lin(ulaw_bytes, 2)

            # Resample from 8kHz → 16kHz
            pcm16_16k = audioop.ratecv(pcm16_bytes, 2, 1, 8000, 16000, None)[0]

            # Encode to base64 for AssemblyAI
            msg = json.dumps({
                "audio_data": base64.b64encode(pcm16_16k).decode("utf-8")
            })
            if assemblyai_ws:
                assemblyai_ws.send(msg)
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
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
