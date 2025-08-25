import os
import base64
import json
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from twilio.rest import Client

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ---- Twilio credentials from env ----
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWIML_APP_SID = os.getenv("TWIML_APP_SID")  # must be set in Twilio Console
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# same conference for browser + candidate
CONFERENCE_NAME = "interview-room"

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/token")
def token():
    identity = "browser"
    token = AccessToken(
        TWILIO_ACCOUNT_SID,
        os.getenv("TWILIO_API_KEY"),
        os.getenv("TWILIO_API_SECRET"),
        identity=identity,
    )
    grant = VoiceGrant(outgoing_application_sid=TWIML_APP_SID)
    token.add_grant(grant)
    return jsonify({"token": token.to_jwt().decode()})


@app.route("/voice", methods=["POST"])
def voice():
    """TwiML for browser device to join conference + stream audio."""
    response = VoiceResponse()
    with response.connect() as connect:
        connect.stream(url="wss://shark-app-fu64d.ondigitalocean.app/media")
        connect.conference(CONFERENCE_NAME, start_conference_on_enter=True)
    return str(response)


@app.route("/call", methods=["POST"])
def call():
    data = request.get_json()
    to_number = data.get("to")
    if not to_number:
        return jsonify({"error": "Missing number"}), 400

    call = client.calls.create(
        to=to_number,
        from_=TWILIO_PHONE_NUMBER,
        twiml=f"<Response><Dial><Conference>{CONFERENCE_NAME}</Conference></Dial></Response>",
    )
    return jsonify({"call_sid": call.sid})


# ---- WebSocket: save audio + forward transcript later ----
@socketio.on("connect", namespace="/media")
def media_connect():
    print("✅ Media WS connected")


@socketio.on("message", namespace="/media")
def media_message(msg):
    try:
        data = json.loads(msg)
        if data["event"] == "media":
            audio_chunk = base64.b64decode(data["media"]["payload"])
            with open("call_audio.raw", "ab") as f:
                f.write(audio_chunk)
        elif data["event"] == "start":
            print("▶️ Stream started")
        elif data["event"] == "stop":
            print("⏹ Stream stopped")
    except Exception as e:
        print("WS error:", e)


@socketio.on("disconnect", namespace="/media")
def media_disconnect():
    print("❌ Media WS disconnected")


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
