import Adafruit_DHT
import requests
import spidev
import I2C_LCD_driver
import RPi.GPIO as GPIO
import sys
import select
from time import sleep
from datetime import datetime, timedelta

# === 🌟 GLOBAL VARIABLES ===
last_temp_alert_time = None  # Last temperature alert sent
last_humidity_alert_time = None  # Last humidity alert sent
last_thingspeak_upload_time = None  # Last ThingSpeak upload timestamp
last_valid_temperature = None  # Last valid temperature reading
last_valid_humidity = None  # Last valid humidity reading
ldr_threshold = 500  # Threshold value for LDR sensor
led_on = False  # LED state tracker

# === 🌡️ SENSOR CONFIGURATION ===
DHT_SENSOR = Adafruit_DHT.DHT11  # Using DHT11 sensor
DHT_PIN = 21  # GPIO pin for DHT sensor

# === ☁️ THINGSPEAK CONFIGURATION ===
THINGSPEAK_CHANNEL_ID = "2746200"
THINGSPEAK_UPDATE_URL = "https://api.thingspeak.com/update"
THINGSPEAK_API_KEY = "ATNCBN0ZUFSYGREX"

# === 📩 TELEGRAM CONFIGURATION ===
TOKEN = "7094057858:AAGU0CMWAcTnuMBJoUmBlg8HxUc8c1Mx3jw"  # Telegram Bot Token
chat_id = "-1002405515611"  # Chat ID for Telegram alerts

# === 🛠️ HARDWARE SETUP ===
# SPI setup for LDR sensor (MCP3008 ADC)
spi = spidev.SpiDev()
spi.open(0, 0)  # Open SPI port 0, device 0
spi.max_speed_hz = 1350000

# GPIO setup for LED control
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(24, GPIO.OUT)  # GPIO 24 controls LED

# LCD Initialization
LCD = I2C_LCD_driver.lcd()

# === 🚀 SYSTEM CONTROL FLAGS ===
system_enabled = True  # Controls the entire system
temp_humi_enabled = True  # Controls temperature & humidity monitoring
ldr_enabled = True  # Controls LDR monitoring


# === 🔄 FUNCTION: Check Alert Timing ===
def can_send_alert(last_alert_time):
    """Prevent alert spam by ensuring at least 24 hours have passed"""
    if last_alert_time is None:
        return True
    return datetime.now() - last_alert_time > timedelta(days=1)


# === 📡 FUNCTION: Read LDR Sensor ===
def readadc(adcnum):
    """Read analog value from LDR sensor via SPI"""
    if adcnum > 7 or adcnum < 0:
        return -1
    r = spi.xfer2([1, (8 + adcnum) << 4, 0])
    data = ((r[1] & 3) << 8) + r[2]
    return data


# === ☁️ FUNCTION: Upload Data to ThingSpeak ===
def upload_to_thingspeak(temp=None, humi=None):
    """Upload temperature & humidity data to ThingSpeak with rate limiting"""
    global last_thingspeak_upload_time

    if last_thingspeak_upload_time is None or (datetime.now() - last_thingspeak_upload_time).seconds >= 15:
        payload = {"api_key": THINGSPEAK_API_KEY}

        if temp is not None:
            payload["field1"] = temp
        if humi is not None:
            payload["field2"] = humi

        if "field1" in payload or "field2" in payload:
            try:
                response = requests.get(THINGSPEAK_UPDATE_URL, params=payload)
                if response.status_code == 200:
                    print("[INFO] Data uploaded to ThingSpeak successfully.")
                    last_thingspeak_upload_time = datetime.now()
                else:
                    print(f"[ERROR] ThingSpeak upload failed: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] ThingSpeak request failed: {e}")


# === 🌡️ FUNCTION: Handle Temperature & Humidity ===
def handle_temperature_humidity():
    """Read temperature & humidity, send alerts, and update ThingSpeak"""
    global last_temp_alert_time, last_humidity_alert_time
    global last_valid_temperature, last_valid_humidity

    humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)

    if humidity is not None and temperature is not None:
        last_valid_temperature = temperature
        last_valid_humidity = humidity
        print(f"[DEBUG] Temp: {temperature}°C, Humidity: {humidity}%")
        upload_to_thingspeak(temp=temperature, humi=humidity)

        if (temperature < 18 or temperature > 28) and can_send_alert(last_temp_alert_time):
            message = f"Alert! The current temperature is {temperature}°C, outside of set threshold!"
            requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}")
            last_temp_alert_time = datetime.now()

        if humidity > 80 and can_send_alert(last_humidity_alert_time):
            message = f"Alert! The current humidity is {humidity}%, too high for optimal plant growth!"
            requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}")
            last_humidity_alert_time = datetime.now()
    else:
        print("[ERROR] Failed to retrieve data from sensor. Using last valid readings.")


# === 🔦 FUNCTION: Handle LDR Sensor & LED ===
def handle_ldr():
    """Monitor light level and control LED based on threshold"""
    global led_on
    LDR_value = readadc(0)

    if LDR_value < ldr_threshold and not led_on:
        GPIO.output(24, 1)  # Turn ON LED
        led_on = True
        print("[INFO] LED turned ON due to low light.")
    elif LDR_value >= ldr_threshold and led_on:
        GPIO.output(24, 0)  # Turn OFF LED
        led_on = False
        print("[INFO] LED turned OFF due to sufficient light.")


# === 🚀 MAIN LOOP ===
try:
    while True:
        # Check for keyboard input without blocking execution
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1).strip().lower()

            # Toggle system features
            if key == "t":
                system_enabled = not system_enabled
                print(f"[INFO] System {'ENABLED' if system_enabled else 'DISABLED'}")
            elif key == "h":
                temp_humi_enabled = not temp_humi_enabled
                print(f"[INFO] Temp & Humidity Monitoring {'ENABLED' if temp_humi_enabled else 'DISABLED'}")
            elif key == "l":
                ldr_enabled = not ldr_enabled
                print(f"[INFO] LDR Monitoring {'ENABLED' if ldr_enabled else 'DISABLED'}")
            elif key == "q":
                print("\n[INFO] Exiting program.")
                break

        if not system_enabled:
            print("\n[INFO] System is disabled. Press 't' to enable.")
            sleep(2)
            continue

        if temp_humi_enabled:
            handle_temperature_humidity()

        if ldr_enabled:
            handle_ldr()

        sleep(2)

except KeyboardInterrupt:
    print("\nProgram stopped by user.")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    print("\n[INFO] Cleaning up resources before exit...")
    GPIO.output(24, 0)  # Ensure LED is off
    GPIO.cleanup()
    spi.close()
    LCD.lcd_clear()
    print("[INFO] System has safely shut down.")
