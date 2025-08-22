import os
import base64
import json
import asyncio
import websockets

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# 🔑 Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")
TWILIO_API_KEY = os.getenv("TWILIO_API_KEY")
TWILIO_API_SECRET = os.getenv("TWILIO_API_SECRET")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")

# Serve frontend
@app.route("/")
def index():
    return render_template("index.html")

# ✅ Token endpoint
@app.route("/token")
def token():
    token = AccessToken(
        TWILIO_ACCOUNT_SID,
        TWILIO_API_KEY,
        TWILIO_API_SECRET,
        identity="browser_user"
    )
    voice_grant = VoiceGrant(
        outgoing_application_sid=TWILIO_TWIML_APP_SID,
        incoming_allow=True
    )
    token.add_grant(voice_grant)
    return jsonify({"token": token.to_jwt()})

# ✅ TwiML for calls
@app.route("/voice", methods=["POST"])
def voice():
    to_number = request.form.get("To")
    response = VoiceResponse()

    # Start media stream for transcription
    response.start().stream(url="wss://shark-app-fu64d.ondigitalocean.app/media")

    if to_number:
        dial = response.dial(callerId=TWILIO_NUMBER)
        dial.number(to_number)
    else:
        response.dial().client("browser_user")

    return str(response)

# ✅ Fallback
@app.route("/fallback", methods=["POST"])
def fallback():
    app.logger.error("Fallback triggered: %s", request.values)
    return ("", 200)

# ✅ Status callback
@app.route("/status", methods=["POST"])
def status():
    call_sid = request.values.get("CallSid")
    call_status = request.values.get("CallStatus")
    app.logger.info(f"Call {call_sid} status: {call_status}")
    return ("", 200)

# ✅ WebSocket endpoint for Twilio Media Streams
# Twilio will connect here and send audio packets
async def media_handler(websocket, path):
    async for message in websocket:
        data = json.loads(message)

        # When audio comes in
        if data.get("event") == "media":
            # Base64-encoded audio PCM16
            audio_chunk = base64.b64decode(data["media"]["payload"])
            # 👉 Here you would send audio_chunk to OpenAI/Deepgram/etc.
            # For now we just simulate a transcript
            fake_text = "Simulated transcript line..."
            socketio.emit("new_transcript", {"text": fake_text})

        elif data.get("event") == "start":
            app.logger.info("Media stream started")

        elif data.get("event") == "stop":
            app.logger.info("Media stream stopped")

# Start WebSocket server in background
def start_ws_server():
    import threading
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = websockets.serve(media_handler, "0.0.0.0", 8765)  # Port 8765
    loop.run_until_complete(server)
    loop.run_forever()

import threading
threading.Thread(target=start_ws_server, daemon=True).start()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
