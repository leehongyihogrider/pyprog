import Adafruit_DHT
import requests
import spidev
import I2C_LCD_driver
import RPi.GPIO as GPIO
import threading
from time import sleep
from datetime import datetime, timedelta
import keyboard  # Keyboard module for detecting key presses

# Sensor type: DHT11 or DHT22
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21  # GPIO pin where the sensor is connected

# **ThingSpeak Configuration**
THINGSPEAK_API_KEY = "ATNCBN0ZUFSYGREX"
THINGSPEAK_CHANNEL_ID = "2746200"
THINGSPEAK_UPDATE_URL = "https://api.thingspeak.com/update"

# **Telegram Bot Configuration**
TOKEN = "7094057858:AAGU0CMWAcTnuMBJoUmBlg8HxUc8c1Mx3jw"
chat_id = "-1002405515611"

# **SPI and GPIO Setup**
spi = spidev.SpiDev()
spi.open(0, 0)  # Open SPI port 0, device 0
spi.max_speed_hz = 1350000

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(24, GPIO.OUT)

# **LCD Initialization**
LCD = I2C_LCD_driver.lcd()

# **System Control Variables**
system_enabled = True   # Controls the entire system
temp_humi_enabled = True  # Controls temperature and humidity readings
ldr_enabled = True      # Controls LDR monitoring

# **Last Alert Time Trackers**
last_temp_alert_time = None
last_humidity_alert_time = None
last_thingspeak_upload_time = None  # Prevent excessive updates

# Function to check if 24 hours have passed for alerts
def can_send_alert(last_alert_time):
    if last_alert_time is None:
        return True
    return datetime.now() - last_alert_time > timedelta(days=1)

# Read from the MCP3008 (SPI ADC)
def readadc(adcnum):
    if adcnum > 7 or adcnum < 0:
        return -1
    r = spi.xfer2([1, (8 + adcnum) << 4, 0])
    data = ((r[1] & 3) << 8) + r[2]
    return data

# Function to toggle system and individual components
def toggle_controls():
    global system_enabled, temp_humi_enabled, ldr_enabled

    while True:
        event = keyboard.read_event()  # Wait for keypress

        if event.event_type == keyboard.KEY_DOWN:
            if event.name == "t":
                system_enabled = not system_enabled
                status = "ENABLED" if system_enabled else "DISABLED"
                print(f"\n[INFO] Entire system {status} manually by the user.")

            elif event.name == "h":
                temp_humi_enabled = not temp_humi_enabled
                status = "ENABLED" if temp_humi_enabled else "DISABLED"
                print(f"\n[INFO] Temperature & Humidity Monitoring {status}.")

            elif event.name == "l":
                ldr_enabled = not ldr_enabled
                status = "ENABLED" if ldr_enabled else "DISABLED"
                print(f"\n[INFO] LDR Monitoring {status}.")

            # Update LCD
            LCD.lcd_clear()
            if not system_enabled:
                LCD.lcd_display_string("System DISABLED", 1)
                LCD.lcd_display_string("Press 't' to enable", 2)
            else:
                LCD.lcd_display_string(f"Temp: {'ON' if temp_humi_enabled else 'OFF'}", 1)
                LCD.lcd_display_string(f"LDR: {'ON' if ldr_enabled else 'OFF'}", 2)

            sleep(1)  # Prevent rapid toggling

# Start the keyboard listener in a separate thread
threading.Thread(target=toggle_controls, daemon=True).start()

# **Function to Upload Data to ThingSpeak**
def upload_to_thingspeak(temp=None, humi=None):
    global last_thingspeak_upload_time

    # Ensure at least 15 seconds have passed before sending data again
    if last_thingspeak_upload_time is None or (datetime.now() - last_thingspeak_upload_time).seconds >= 15:
        payload = {
            "api_key": THINGSPEAK_API_KEY
        }

        if temp is not None:
            payload["field1"] = temp
            response = requests.get(THINGSPEAK_UPDATE_URL, params=payload)
            if response.status_code == 200:
                print(f"[INFO] Temperature {temp}°C uploaded to ThingSpeak")
            else:
                print(f"[ERROR] Failed to upload temperature. Status: {response.status_code}")

        if humi is not None:
            payload["field2"] = humi
            response = requests.get(THINGSPEAK_UPDATE_URL, params=payload)
            if response.status_code == 200:
                print(f"[INFO] Humidity {humi}% uploaded to ThingSpeak")
            else:
                print(f"[ERROR] Failed to upload humidity. Status: {response.status_code}")

        last_thingspeak_upload_time = datetime.now()

try:
    while True:
        # **Check if system is disabled**
        if not system_enabled:
            LCD.lcd_display_string("System DISABLED", 1)
            LCD.lcd_display_string("Press 't' to enable", 2)
            print("\n[INFO] User has disabled the plant care system.")
            sleep(2)
            continue  # Skip sensor readings

        # **Temperature & Humidity Readings**
        if temp_humi_enabled:
            humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)

            if humidity is not None and temperature is not None:
                # **Send to ThingSpeak separately**
                upload_to_thingspeak(temp=temperature)
                upload_to_thingspeak(humi=humidity)

                # Temperature alert
                if (temperature < 18 or temperature > 28) and can_send_alert(last_temp_alert_time):
                    message = f"Alert! The current temperature is {temperature}°C, outside of set threshold!"
                    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}"
                    requests.get(url)
                    last_temp_alert_time = datetime.now()

                # Humidity alert
                if humidity > 80 and can_send_alert(last_humidity_alert_time):
                    message = f"Alert! The current humidity is {humidity}%, too high for optimal plant growth!"
                    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}"
                    requests.get(url)
                    last_humidity_alert_time = datetime.now()
            else:
                print("Failed to retrieve data from the sensor. Check wiring!")

        # **LDR Sensor Monitoring**
        if ldr_enabled:
            LDR_value = readadc(0)  # Read ADC channel 0 (LDR)
            print(f"LDR = {LDR_value}")
            GPIO.output(24, 1 if LDR_value < 500 else 0)

        # **LCD Display Updates**
        LCD.lcd_display_string(f"Temp: {'ON' if temp_humi_enabled else 'OFF'}", 1)
        LCD.lcd_display_string(f"LDR: {'ON' if ldr_enabled else 'OFF'}", 2)

        sleep(2)  # Delay for stability

except KeyboardInterrupt:
    print("\nProgram stopped by user.")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    GPIO.output(24, 0)  # Ensure LED is off
    GPIO.cleanup()
    spi.close()
    LCD.lcd_clear()
