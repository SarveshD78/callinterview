import os
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.rest import Client as TwilioRestClient
from twilio.twiml.voice_response import VoiceResponse, Dial

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# -----------------------------
# 🔑 Env variables
# -----------------------------
TWILIO_ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")
TWILIO_API_KEY       = os.getenv("TWILIO_API_KEY")
TWILIO_API_SECRET    = os.getenv("TWILIO_API_SECRET")
TWILIO_NUMBER        = os.getenv("TWILIO_NUMBER")
PUBLIC_BASE_URL      = os.getenv("PUBLIC_BASE_URL")

twilio_client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
CONFERENCE_NAME = "InterviewRoom"  # <-- use consistently

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
        TWILIO_ACCOUNT_SID, TWILIO_API_KEY, TWILIO_API_SECRET, identity=identity
    )
    voice_grant = VoiceGrant(outgoing_application_sid=TWILIO_TWIML_APP_SID, incoming_allow=True)
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

    call = twilio_client.calls.create(
        to=to_number,
        from_=TWILIO_NUMBER,
        url=absolute_url("/voice"),
        status_callback=absolute_url("/status"),
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        status_callback_method="POST"
    )
    return jsonify({"call_sid": call.sid})

@app.route("/voice", methods=["POST"])
def voice():
    response = VoiceResponse()
    dial = Dial()
    dial.conference(
        CONFERENCE_NAME,
        start_conference_on_enter=True,
        end_conference_on_exit=True,
        record="record-from-start"
    )
    response.append(dial)
    return str(response)

@app.route("/transcripts", methods=["POST"])
def transcripts():
    data = request.get_json(force=True)
    socketio.emit("new_transcript", data)
    return ("", 204)

@app.route("/status", methods=["POST"])
def status():
    info = {
        "CallSid": request.values.get("CallSid"),
        "CallStatus": request.values.get("CallStatus"),
        "From": request.values.get("From"),
        "To": request.values.get("To"),
        "Timestamp": request.values.get("Timestamp")
    }
    print(f"[/status] {info}")
    return ("", 200)

# -----------------------------
# Helpers
# -----------------------------
def absolute_url(path: str) -> str:
    base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else request.url_root.rstrip("/")
    if not base.startswith("http"):
        base = "https://" + base.lstrip("/")
    return f"{base}{path}"

# -----------------------------
# Dev server
# -----------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
