from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# User table tracks each relevant user or device in the system.
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    phone_id = db.Column(db.String(100), unique=True)

# Beacon table describes each room/ESP32 node or BLE beacon location.
class Beacon(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    location = db.Column(db.String(100))
    type = db.Column(db.String(50))

# BLE Event table this is the core table for BLE sightings ("User X seen by Beacon Y at this time")
class BLEEvent(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    beacon_id = db.Column(db.Integer, db.ForeignKey('beacon.id'))
    timestamp = db.Column(db.DateTime)
    rssi = db.Column(db.Integer)  # Signal strength, useful for proximity estimation and setting a threshold for detection

class RoomEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    beacon_id = db.Column(db.Integer, db.ForeignKey('beacon.id'))
    entry_time = db.Column(db.DateTime)
    exit_time = db.Column(db.DateTime)
    avg_rssi = db.Column(db.Integer)

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(100), unique=True, nullable = False)
    metadata = db.Column(db.JSON, nullable= True)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

