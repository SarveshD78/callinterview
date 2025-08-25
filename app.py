import os
import json
import base64
import wave
import audioop
from flask import Flask, request, render_template, jsonify
from flask_socketio import SocketIO
from flask_sockets import Sockets
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.rest import Client

# Flask + Socket setup
app = Flask(__name__)
socketio = SocketIO(app)
sockets = Sockets(app)

# Twilio creds (from env vars)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_API_KEY = os.getenv("TWILIO_API_KEY_SID")
TWILIO_API_SECRET = os.getenv("TWILIO_API_KEY_SECRET")
TWILIO_APP_SID = os.getenv("TWILIO_APP_SID")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

client = Client(TWILIO_API_KEY, TWILIO_API_SECRET, TWILIO_ACCOUNT_SID)

# =============== Browser UI ===============
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/token")
def token():
    identity = "browser_user"
    token = AccessToken(TWILIO_ACCOUNT_SID, TWILIO_API_KEY, TWILIO_API_SECRET, identity=identity)
    token.add_grant(VoiceGrant(outgoing_application_sid=TWILIO_APP_SID, incoming_allow=True))
    return jsonify({"token": token.to_jwt().decode()})

@app.route("/call", methods=["POST"])
def call():
    data = request.json
    number = data.get("to")
    call = client.calls.create(
        to=number,
        from_=TWILIO_PHONE_NUMBER,
        url=request.url_root + "twiml"  # when call connects, hit /twiml
    )
    return jsonify({"call_sid": call.sid})

# =============== Twilio Streaming ===============
@app.route("/twiml", methods=["POST", "GET"])
def twiml():
    return render_template("streams.xml")

@sockets.route("/media")
def media_stream(ws):
    """Receive audio packets from Twilio Media Stream and save to WAV"""
    print("🔗 Media stream connected")
    has_seen_media = False

    # setup WAV file
    wav = wave.open("call_audio.wav", "wb")
    wav.setnchannels(1)  # mono
    wav.setsampwidth(2)  # 16-bit PCM
    wav.setframerate(8000)

    while not ws.closed:
        message = ws.receive()
        if message is None:
            continue
        data = json.loads(message)

        if data["event"] == "start":
            print("▶️ Stream started")
        elif data["event"] == "media":
            if not has_seen_media:
                print("🎤 Receiving audio...")
                has_seen_media = True
            audio_chunk = base64.b64decode(data["media"]["payload"])
            # Convert μ-law to PCM16
            pcm16 = audioop.ulaw2lin(audio_chunk, 2)
            wav.writeframes(pcm16)
        elif data["event"] == "stop":
            print("⏹️ Stream stopped")
            break

    wav.close()
    print("💾 Saved call_audio.wav")

# =============== Run ===============
if __name__ == "__main__":
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(("", 5000), app, handler_class=WebSocketHandler)
    print("🚀 Server running at http://localhost:5000")
    server.serve_forever()
