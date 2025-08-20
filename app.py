import os
from flask import Flask, render_template, request, jsonify
from twilio.rest import Client
from twilio.jwt.client import ClientCapabilityToken
from twilio.twiml.voice_response import VoiceResponse
from dotenv import load_dotenv

# Load environment variables locally
load_dotenv()

app = Flask(__name__)

# Twilio configuration
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Home page
@app.route('/')
def index():
    return render_template('under.html')

# Start call to candidate
@app.route('/call', methods=['POST'])
def call():
    candidate_number = request.form.get('to')
    if not candidate_number:
        return jsonify({"error": "Candidate number missing"}), 400
    try:
        call = client.calls.create(
            to=candidate_number,
            from_=TWILIO_NUMBER,
            application_sid=TWIML_APP_SID
        )
        return jsonify({"status": "call started", "call_sid": call.sid})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Generate browser WebRTC token
@app.route('/token', methods=['GET'])
def token():
    capability = ClientCapabilityToken(ACCOUNT_SID, AUTH_TOKEN)
    capability.allow_client_outgoing(TWIML_APP_SID)
    capability.allow_client_incoming("interviewer")
    return jsonify(token=capability.to_jwt())

# TwiML for connecting phone to browser
@app.route('/voice', methods=['POST'])
def voice():
    response = VoiceResponse()
    response.dial().client('interviewer')  # auto-connect
    return str(response)

# Call status updates
@app.route('/call-status', methods=['POST'])
def call_status():
    data = request.form.to_dict()
    print("Call status update:", data)
    return '', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)
