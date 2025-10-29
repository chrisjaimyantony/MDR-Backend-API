from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime
import os

MONGO_URI = os.environ.get("MONGO_URI")
# -----------------------
# Flask App Setup
# -----------------------
app = Flask(__name__)
CORS(app)  # Allow Android app to call Flask API

# -----------------------
# MongoDB Atlas Connection
# -----------------------
# MONGO_URI = "mongodb+srv://chrisjaimyantony_db_user:wmzacOeKu77KpBiL@mdr-cluster.ci4krd.mongodb.net/"
MONGO_URI = "mongodb+srv://chrisjaimyantony_db_user:wmzacOeKu77KpBiL@mdr-cluster.ci4krd.mongodb.net/?retryWrites=true&w=majority&appName=MDR-Cluster"
client = MongoClient(MONGO_URI)
db = client['MDR']  # Database name
devices_collection = db['devices']
events_collection = db['ble_events']

# -----------------------
# Register Device (Android App)an
# -----------------------
@app.route('/api/register_device', methods=['POST'])
def register_device():
    """
    Called by Android app after generating a unique UUID.
    Example JSON:
    {
        "uuid": "unique_device_uuid",
        "metadata": {"model": "Pixel 5"}
    }
    """
    data = request.get_json()

    if not data or 'uuid' not in data:
        return jsonify({'error': 'Missing uuid field'}), 400

    # Check if already exists
    if devices_collection.find_one({'uuid': data['uuid']}):
        return jsonify({'message': 'Device already registered'}), 200

    new_device = {
        'uuid': data['uuid'],
        'metadata': data.get('metadata', {}),
        'created_at': datetime.utcnow()
    }
    devices_collection.insert_one(new_device)

    return jsonify({'success': True, 'message': 'Device registered successfully'}), 201


# -----------------------
# Add BLE Event (ESP32 Beacon)
# -----------------------
@app.route('/api/ble_event', methods=['POST'])
def add_ble_event():
    """
    Called by ESP32 when it detects a BLE UUID nearby.
    Example JSON:
    {
        "uuid": "unique_device_uuid",
        "beacon_id": "101",
        "rssi": -70,
        "timestamp": "2023-10-01T12:00:00"
    }
    """
    data = request.get_json()

    if not data or 'uuid' not in data or 'beacon_id' not in data:
        return jsonify({'error': 'Missing required fields'}), 400

    # Store event in MongoDB
    new_event = {
        'uuid': data['uuid'],
        'beacon_id': data['beacon_id'],
        'rssi': data.get('rssi', None),
        'timestamp': data.get('timestamp', datetime.utcnow().isoformat())
    }
    events_collection.insert_one(new_event)

    return jsonify({'success': True, 'message': 'BLE event recorded'}), 201


# -----------------------
# Check Device (ESP32 Beacon Verification)
# -----------------------
@app.route('/api/check_device', methods=['POST'])
def check_device():
    """
    Used by ESP32 beacons to verify if a UUID is registered.
    Example JSON:
    {
        "uuid": "a-unique-device-uuid",
        "beacon_id": "101"
    }
    """
    data = request.get_json()
    if not data or 'uuid' not in data:
        return jsonify({'error': 'Missing uuid field'}), 400

    exists = devices_collection.find_one({'uuid': data['uuid']}) is not None
    return jsonify({'exists': exists}), 200

# -----------------------
# Get All Registered Devices (for Android App)
# -----------------------
@app.route('/api/devices', methods=['GET'])
def get_devices():
    """
    Returns a list of all registered devices.
    """
    try:
        # Projection {'_id': 0} excludes the default MongoDB _id field
        devices = list(devices_collection.find({}, {'_id': 0}))
        return jsonify(devices), 200
    except Exception as e:
        print(f"Error fetching devices: {e}")
        return jsonify({'error': 'Could not fetch devices'}), 500
    

# -----------------------
# Root Endpoint (For Testing)
# -----------------------
@app.route('/')
def index():
    return "✅ MDR RLTS API connected to MongoDB Atlas and running."


# -----------------------
# Main Entry Point
# -----------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)