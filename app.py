from flask import Flask, render_template, jsonify, request, redirect, url_for
import sqlite3
import threading
import Adafruit_DHT
import spidev
import I2C_LCD_driver
import RPi.GPIO as GPIO
from time import sleep
from datetime import datetime

# Flask app initialization
app = Flask(__name__)

# GPIO & SPI Setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(24, GPIO.OUT)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

# LCD Display Initialization
LCD = I2C_LCD_driver.lcd()

# Sensor configuration
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21

# System state variables
system_enabled = True
temp_humi_enabled = True
ldr_enabled = True

# SQLite Database Setup
DB_FILE = "sensor_data.db"

def init_db():
    """ Initialize the SQLite database with required tables. """
    conn = sqlite3.connect(DB_FILE)
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

# Run DB initialization
init_db()

def readadc(adcnum):
    """ Read analog value from LDR sensor through SPI """
    if adcnum > 7 or adcnum < 0:
        return -1
    r = spi.xfer2([1, (8 + adcnum) << 4, 0])
    data = ((r[1] & 3) << 8) + r[2]
    return data

def read_sensors():
    """ Background function to read and store sensor data. """
    global system_enabled, temp_humi_enabled, ldr_enabled

    while True:
        if system_enabled:
            temp, humi = None, None

            if temp_humi_enabled:
                humi, temp = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)

            ldr_value = readadc(0) if ldr_enabled else None

            if temp is not None and humi is not None:
                print(f"Logged -> Temp: {temp}, Humi: {humi}, LDR: {ldr_value}")

                # Store in SQLite
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute(
                    "INSERT INTO readings (temperature, humidity, ldr_value) VALUES (?, ?, ?)",
                    (temp, humi, ldr_value)
                )
                conn.commit()
                conn.close()

            sleep(2)  # Read every 2 seconds

# Start background sensor reading thread
threading.Thread(target=read_sensors, daemon=True).start()

@app.route("/")
def home():
    """ Render homepage with system status. """
    return render_template("index.html",
                           system_enabled=system_enabled,
                           temp_humi_enabled=temp_humi_enabled,
                           ldr_enabled=ldr_enabled)

@app.route("/toggle", methods=["POST"])
def toggle_system():
    """ Handle system state toggles from UI. """
    global system_enabled, temp_humi_enabled, ldr_enabled

    toggle_type = request.form.get("toggle")

    if toggle_type == "system":
        system_enabled = not system_enabled
    elif toggle_type == "temp_humi":
        temp_humi_enabled = not temp_humi_enabled
    elif toggle_type == "ldr":
        ldr_enabled = not ldr_enabled

    return redirect(url_for("home"))

@app.route("/chart")
def chart():
    """ Render the chart page """
    return render_template("chart.html")

@app.route("/data")
def get_data():
    """ Return last 20 readings as JSON for charting """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT timestamp, temperature, humidity, ldr_value FROM readings ORDER BY timestamp DESC LIMIT 20")
    data = c.fetchall()
    conn.close()

    # Format data as JSON
    readings = [
        {"timestamp": row[0], "temperature": row[1], "humidity": row[2], "ldr_value": row[3]}
        for row in data
    ]
    
    return jsonify(readings)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
