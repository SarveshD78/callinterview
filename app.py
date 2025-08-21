import os
from flask import Flask, request, jsonify, render_template
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)

# Env variables
ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
API_KEY_SID = os.environ.get("TWILIO_API_KEY_SID")
API_KEY_SECRET = os.environ.get("TWILIO_API_KEY_SECRET")
APP_SID = os.environ.get("TWILIO_APP_SID")
CALLER_ID = os.environ.get("TWILIO_CALLER_ID")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/token")
def token():
    identity = "user-browser"
    token = AccessToken(ACCOUNT_SID, API_KEY_SID, API_KEY_SECRET, identity=identity)
    voice_grant = VoiceGrant(outgoing_application_sid=APP_SID, incoming_allow=True)
    token.add_grant(voice_grant)
    return jsonify(identity=identity, token=token.to_jwt().decode("utf-8"))


# 1️⃣ Main Voice URL
@app.route("/voice", methods=["POST"])
def voice():
    to_number = request.form.get("To")
    response = VoiceResponse()
    if to_number:
        dial = response.dial(callerId=CALLER_ID)
        dial.number(to_number)
    else:
        response.say("No number provided.")
    print("[VOICE LOG]", request.form)
    return str(response)


# 2️⃣ Fallback URL
@app.route("/fallback", methods=["POST"])
def fallback():
    print("[FALLBACK LOG]", request.form)
    response = VoiceResponse()
    response.say("We are sorry, something went wrong with your call.")
    return str(response)


# 3️⃣ Status Callback URL
@app.route("/status", methods=["POST"])
def status():
    print("[STATUS LOG]", request.form)
    return ("", 204)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
