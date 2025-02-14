import Adafruit_DHT
import requests
import spidev
import I2C_LCD_driver
import RPi.GPIO as GPIO
import sys
import select
from time import sleep
from datetime import datetime, timedelta

# Global timing variables to prevent alert/upload spam
last_temp_alert_time = None
last_humidity_alert_time = None
last_thingspeak_upload_time = None
last_valid_temperature = None
last_valid_humidity = None
led_on = False  # Track LED state

# Hardware configuration
DHT_SENSOR = Adafruit_DHT.DHT11  # Using DHT11 temperature/humidity sensor
DHT_PIN = 21  # GPIO pin for DHT11 sensor

# Cloud service configurations
THINGSPEAK_UPDATE_URL = "https://api.thingspeak.com/update"
TOKEN = "7094057858:AAGU0CMWAcTnuMBJoUmBlg8HxUc8c1Mx3jw"  # Telegram bot token
chat_id = "-1002405515611"  # Telegram chat ID for notifications

# Initialize SPI communication for LDR sensor
spi = spidev.SpiDev()
spi.open(0, 0)  # Open SPI port 0, device 0
spi.max_speed_hz = 1350000

# Set up GPIO for LED control
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(24, GPIO.OUT)  # GPIO 24 controls LED

# Initialize LCD display
LCD = I2C_LCD_driver.lcd()

# System state flags
system_enabled = True   # Master switch for entire system
temp_humi_enabled = True  # Control temperature/humidity monitoring
ldr_enabled = True      # Control light level monitoring

def can_send_alert(last_alert_time):
    """Prevent alert spam by checking if 24 hours have passed since last alert"""
    if last_alert_time is None:
        return True
    return datetime.now() - last_alert_time > timedelta(days=1)

def readadc(adcnum):
    """Read analog value from LDR sensor through SPI"""
    if adcnum > 7 or adcnum < 0:
        return -1
    r = spi.xfer2([1, (8 + adcnum) << 4, 0])
    data = ((r[1] & 3) << 8) + r[2]
    return data

def upload_to_thingspeak(temp=None, humi=None):
    """Upload sensor data to ThingSpeak with 15-second rate limiting"""
    global last_thingspeak_upload_time

    if last_thingspeak_upload_time is None or (datetime.now() - last_thingspeak_upload_time).seconds >= 15:
        url = "https://api.thingspeak.com/update"
        payload = {"api_key": "ATNCBN0ZUFSYGREX"}

        if temp is not None:
            payload["field1"] = temp
        if humi is not None:
            payload["field2"] = humi

        if "field1" in payload or "field2" in payload:
            response = requests.get(url, params=payload)
            print(f"[INFO] Data uploaded to ThingSpeak: {response.status_code}")
            last_thingspeak_upload_time = datetime.now()

def handle_temperature_humidity():
    """Monitor temperature/humidity and send alerts if thresholds exceeded"""
    global last_temp_alert_time, last_humidity_alert_time, last_valid_temperature, last_valid_humidity

    humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)

    if humidity is not None and temperature is not None:
        last_valid_temperature = temperature
        last_valid_humidity = humidity
        print(f"[DEBUG] Temp: {temperature}°C, Humidity: {humidity}%")
        upload_to_thingspeak(temp=temperature, humi=humidity)

        if (temperature < 18 or temperature > 28) and can_send_alert(last_temp_alert_time):
            message = f"Alert! The current temperature is {temperature}°C, outside of set threshold!"
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}"
            requests.get(url)
            last_temp_alert_time = datetime.now()

        if humidity > 80 and can_send_alert(last_humidity_alert_time):
            message = f"Alert! The current humidity is {humidity}%, too high for optimal plant growth!"
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}"
            requests.get(url)
            last_humidity_alert_time = datetime.now()
    else:
        print("Failed to retrieve data from the sensor. Check wiring!")

def update_lcd():
    """Update LCD display with current system status"""
    LCD.lcd_clear()
    
    if not system_enabled:
        LCD.lcd_display_string("System DISABLED", 1)
        LCD.lcd_display_string("Press 't' to enable", 2)
    else:
        if temp_humi_enabled:
            if last_valid_temperature is not None and last_valid_humidity is not None:
                LCD.lcd_display_string(f"T:{last_valid_temperature:.1f}C H:{last_valid_humidity:.1f}%", 1)
            else:
                LCD.lcd_display_string("T:ERR H:ERR", 1)
        else:
            LCD.lcd_display_string("T:OFF H:OFF", 1)

        if ldr_enabled:
            LDR_value = readadc(0)
            LCD.lcd_display_string(f"LDR:{LDR_value}", 2)
        else:
            LCD.lcd_display_string("LDR:OFF", 2)

try:
    while True:
        # Check for keyboard input without blocking
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1).strip().lower()

            if key == "t":
                system_enabled = not system_enabled
                print(f"\n[INFO] System {'ENABLED' if system_enabled else 'DISABLED'} manually.")

            elif key == "h":
                temp_humi_enabled = not temp_humi_enabled
                print(f"\n[INFO] Temp & Humidity {'ENABLED' if temp_humi_enabled else 'DISABLED'}.")

            elif key == "l":
                ldr_enabled = not ldr_enabled
                print(f"\n[INFO] LDR Monitoring {'ENABLED' if ldr_enabled else 'DISABLED'}.")

            elif key == "q":
                print("\n[INFO] Exiting program.")
                break

            update_lcd()  # Ensure LCD updates after input

        if not system_enabled:
            print("\n[INFO] System disabled. Waiting for activation...")
            update_lcd()
            sleep(2)
            continue

        if temp_humi_enabled:
            handle_temperature_humidity()

        if ldr_enabled:
            LDR_value = readadc(0)
            print(f"LDR = {LDR_value}")
            if LDR_value < 500 and not led_on:
                GPIO.output(24, 1)  # Turn on LED if light level is low
                led_on = True
            elif LDR_value >= 500 and led_on:
                GPIO.output(24, 0)  # Turn off LED
                led_on = False

        update_lcd()  # Keep LCD updated
        sleep(2)

except KeyboardInterrupt:
    print("\n[INFO] Program stopped by user.")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    print("\n[INFO] Cleaning up resources before exit...")
    GPIO.output(24, 0)
    GPIO.cleanup()
    spi.close()
    LCD.lcd_clear()
    print("[INFO] System has safely shut down.")
