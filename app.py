import os
from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse

# Flask setup
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "super-secret-key")

# SocketIO setup with gevent
socketio = SocketIO(app, cors_allowed_origins="*")

# Twilio credentials (env vars must be set in DO App Spec)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_API_KEY_SID = os.getenv("TWILIO_API_KEY_SID")
TWILIO_API_KEY_SECRET = os.getenv("TWILIO_API_KEY_SECRET")
TWILIO_APP_SID = os.getenv("TWILIO_APP_SID")  # TwiML App SID


@app.route("/")
def index():
    return "🚀 Flask + Twilio app is running!"


# ---- Token endpoint for Twilio JS SDK ----
@app.route("/token", methods=["GET"])
def token():
    identity = request.args.get("identity", "interviewer")

    token = AccessToken(
        TWILIO_ACCOUNT_SID,
        TWILIO_API_KEY_SID,
        TWILIO_API_KEY_SECRET,
        identity=identity,
    )

    voice_grant = VoiceGrant(
        outgoing_application_sid=TWILIO_APP_SID,
        incoming_allow=True,
    )
    token.add_grant(voice_grant)

    # ✅ Fix: no .decode()
    return jsonify({"identity": identity, "token": token.to_jwt()})


# ---- Twilio Voice webhook (conference example) ----
@app.route("/voice", methods=["POST"])
def voice():
    response = VoiceResponse()
    dial = response.dial()
    dial.conference("InterviewRoom")
    return str(response)


# ---- Socket.IO events ----
@socketio.on("connect")
def handle_connect():
    print("Client connected")


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
