import os
from flask import Flask, request, jsonify, render_template, Response
from flask_socketio import SocketIO
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.rest import Client as TwilioRestClient
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# -----------------------------
# 🔑 Required env variables
# -----------------------------
TWILIO_ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")
TWILIO_API_KEY       = os.getenv("TWILIO_API_KEY")
TWILIO_API_SECRET    = os.getenv("TWILIO_API_SECRET")
TWILIO_NUMBER        = os.getenv("TWILIO_NUMBER")
PUBLIC_BASE_URL      = os.getenv("PUBLIC_BASE_URL")

print("[INIT] Loading environment variables...")
print(f"[INIT] TWILIO_ACCOUNT_SID: {TWILIO_ACCOUNT_SID}")
print(f"[INIT] TWILIO_TWIML_APP_SID: {TWILIO_TWIML_APP_SID}")
print(f"[INIT] TWILIO_NUMBER: {TWILIO_NUMBER}")
print(f"[INIT] PUBLIC_BASE_URL: {PUBLIC_BASE_URL}")

# Twilio REST client
twilio_client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

CONFERENCE_NAME = "interview_room"

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    print("[ROUTE /] Rendering index.html")
    return render_template("index.html")

@app.route("/token")
def token():
    print("[ROUTE /token] Generating token for browser user")
    identity = "browser_user"

    token = AccessToken(
        TWILIO_ACCOUNT_SID,
        TWILIO_API_KEY,
        TWILIO_API_SECRET,
        identity=identity
    )
    print("[/token] AccessToken created")

    voice_grant = VoiceGrant(
        outgoing_application_sid=TWILIO_TWIML_APP_SID,
        incoming_allow=True
    )
    token.add_grant(voice_grant)
    print("[/token] VoiceGrant added")

    jwt_token = token.to_jwt()
    if hasattr(jwt_token, "decode"):
        jwt_token = jwt_token.decode("utf-8")
    print("[/token] Returning JWT token")
    return jsonify({"token": jwt_token})

@app.route("/call", methods=["POST"])
def call_candidate():
    print("[ROUTE /call] Incoming request to call candidate")
    data = request.get_json(force=True)
    print(f"[/call] Request JSON: {data}")

    to_number = data.get("to")
    if not to_number:
        print("[/call] ERROR: Missing 'to' phone number")
        return jsonify({"error": "Missing 'to' phone number"}), 400

    voice_url = absolute_url("/voice")
    print(f"[/call] Dialing {to_number} from {TWILIO_NUMBER}, voice_url={voice_url}")

    call = twilio_client.calls.create(
        to=to_number,
        from_=TWILIO_NUMBER,
        url=voice_url,
        status_callback=absolute_url("/status"),
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        status_callback_method="POST"
    )
    print(f"[/call] Call created with SID: {call.sid}")
    return jsonify({"call_sid": call.sid})

from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Dial

app = Flask(__name__)

@app.route("/voice", methods=['POST'])
def voice():
    """Twilio hits this whenever a call (browser or candidate) connects"""
    response = VoiceResponse()
    dial = Dial()

    # fixed room name — browser & phone MUST match this
    dial.conference(
        "InterviewRoom",  # <--- important: consistent name!
        start_conference_on_enter=True,
        end_conference_on_exit=True,
        record="record-from-start"   # optional, if you want recordings
    )

    response.append(dial)
    return str(response)



@app.route("/transcripts", methods=["POST"])
def transcripts():
    print("[ROUTE /transcripts] Got transcription event")
    try:
        data = request.get_json(force=True)
    except Exception as e:
        print(f"[/transcripts] ERROR parsing JSON: {e}")
        return ("", 400)

    print(f"[/transcripts] Data: {data}")
    socketio.emit("new_transcript", data)
    print("[/transcripts] Emitted new_transcript to browser via Socket.IO")
    return ("", 204)

@app.route("/status", methods=["POST"])
def status():
    print("[ROUTE /status] Call status update received")
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
    full_url = f"{base}{path}"
    print(f"[HELPER absolute_url] Built URL: {full_url}")
    return full_url

# -----------------------------
# Dev server
# -----------------------------
if __name__ == "__main__":
    print("[MAIN] Starting Flask-SocketIO server on 0.0.0.0:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
