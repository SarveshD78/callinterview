import os
from flask import Flask, request, jsonify, render_template
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)

# Load env variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")


@app.route("/")
def index():
    return render_template("index.html")


# ✅ Generate Twilio Capability Token for browser client
@app.route("/token")
def token():
    identity = "browser_user"
    token = AccessToken(
        TWILIO_ACCOUNT_SID,
        os.getenv("TWILIO_API_KEY_SID"),     # optional if you created API Key
        os.getenv("TWILIO_API_KEY_SECRET"), # optional if you created API Key
        identity=identity,
    )

    # Use VoiceGrant
    voice_grant = VoiceGrant(
        outgoing_application_sid=TWILIO_TWIML_APP_SID,
        incoming_allow=True
    )
    token.add_grant(voice_grant)

    return jsonify(identity=identity, token=token.to_jwt().decode())


# ✅ TwiML for outbound call
@app.route("/voice", methods=["POST"])
def voice():
    to_number = request.values.get("To")

    response = VoiceResponse()
    if to_number:
        # Dial out to phone
        dial = response.dial(callerId=TWILIO_NUMBER)
        dial.number(to_number)
    else:
        response.say("Thanks for calling!")

    return str(response)


# ✅ Fallback (when Twilio cannot reach /voice)
@app.route("/fallback", methods=["POST"])
def fallback():
    print("⚠️ Fallback called:", request.values)
    return str(VoiceResponse().say("An error occurred, please try again later."))


# ✅ Call status callback
@app.route("/status", methods=["POST"])
def status():
    print("📞 Call status update:", request.values)
    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
