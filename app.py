from flask import Flask, render_template, jsonify, request
import threading
import time
import sqlite3
import Adafruit_DHT
import spidev
import RPi.GPIO as GPIO

app = Flask(__name__)

# Sensor & GPIO Setup
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000
GPIO.setmode(GPIO.BCM)
GPIO.setup(24, GPIO.OUT)

# System Control Variables
system_enabled = True
temp_humi_enabled = True
ldr_enabled = True

# Create Database & Store Readings
def init_db():
    conn = sqlite3.connect("sensor_data.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS readings 
                (timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, temperature REAL, humidity REAL, ldr INTEGER)''')
    conn.commit()
    conn.close()

def read_adc(channel):
    r = spi.xfer2([1, (8 + channel) << 4, 0])
    return ((r[1] & 3) << 8) + r[2]

def read_sensors():
    global system_enabled, temp_humi_enabled, ldr_enabled
    while True:
        if system_enabled:
            temp, humi = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN) if temp_humi_enabled else (None, None)
            ldr = read_adc(0) if ldr_enabled else None
            
            conn = sqlite3.connect("sensor_data.db")
            c = conn.cursor()
            c.execute("INSERT INTO readings (temperature, humidity, ldr) VALUES (?, ?, ?)", (temp, humi, ldr))
            conn.commit()
            conn.close()
            print(f"Logged -> Temp: {temp}, Humi: {humi}, LDR: {ldr}")

        time.sleep(2)

# Start Background Sensor Reading
threading.Thread(target=read_sensors, daemon=True).start()

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
    c.execute("SELECT timestamp, temperature, humidity, ldr FROM readings ORDER BY timestamp DESC LIMIT 20")
    data = [{"time": row[0], "temperature": row[1], "humidity": row[2], "ldr": row[3]} for row in c.fetchall()]
    conn.close()
    return jsonify(data[::-1])

@app.route("/toggle", methods=["POST"])
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

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
