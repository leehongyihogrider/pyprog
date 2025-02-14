from flask import Flask, render_template, request, jsonify, redirect
import requests
import Adafruit_DHT
import spidev
import RPi.GPIO as GPIO
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# --- Hardware Configuration ---
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(24, GPIO.OUT)

# --- System Control Flags ---
system_enabled = True
temp_humi_enabled = True
ldr_enabled = True
last_valid_temperature = None
last_valid_humidity = None
led_on = False  # Track LED state

# --- ThingSpeak Configuration ---
THINGSPEAK_CHANNEL_ID = "2746200"
THINGSPEAK_API_KEY = "ATNCBN0ZUFSYGREX"
THINGSPEAK_URL = "https://api.thingspeak.com/update"

# --- LCD Setup ---
import I2C_LCD_driver
LCD = I2C_LCD_driver.lcd()

# --- Read LDR Sensor ---
def read_adc(channel):
    if channel > 7 or channel < 0:
        return -1
    r = spi.xfer2([1, (8 + channel) << 4, 0])
    return ((r[1] & 3) << 8) + r[2]

# --- Read & Upload Sensor Data ---
def read_sensors():
    global system_enabled, temp_humi_enabled, ldr_enabled, last_valid_temperature, last_valid_humidity, led_on
    
    while True:
        if system_enabled:
            temp, humi = None, None
            if temp_humi_enabled:
                humi, temp = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)

            ldr = read_adc(0) if ldr_enabled else None

            if temp is not None and humi is not None:
                last_valid_temperature = temp
                last_valid_humidity = humi
                print(f"Logged -> Temp: {temp}, Humi: {humi}, LDR: {ldr}")

                # Upload to ThingSpeak
                params = {
                    "api_key": THINGSPEAK_API_KEY,
                    "field1": temp,
                    "field2": humi,
                    "field3": ldr
                }
                requests.get(THINGSPEAK_URL, params=params)

            # Control LED based on LDR
            if ldr_enabled and ldr is not None:
                if ldr < 500 and not led_on:
                    GPIO.output(24, 1)
                    led_on = True
                elif ldr >= 500 and led_on:
                    GPIO.output(24, 0)
                    led_on = False

        time.sleep(2)

# --- Background Sensor Thread ---
threading.Thread(target=read_sensors, daemon=True).start()

# --- Flask Routes ---
@app.route("/")
def home():
    return render_template("index.html", system_enabled=system_enabled, temp_humi_enabled=temp_humi_enabled, ldr_enabled=ldr_enabled)

@app.route("/chart")
def chart():
    return redirect(f"https://thingspeak.com/channels/{THINGSPEAK_CHANNEL_ID}")

@app.route("/toggle", methods=["POST"])
def toggle():
    global system_enabled, temp_humi_enabled, ldr_enabled

    toggle_type = request.json.get("toggle")
    
    if toggle_type == "system":
        system_enabled = not system_enabled
    elif toggle_type == "temp_humi":
        temp_humi_enabled = not temp_humi_enabled
    elif toggle_type == "ldr":
        ldr_enabled = not ldr_enabled

    # Update LCD display after toggle
    update_lcd()

    print(f"TOGGLE: {toggle_type} -> System: {system_enabled}, Temp/Humi: {temp_humi_enabled}, LDR: {ldr_enabled}")

    return jsonify({
        "system_enabled": system_enabled,
        "temp_humi_enabled": temp_humi_enabled,
        "ldr_enabled": ldr_enabled
    })

# --- LCD Update Function ---
def update_lcd():
    LCD.lcd_clear()

    if not system_enabled:
        LCD.lcd_display_string("System DISABLED", 1)
        LCD.lcd_display_string("Press 't' to enable", 2)
    else:
        LCD.lcd_display_string(f"T:{last_valid_temperature if last_valid_temperature else 'ERR'} H:{last_valid_humidity if last_valid_humidity else 'ERR'}", 1)
        LCD.lcd_display_string(f"LDR: {'ON' if ldr_enabled else 'OFF'}", 2)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
