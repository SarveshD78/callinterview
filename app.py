import os
import base64
import json
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO
from flask_sockets import Sockets
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")   # for transcripts → browser
sockets = Sockets(app)                               # Twilio Media raw WS

# ---- Twilio credentials from env ----
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWIML_APP_SID = os.getenv("TWIML_APP_SID")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

CONFERENCE_NAME = "interview-room"

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


@app.route("/")
def index():
    return render_template("index.html")


# --- Token for browser Twilio.Device ---
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
    return jsonify({"token": token.to_jwt().decode("utf-8")})


# --- TwiML for browser device ---
@app.route("/voice", methods=["POST"])
def voice():
    response = VoiceResponse()
    response.start().stream(url="wss://shark-app-fu64d.ondigitalocean.app/media")
    dial = response.dial()
    dial.conference(
        CONFERENCE_NAME,
        start_conference_on_enter=True,
        end_conference_on_exit=False
    )
    return str(response)


# --- REST endpoint to call candidate ---
@app.route("/call", methods=["POST"])
def call():
    data = request.get_json()
    to_number = data.get("to")
    if not to_number:
        return jsonify({"error": "Missing number"}), 400

    twiml = f"""
    <Response>
      <Start>
        <Stream url="wss://shark-app-fu64d.ondigitalocean.app/media" />
      </Start>
      <Dial>
        <Conference>{CONFERENCE_NAME}</Conference>
      </Dial>
    </Response>
    """

    call = client.calls.create(
        to=to_number,
        from_=TWILIO_PHONE_NUMBER,
        twiml=twiml
    )
    return jsonify({"call_sid": call.sid})


# --- Twilio Media Streams raw WebSocket ---
@sockets.route("/media")
def media(ws):
    print("✅ Twilio Media Stream connected")
    while not ws.closed:
        msg = ws.receive()
        if msg is None:
            break

        try:
            data = json.loads(msg)
            event = data.get("event")

            if event == "start":
                print("▶️ Stream started:", data["start"].get("streamSid"))

            elif event == "media":
                payload = data["media"]["payload"]
                audio_chunk = base64.b64decode(payload)
                # Save audio for debugging
                with open("call_audio.raw", "ab") as f:
                    f.write(audio_chunk)

                # TODO: pass `audio_chunk` to STT
                # Example push:
                # socketio.emit("new_transcript", {"text": "hello", "is_final": False})

            elif event == "stop":
                print("⏹ Stream stopped")

        except Exception as e:
            print("WS error:", e)

    print("❌ Twilio Media Stream disconnected")


if __name__ == "__main__":
    # IMPORTANT: When deploying with gunicorn + gevent, run like:
    # gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 app:app -b 0.0.0.0:5000
    socketio.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
