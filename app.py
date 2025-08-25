import os
import json
import base64
import wave

from flask import Flask, request, jsonify, render_template
from flask_sockets import Sockets
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant

# Flask app + WebSocket setup
app = Flask(__name__)
sockets = Sockets(app)

# Twilio credentials (set via environment variables)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_API_KEY = os.getenv("TWILIO_API_KEY")
TWILIO_API_SECRET = os.getenv("TWILIO_API_SECRET")
TWIML_APP_SID = os.getenv("TWIML_APP_SID")

HTTP_SERVER_PORT = int(os.getenv("PORT", 8080))


def log(*args):
    print("Media WS:", *args)


# ------------------------------
# Routes
# ------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/token")
def token():
    """Return AccessToken for Twilio.Device"""
    identity = "browser_user"
    token = AccessToken(
        TWILIO_ACCOUNT_SID,
        TWILIO_API_KEY,
        TWILIO_API_SECRET,
        identity=identity,
    )
    voice_grant = VoiceGrant(outgoing_application_sid=TWIML_APP_SID)
    token.add_grant(voice_grant)

    return jsonify({"token": token.to_jwt().decode("utf-8")})


@app.route("/twiml", methods=["POST"])
def return_twiml():
    """Return TwiML that connects call to WebSocket stream"""
    return render_template("streams.xml")


# ------------------------------
# WebSocket Handler
# ------------------------------

@sockets.route("/media")
def media_stream(ws):
    log("WebSocket connection accepted")

    # Create wav file for saving audio
    wf = wave.open("call_audio.wav", "wb")
    wf.setnchannels(1)       # mono
    wf.setsampwidth(2)       # 16-bit
    wf.setframerate(8000)    # Twilio streams at 8kHz

    count = 0
    while not ws.closed:
        message = ws.receive()
        if message is None:
            continue

        data = json.loads(message)

        if data["event"] == "start":
            log("Start event received")
        elif data["event"] == "media":
            audio_chunk = base64.b64decode(data["media"]["payload"])
            wf.writeframes(audio_chunk)
        elif data["event"] == "stop":
            log("Stop event received")
            break

        count += 1

    wf.close()
    log(f"Connection closed. Saved audio to call_audio.wav, received {count} messages")


# ------------------------------
# Run Locally
# ------------------------------
if __name__ == "__main__":
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler

    server = pywsgi.WSGIServer(
        ("", HTTP_SERVER_PORT), app, handler_class=WebSocketHandler
    )
    print(f"Server listening on http://localhost:{HTTP_SERVER_PORT}")
    server.serve_forever()
