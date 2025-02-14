import Adafruit_DHT
import requests
import spidev
import I2C_LCD_driver
import RPi.GPIO as GPIO
import json
import time
from datetime import datetime, timedelta

# Global Variables
last_temp_alert_time = None
last_humidity_alert_time = None
last_thingspeak_upload_time = None
last_valid_temperature = None
last_valid_humidity = None
led_on = False  # Track LED state

# Sensor Configurations
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21

# Cloud Configurations
THINGSPEAK_API_KEY = "ATNCBN0ZUFSYGREX"
THINGSPEAK_URL = "https://api.thingspeak.com/update"
TELEGRAM_TOKEN = "7094057858:AAGU0CMWAcTnuMBJoUmBlg8HxUc8c1Mx3jw"
CHAT_ID = "-1002405515611"

# SPI (LDR Sensor)
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

# GPIO Setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(24, GPIO.OUT)  # LED

# LCD Setup
LCD = I2C_LCD_driver.lcd()

# Read System State from JSON
def load_system_state():
    try:
        with open("system_state.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"system": True, "temp_humi": True, "ldr": True}

def save_system_state(state):
    with open("system_state.json", "w") as file:
        json.dump(state, file)

# Read ADC Data (LDR Sensor)
def readadc(adcnum):
    if adcnum > 7 or adcnum < 0:
        return -1
    r = spi.xfer2([1, (8 + adcnum) << 4, 0])
    return ((r[1] & 3) << 8) + r[2]

# Upload Data to ThingSpeak
def upload_to_thingspeak(temp=None, humi=None):
    global last_thingspeak_upload_time
    if last_thingspeak_upload_time is None or (datetime.now() - last_thingspeak_upload_time).seconds >= 15:
        payload = {"api_key": THINGSPEAK_API_KEY}
        if temp is not None:
            payload["field1"] = temp
        if humi is not None:
            payload["field2"] = humi
        requests.get(THINGSPEAK_URL, params=payload)
        last_thingspeak_upload_time = datetime.now()

# Handle Temperature & Humidity Monitoring
def handle_temperature_humidity():
    global last_valid_temperature, last_valid_humidity, last_temp_alert_time, last_humidity_alert_time

    humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
    if humidity is not None and temperature is not None:
        last_valid_temperature, last_valid_humidity = temperature, humidity
        upload_to_thingspeak(temp=temperature, humi=humidity)

        if (temperature < 18 or temperature > 28) and last_temp_alert_time is None:
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                         params={"chat_id": CHAT_ID, "text": f"⚠ Temp Alert: {temperature}°C"})
            last_temp_alert_time = datetime.now()

        if humidity > 80 and last_humidity_alert_time is None:
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                         params={"chat_id": CHAT_ID, "text": f"⚠ Humidity Alert: {humidity}%"})
            last_humidity_alert_time = datetime.now()
    else:
        print("[WARNING] Sensor error! Check wiring.")

# Update LCD Display
def update_lcd(state):
    LCD.lcd_clear()
    if not state["system"]:
        LCD.lcd_display_string("System DISABLED", 1)
        LCD.lcd_display_string("Press 'Enable'", 2)
        return

    temp_display = f"T:{last_valid_temperature or 'ERR'}C H:{last_valid_humidity or 'ERR'}%"
    ldr_display = f"LDR: {'ON' if state['ldr'] else 'OFF'}"
    LCD.lcd_display_string(temp_display, 1)
    LCD.lcd_display_string(ldr_display, 2)

# Main Loop
try:
    while True:
        system_state = load_system_state()
        update_lcd(system_state)

        if system_state["system"]:
            if system_state["temp_humi"]:
                handle_temperature_humidity()

            if system_state["ldr"]:
                LDR_value = readadc(0)
                GPIO.output(24, 1 if LDR_value < 500 else 0)

        time.sleep(2)

except KeyboardInterrupt:
    print("\n[INFO] Exiting program...")

finally:
    GPIO.cleanup()
    spi.close()
    LCD.lcd_clear()
