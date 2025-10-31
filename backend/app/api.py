from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file
IST = timezone(timedelta(hours=5, minutes=30))

MONGO_URI = os.environ.get("MONGO_URI")

if not MONGO_URI:
    # This check ensures you know immediately if the variable wasn't set during deployment
    print("FATAL ERROR")
    exit(1)

try:
    client = MongoClient(MONGO_URI)
    client.admin.command('ping') # Good practice to verify connection immediately
    print("Successfully connected to MongoDB Atlas.")
except Exception as e:
    print(f"ERROR: Could not connect to MongoDB Atlas: {e}")
    exit(1)
# -----------------------
# Flask App Setup
# -----------------------
app = Flask(__name__)
CORS(app)  # Allow Android app to call Flask API

# -----------------------
# MongoDB Atlas Connection
# -----------------------
db = client['MDR']  # Database name
devices_collection = db['devices']
entries_collection = db['ble_entries']
exits_collection   = db['ble_exits']
presence_collection = db['presence']

# -----------------------
# Register Device (Android App)an
# -----------------------
@app.route('/api/register_device', methods=['POST'])
def register_device():
    data = request.get_json()
    if not data or 'uuid' not in data:
        return jsonify({'error': 'Missing uuid field'}), 400

    if devices_collection.find_one({'uuid': data['uuid']}):
        return jsonify({'message': 'Device already registered'}), 200

    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(IST)

    new_device = {
        'uuid': data['uuid'],
        'short_id': data.get('short_id'),
        'metadata': data.get('metadata', {}),
        'registered_at_ist': now_ist.isoformat(timespec='microseconds'),
    }
    devices_collection.insert_one(new_device)
    return jsonify({'success': True, 'message': 'Device registered successfully'}), 201


# -----------------------
# Add BLE Event (ESP32 Beacon)
# -----------------------
@app.route('/api/ble_event', methods=['POST'])
def add_ble_event():
    data = request.get_json()
    if not data or 'uuid' not in data or 'beacon_id' not in data:
        return jsonify({'error': 'Missing required fields'}), 400

    uuid = data['uuid']
    beacon_id = data['beacon_id']
    rssi = data.get('rssi')

    now_ist = datetime.now(IST)
    ts_ist = now_ist.isoformat(timespec='microseconds')
    # Helpful denormalized features for ML
    day_ist = now_ist.strftime('%Y-%m-%d')
    hour_ist = now_ist.strftime('%H')

    TOGGLE_GUARD_SEC = 8

    pres = presence_collection.find_one({'uuid': uuid, 'beacon_id': beacon_id})
    write_collection = None
    event_type = None

    if not pres or pres.get('state') == 'outside':
        # Entry
        event_type = 'entry'
        write_collection = entries_collection
        presence_collection.update_one(
            {'uuid': uuid, 'beacon_id': beacon_id},
            {'$set': {
                'state': 'inside',
                'last_event': 'entry',
                'last_seen_ist': ts_ist,
                'last_rssi': rssi
            }},
            upsert=True
        )
    else:
        # Exit with anti-flap guard (compare IST)
        within_guard = False
        last_seen_ist = pres.get('last_seen_ist')
        if last_seen_ist:
            try:
                last_dt = datetime.fromisoformat(last_seen_ist.replace('Z', '+00:00'))
                # last_dt already contains +05:30 if inserted by this API; fromisoformat handles it
                diff = (now_ist - last_dt).total_seconds()
                within_guard = diff < TOGGLE_GUARD_SEC
            except Exception:
                within_guard = False

        if within_guard:
            # Update heartbeat only
            presence_collection.update_one(
                {'uuid': uuid, 'beacon_id': beacon_id},
                {'$set': {'last_seen_ist': ts_ist, 'last_rssi': rssi}}
            )
            return jsonify({'success': True, 'message': 'heartbeat', 'suppressed': True}), 201

        event_type = 'exit'
        write_collection = exits_collection
        presence_collection.update_one(
            {'uuid': uuid, 'beacon_id': beacon_id},
            {'$set': {
                'state': 'outside',
                'last_event': 'exit',
                'last_seen_ist': ts_ist,
                'last_rssi': rssi
            }}
        )

    doc = {
        'uuid': uuid,
        'beacon_id': beacon_id,
        'rssi': rssi,
        'ist_timestamp': ts_ist,
        'day_ist': day_ist,
        'hour_ist': hour_ist
    }
    write_collection.insert_one(doc)
    return jsonify({'success': True, 'type': event_type}), 201


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