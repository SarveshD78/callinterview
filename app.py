import os
from flask import Flask, render_template, request, jsonify
from twilio.rest import Client
from twilio.jwt.client import ClientCapabilityToken
from twilio.twiml.voice_response import VoiceResponse
from dotenv import load_dotenv
import logging

# Load environment variables locally
load_dotenv()

app = Flask(__name__)

# Setup detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("CallInterview")

# Twilio configuration
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# -------------------------------
# Home page
# -------------------------------
@app.route('/')
def index():
    logger.debug("Rendering under.html template")
    return render_template('under.html')


# -------------------------------
# Start outbound call to candidate
# -------------------------------
@app.route('/call', methods=['POST'])
def call():
    candidate_number = request.form.get('to')
    logger.debug(f"Call request received for number: {candidate_number}")

    if not candidate_number:
        logger.warning("Candidate number missing in request")
        return jsonify({"error": "Candidate number missing"}), 400

    try:
        call = client.calls.create(
            to=candidate_number,
            from_=TWILIO_NUMBER,
            application_sid=TWIML_APP_SID
        )
        logger.info(f"Call started with SID: {call.sid}")
        return jsonify({"status": "call started", "call_sid": call.sid})
    except Exception as e:
        logger.error(f"Error starting call: {e}")
        return jsonify({"error": str(e)}), 400


# -------------------------------
# Generate Twilio capability token for browser
# -------------------------------
@app.route('/token', methods=['GET'])
def token():
    logger.debug("Generating Twilio capability token for browser")
    capability = ClientCapabilityToken(ACCOUNT_SID, AUTH_TOKEN)
    capability.allow_client_outgoing(TWIML_APP_SID)
    capability.allow_client_incoming("interviewer")  # must match JS client name
    token = capability.to_jwt()
    logger.debug(f"Token generated: {token[:10]}... (truncated)")
    return jsonify(token=token)


# -------------------------------
# TwiML endpoint to connect candidate to browser
# -------------------------------
@app.route('/voice', methods=['POST'])
def voice():
    logger.debug("Voice webhook hit")
    response = VoiceResponse()
    response.dial().client('interviewer')  # connect to browser
    logger.debug(f"TwiML response: {response}")
    return str(response)


# -------------------------------
# Call status updates
# -------------------------------
@app.route('/call-status', methods=['POST'])
def call_status():
    data = request.form.to_dict()
    logger.info(f"Call status update: {data}")
    return '', 200


# -------------------------------
# Run Flask app
# -------------------------------
if __name__ == '__main__':
    logger.info("Starting Flask app")
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)
