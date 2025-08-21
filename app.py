# import os
# from flask import Flask, request, jsonify, render_template
# from twilio.jwt.access_token import AccessToken
# from twilio.jwt.access_token.grants import VoiceGrant
# from twilio.twiml.voice_response import VoiceResponse

# app = Flask(__name__)

# # 🔑 Load Twilio credentials from env
# TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
# TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
# TWILIO_TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")   # APxxxxxxxx
# TWILIO_API_KEY = os.getenv("TWILIO_API_KEY")               # SKxxxxxxxx
# TWILIO_API_SECRET = os.getenv("TWILIO_API_SECRET")
# TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")                 # Your Twilio phone no.


# # Serve frontend
# @app.route("/")
# def index():
#     return render_template("index.html")


# # ✅ 1. Provide JWT Access Token to browser
# @app.route("/token")
# def token():
#     token = AccessToken(
#         TWILIO_ACCOUNT_SID,
#         TWILIO_API_KEY,
#         TWILIO_API_SECRET,
#         identity="browser_user"  # 👈 identity for Web Client
#     )

#     voice_grant = VoiceGrant(
#         outgoing_application_sid=TWILIO_TWIML_APP_SID,
#         incoming_allow=True
#     )
#     token.add_grant(voice_grant)

#     return jsonify({"token": token.to_jwt()})


# # ✅ 2. TwiML: What happens when browser makes a call
# @app.route("/voice", methods=["POST"])
# def voice():
#     to_number = request.form.get("To")
#     response = VoiceResponse()

#     if to_number:
#         # Call a real phone number
#         dial = response.dial(callerId=TWILIO_NUMBER)
#         dial.number(to_number)
#     else:
#         # If no number → connect back to client
#         response.dial().client("browser_user")

#     return str(response)


# # ✅ 3. Fallback (if TwiML App fails)
# @app.route("/fallback", methods=["POST"])
# def fallback():
#     app.logger.error("Fallback triggered: %s", request.values)
#     return ("", 200)


# # ✅ 4. Status callback (logs ringing, answered, completed)
# @app.route("/status", methods=["POST"])
# def status():
#     call_sid = request.values.get("CallSid")
#     call_status = request.values.get("CallStatus")
#     app.logger.info(f"Call {call_sid} status: {call_status}")
#     return ("", 200)


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5000, debug=True)

import os
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse, Start, Stream

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# 🔑 Load Twilio credentials from env
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")   # APxxxxxxxx
TWILIO_API_KEY = os.getenv("TWILIO_API_KEY")               # SKxxxxxxxx
TWILIO_API_SECRET = os.getenv("TWILIO_API_SECRET")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")                 # Your Twilio phone no.


# Serve frontend
@app.route("/")
def index():
    return render_template("index.html")


# ✅ 1. Provide JWT Access Token to browser
@app.route("/token")
def token():
    token = AccessToken(
        TWILIO_ACCOUNT_SID,
        TWILIO_API_KEY,
        TWILIO_API_SECRET,
        identity="browser_user"  # 👈 identity for Web Client
    )

    voice_grant = VoiceGrant(
        outgoing_application_sid=TWILIO_TWIML_APP_SID,
        incoming_allow=True
    )
    token.add_grant(voice_grant)

    return jsonify({"token": token.to_jwt()})


# ✅ 2. TwiML: What happens when browser makes a call
@app.route("/voice", methods=["POST"])
def voice():
    to_number = request.form.get("To")
    response = VoiceResponse()

    # Start real-time stream to our websocket endpoint
    start = Start()
    start.stream(url="wss://your-ngrok-id.ngrok-free.app/media")   # 👈 change this
    response.append(start)

    if to_number:
        # Call a real phone number
        dial = response.dial(callerId=TWILIO_NUMBER)
        dial.number(to_number)
    else:
        # If no number → connect back to client
        response.dial().client("browser_user")

    return str(response)


# ✅ 3. WebSocket: Twilio Media Stream events
@socketio.on("connect")
def handle_connect():
    app.logger.info("Client connected for transcription")

@socketio.on("disconnect")
def handle_disconnect():
    app.logger.info("Client disconnected")


@app.route("/media", methods=["POST"])
def media():
    """
    Twilio will POST audio events here in real-time.
    You would typically send this audio to a transcription engine.
    For demo, we just emit fake text events.
    """
    event = request.json.get("event", "")
    if event == "media":
        # Here you’d normally decode audio and send to STT service
        # Example: forward to OpenAI Realtime / Deepgram / Google STT
        transcript = "🗣 (demo) someone is speaking..."
        socketio.emit("transcript", {"text": transcript})
    return ("", 200)


# ✅ 4. Fallback (if TwiML App fails)
@app.route("/fallback", methods=["POST"])
def fallback():
    app.logger.error("Fallback triggered: %s", request.values)
    return ("", 200)


# ✅ 5. Status callback (logs ringing, answered, completed)
@app.route("/status", methods=["POST"])
def status():
    call_sid = request.values.get("CallSid")
    call_status = request.values.get("CallStatus")
    app.logger.info(f"Call {call_sid} status: {call_status}")
    return ("", 200)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)

