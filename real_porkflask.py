from flask import Flask, render_template, jsonify, request
import sqlite3
import threading
import time
import Adafruit_DHT
import spidev
import RPi.GPIO as GPIO
from datetime import datetime

# Flask App
app = Flask(__name__)

# Sensor Setup
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21  # GPIO pin
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(24, GPIO.OUT)

# System Control Variables
system_enabled = True
temp_humi_enabled = True
ldr_enabled = True

# Database Setup
DB_FILE = "sensor_data.db"
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                temperature REAL,
                humidity REAL,
                ldr_value INTEGER
            )
        """)
        conn.commit()
init_db()

# Read LDR Sensor
def readadc(adcnum):
    if adcnum > 7 or adcnum < 0:
        return -1
    r = spi.xfer2([1, (8 + adcnum) << 4, 0])
    data = ((r[1] & 3) << 8) + r[2]
    return data

# Background Task for Sensor Readings
def sensor_loop():
    global system_enabled, temp_humi_enabled, ldr_enabled
    while True:
        if system_enabled:
            humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN) if temp_humi_enabled else (None, None)
            ldr_value = readadc(0) if ldr_enabled else None
            
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO readings (temperature, humidity, ldr_value) VALUES (?, ?, ?)",
                               (temperature, humidity, ldr_value))
                conn.commit()
            print(f"Logged -> Temp: {temperature}, Humi: {humidity}, LDR: {ldr_value}")
        time.sleep(2)

threading.Thread(target=sensor_loop, daemon=True).start()

# Flask Routes
@app.route('/')
def home():
    return render_template("index.html", system_enabled=system_enabled, temp_humi_enabled=temp_humi_enabled, ldr_enabled=ldr_enabled)

@app.route('/data')
def get_data():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, temperature, humidity, ldr_value FROM readings ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        data = [{"timestamp": row[0], "temperature": row[1], "humidity": row[2], "ldr": row[3]} for row in rows]
    return jsonify(data[::-1])

@app.route('/toggle', methods=['POST'])
def toggle():
    global system_enabled, temp_humi_enabled, ldr_enabled
    setting = request.json.get("setting")
    if setting == "system":
        system_enabled = not system_enabled
    elif setting == "temp_humi":
        temp_humi_enabled = not temp_humi_enabled
    elif setting == "ldr":
        ldr_enabled = not ldr_enabled
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
