import Adafruit_DHT
import spidev
import I2C_LCD_driver
import RPi.GPIO as GPIO
import json
import time
import requests
from datetime import datetime

# Sensor and GPIO setup
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21
GPIO.setmode(GPIO.BCM)
GPIO.setup(24, GPIO.OUT)
LCD = I2C_LCD_driver.lcd()

# SPI for LDR sensor
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

# File for storing system state
SYSTEM_STATE_FILE = "system_state.json"

# ThingSpeak API Key
THINGSPEAK_API_KEY = "ATNCBN0ZUFSYGREX"

# Telegram Bot Config
TELEGRAM_TOKEN = "7094057858:AAGU0CMWAcTnuMBJoUmBlg8HxUc8c1Mx3jw"
CHAT_ID = "-1002405515611"

# Timing variables to prevent spam
last_temp_alert_time = None
last_humidity_alert_time = None
last_thingspeak_upload_time = None

# Read system state JSON
def read_system_state():
    try:
        with open(SYSTEM_STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"system": True, "temperature_humidity": True, "ldr": True}

# Read from ADC (LDR sensor)
def readadc(adcnum):
    r = spi.xfer2([1, (8 + adcnum) << 4, 0])
    return ((r[1] & 3) << 8) + r[2]

# Function to check if 24 hours have passed for alerts
def can_send_alert(last_alert_time):
    if last_alert_time is None:
        return True
    return datetime.now() - last_alert_time > timedelta(hours=24)

# Function to upload data to ThingSpeak every 15 sec
def upload_to_thingspeak(temp, humi):
    global last_thingspeak_upload_time
    if last_thingspeak_upload_time is None or (datetime.now() - last_thingspeak_upload_time).seconds >= 15:
        url = f"https://api.thingspeak.com/update?api_key={THINGSPEAK_API_KEY}&field1={temp}&field2={humi}"
        requests.get(url)
        last_thingspeak_upload_time = datetime.now()
        print(f"[INFO] Uploaded Temp: {temp}C, Humidity: {humi}% to ThingSpeak.")

# Function to send Telegram alerts
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message}"
    requests.get(url)

# Main loop
while True:
    system_state = read_system_state()

    if not system_state["system"]:
        LCD.lcd_clear()
        LCD.lcd_display_string("System OFF", 1)
        LCD.lcd_display_string("Enable in Web UI", 2)
        time.sleep(2)
        continue

    temp, humi = None, None
    if system_state["temperature_humidity"]:
        humi, temp = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
        if humi is not None and temp is not None:
            upload_to_thingspeak(temp, humi)
            print(f"[INFO] Temp: {temp}°C, Humidity: {humi}%")

            # Send Telegram alerts if conditions met
            if (temp < 18 or temp > 28) and can_send_alert(last_temp_alert_time):
                send_telegram_alert(f"Alert! Temperature is {temp}°C, outside safe range.")
                last_temp_alert_time = datetime.now()
            
            if humi > 80 and can_send_alert(last_humidity_alert_time):
                send_telegram_alert(f"Alert! Humidity is {humi}%, too high for plants.")
                last_humidity_alert_time = datetime.now()

        else:
            print("[ERROR] Failed to read DHT sensor")

    ldr_value = None
    if system_state["ldr"]:
        ldr_value = readadc(0)
        GPIO.output(24, ldr_value < 500)  # Control LED

    # Update LCD
    LCD.lcd_clear()
    if temp is not None and humi is not None:
        LCD.lcd_display_string(f"T:{temp:.1f}C H:{humi:.1f}%", 1)
    else:
        LCD.lcd_display_string("T:ERR H:ERR", 1)

    if system_state["ldr"]:
        LCD.lcd_display_string(f"LDR:{ldr_value}", 2)
    else:
        LCD.lcd_display_string("LDR:OFF", 2)

    time.sleep(2)
