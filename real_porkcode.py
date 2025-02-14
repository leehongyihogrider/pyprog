import Adafruit_DHT
import requests
import spidev
import I2C_LCD_driver
import RPi.GPIO as GPIO
import json
import os
from time import sleep
from datetime import datetime, timedelta

# Global timing variables
last_temp_alert_time = None
last_humidity_alert_time = None
last_thingspeak_upload_time = None
last_valid_temperature = None
last_valid_humidity = None
led_on = False  

# Hardware configuration
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21  

# Initialize SPI communication for LDR sensor
spi = spidev.SpiDev()
spi.open(0, 0)  
spi.max_speed_hz = 1350000

# Set up GPIO for LED control
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(24, GPIO.OUT)  

# Initialize LCD display
LCD = I2C_LCD_driver.lcd()

# ThingSpeak API
THINGSPEAK_API_KEY = "ATNCBN0ZUFSYGREX"  # Change this to your API key
THINGSPEAK_UPDATE_URL = "https://api.thingspeak.com/update"
TOKEN = "7094057858:AAGU0CMWAcTnuMBJoUmBlg8HxUc8c1Mx3jw"
chat_id = "-1002405515611"  

def load_system_state():
    """Loads the system state from JSON or creates a default one if missing."""
    default_state = {"system": True, "temp_humi": True, "ldr": True}

    if not os.path.exists("system_state.json"):
        save_system_state(default_state)
        return default_state

    try:
        with open("system_state.json", "r") as file:
            state = json.load(file)
            if not all(k in state for k in ["system", "temp_humi", "ldr"]):
                raise ValueError("Missing keys in system_state.json")
            return state
    except (json.JSONDecodeError, ValueError):
        print("[ERROR] system_state.json corrupted! Resetting...")
        save_system_state(default_state)
        return default_state


def save_system_state(state):
    """Writes system state to JSON file."""
    with open("system_state.json", "w") as file:
        json.dump(state, file)


def update_lcd(state):
    """Update LCD display based on system state."""
    LCD.lcd_clear()

    if not state["system"]:
        LCD.lcd_display_string("System DISABLED", 1)
        LCD.lcd_display_string("Re-enable via toggle", 2)
    else:
        if state["temp_humi"]:
            if last_valid_temperature is not None and last_valid_humidity is not None:
                LCD.lcd_display_string(f"T:{last_valid_temperature:.1f}C H:{last_valid_humidity:.1f}%", 1)
            else:
                LCD.lcd_display_string("T:ERR H:ERR", 1)
        else:
            LCD.lcd_display_string("T:OFF H:OFF", 1)

        if state["ldr"]:
            LDR_value = readadc(0)
            LCD.lcd_display_string(f"LDR:{LDR_value}", 2)
        else:
            LCD.lcd_display_string("LDR:OFF", 2)


def readadc(adcnum):
    """Read analog value from LDR sensor through SPI"""
    if adcnum > 7 or adcnum < 0:
        return -1
    r = spi.xfer2([1, (8 + adcnum) << 4, 0])
    data = ((r[1] & 3) << 8) + r[2]
    return data


def upload_to_thingspeak(temp, humi, ldr):
    """Uploads data to ThingSpeak every 15 seconds."""
    global last_thingspeak_upload_time

    if last_thingspeak_upload_time is None or (datetime.now() - last_thingspeak_upload_time).seconds >= 15:
        payload = {
            "api_key": THINGSPEAK_API_KEY,
            "field1": temp,
            "field2": humi,
            "field3": ldr
        }

        response = requests.get(THINGSPEAK_UPDATE_URL, params=payload)
        if response.status_code == 200:
            print(f"[INFO] Data uploaded to ThingSpeak successfully.")
            last_thingspeak_upload_time = datetime.now()
        else:
            print(f"[ERROR] ThingSpeak upload failed: {response.status_code}")


def handle_temperature_humidity(state):
    """Monitor temperature/humidity and send alerts if thresholds exceeded"""
    global last_temp_alert_time, last_humidity_alert_time, last_valid_temperature, last_valid_humidity

    if not state["temp_humi"]:
        return  

    humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)

    if humidity is not None and temperature is not None:
        last_valid_temperature = temperature
        last_valid_humidity = humidity
        print(f"[DEBUG] Temp: {temperature}°C, Humidity: {humidity}%")

    else:
        print("Failed to retrieve data from the sensor. Check wiring!")


try:
    while True:
        state = load_system_state()
        update_lcd(state)

        if not state["system"]:
            print("\n[INFO] System disabled. Waiting for activation...")
            sleep(2)
            continue

        handle_temperature_humidity(state)

        if state["ldr"]:
            LDR_value = readadc(0)
            print(f"LDR = {LDR_value}")

        # Upload data to ThingSpeak
        if last_valid_temperature is not None and last_valid_humidity is not None:
            upload_to_thingspeak(last_valid_temperature, last_valid_humidity, LDR_value)

        sleep(2)

except KeyboardInterrupt:
    print("\n[INFO] Program stopped by user.")

finally:
    print("\n[INFO] Cleaning up resources before exit...")
    GPIO.output(24, 0)
    GPIO.cleanup()
    spi.close()
    LCD.lcd_clear()
    print("[INFO] System has safely shut down.")
