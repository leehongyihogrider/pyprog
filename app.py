from flask import Flask, render_template, request, jsonify
import sqlite3
import threading
import Adafruit_DHT
import spidev
import RPi.GPIO as GPIO
from time import sleep
from datetime import datetime

# Initialize Flask
app = Flask(__name__)

# Sensor & GPIO Configuration
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(24, GPIO.OUT)

# System Control Flags
system_enabled = True
temp_humi_enabled = True
ldr_enabled = True

# Database Initialization
def init_db():
    conn = sqlite3.connect("sensor_data.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            temperature REAL,
            humidity REAL,
            ldr_value INTEGER
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Function to Read from LDR Sensor
def read_adc(channel):
    if channel > 7 or channel < 0:
        return -1
    r = spi.xfer2([1, (8 + channel) << 4, 0])
    return ((r[1] & 3) << 8) + r[2]

# Function to Read & Store Sensor Data
def read_sensors():
    global system_enabled, temp_humi_enabled, ldr_enabled
    while True:
        if system_enabled:
            temp, humi = None, None
            if temp_humi_enabled:
                humi, temp = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
            
            ldr = read_adc(0) if ldr_enabled else None

            # Store in database
            conn = sqlite3.connect("sensor_data.db")
            c = conn.cursor()
            c.execute("INSERT INTO readings (temperature, humidity, ldr_value) VALUES (?, ?, ?)",
                      (temp, humi, ldr))
            conn.commit()
            conn.close()

            print(f"Logged -> Temp: {temp}, Humi: {humi}, LDR: {ldr}")

        sleep(2)  # Read every 2 seconds

# Start Sensor Reading in Background
threading.Thread(target=read_sensors, daemon=True).start()

# Flask Routes
@app.route("/")
def home():
    return render_template("index.html", system_enabled=system_enabled, temp_humi_enabled=temp_humi_enabled, ldr_enabled=ldr_enabled)

@app.route("/chart")
def chart():
    return render_template("chart.html")

@app.route("/data")
def get_data():
    conn = sqlite3.connect("sensor_data.db")
    c = conn.cursor()
    c.execute("SELECT timestamp, temperature, humidity, ldr_value FROM readings ORDER BY timestamp DESC LIMIT 20")
    data = [{"timestamp": row[0], "temperature": row[1], "humidity": row[2], "ldr_value": row[3]} for row in c.fetchall()]
    conn.close()
    return jsonify(data[::-1])  # Reverse for correct order in chart

@app.route("/toggle", methods=["POST"])
def toggle():
    global system_enabled, temp_humi_enabled, ldr_enabled

    toggle_type = request.form.get("toggle")
    
    if toggle_type == "system":
        system_enabled = not system_enabled
    elif toggle_type == "temp_humi":
        temp_humi_enabled = not temp_humi_enabled
    elif toggle_type == "ldr":
        ldr_enabled = not ldr_enabled

    return jsonify({
        "system_enabled": system_enabled,
        "temp_humi_enabled": temp_humi_enabled,
        "ldr_enabled": ldr_enabled
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
