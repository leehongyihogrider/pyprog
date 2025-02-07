import Adafruit_DHT
import requests
import spidev
import I2C_LCD_driver
import RPi.GPIO as GPIO
import threading
from time import sleep
from datetime import datetime, timedelta
import queue

# Sensor type: DHT11 or DHT22
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21  # GPIO pin where the sensor is connected

# **ThingSpeak Configuration**
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

# **Last Alert Time Trackers (Declared Globally)**
last_temp_alert_time = None
last_humidity_alert_time = None
last_thingspeak_upload_time = None  # Prevent excessive updates

# Create a queue for user input
input_queue = queue.Queue()

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

def toggle_controls():
    global system_enabled, temp_humi_enabled, ldr_enabled

    while True:
        try:
            key = input_queue.get_nowait().strip().lower()  # Get input without blocking

            if key == "t":
                system_enabled = not system_enabled
                status = "ENABLED" if system_enabled else "DISABLED"
                print(f"\n[INFO] Entire system {status} manually by the user.")

            elif key == "h":
                temp_humi_enabled = not temp_humi_enabled
                status = "ENABLED" if temp_humi_enabled else "DISABLED"
                print(f"\n[INFO] Temperature & Humidity Monitoring {status}.")

            elif key == "l":
                ldr_enabled = not ldr_enabled
                status = "ENABLED" if ldr_enabled else "DISABLED"
                print(f"\n[INFO] LDR Monitoring {status}.")

            elif key == "q":
                print("\n[INFO] Exiting control mode.")
                break  # Exit the loop when 'q' is pressed

            # Update LCD Display
            LCD.lcd_clear()
            if not system_enabled:
                LCD.lcd_display_string("System DISABLED", 1)
                LCD.lcd_display_string("Press 't' to enable", 2)
            else:
                LCD.lcd_display_string(f"Temp: {'ON' if temp_humi_enabled else 'OFF'}", 1)
                LCD.lcd_display_string(f"LDR: {'ON' if ldr_enabled else 'OFF'}", 2)

        except queue.Empty:
            pass  # If queue is empty, do nothing

        sleep(0.1)  # Short delay to prevent CPU overuse

# Start the toggle_controls function in a separate thread
threading.Thread(target=toggle_controls, daemon=True).start()

# **Function to continuously read user input and add it to the queue**
def read_user_input():
    while True:
        user_input = input().strip().lower()
        input_queue.put(user_input)  # Add user input to queue

# Start the user input reader in a separate thread
threading.Thread(target=read_user_input, daemon=True).start()

def upload_to_thingspeak(temp=None, humi=None):
    global last_thingspeak_upload_time

    # Ensure at least 15 seconds have passed before sending data again
    if last_thingspeak_upload_time is None or (datetime.now() - last_thingspeak_upload_time).seconds >= 15:
        url = "https://api.thingspeak.com/update"
        payload = {
            "api_key": "ATNCBN0ZUFSYGREX"
        }

        if temp is not None:
            payload["field1"] = temp
        if humi is not None:
            payload["field2"] = humi

        if "field1" in payload or "field2" in payload:  # Ensure data is present before sending request
            response = requests.get(url, params=payload)
            print(f"[INFO] Data uploaded to ThingSpeak: {response.status_code}")
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
                print(f"[DEBUG] Temp: {temperature}°C, Humidity: {humidity}%")
                upload_to_thingspeak(temp=temperature, humi=humidity)  

                # **Temperature Alert**
                if (temperature < 18 or temperature > 28) and can_send_alert(last_temp_alert_time):
                    last_temp_alert_time = datetime.now()  # ✅ Works now
                    message = f"Alert! The current temperature is {temperature}°C, outside of set threshold!"
                    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}"
                    requests.get(url)

                # **Humidity Alert**
                if humidity > 80 and can_send_alert(last_humidity_alert_time):
                    last_humidity_alert_time = datetime.now()  # ✅ Works now
                    message = f"Alert! The current humidity is {humidity}%, too high for optimal plant growth!"
                    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}"
                    requests.get(url)

            else:
                print("Failed to retrieve data from the sensor. Check wiring!")

        # **LDR Sensor Monitoring**
        if ldr_enabled:
            LDR_value = readadc(0)  
            print(f"LDR = {LDR_value}")
            GPIO.output(24, 1 if LDR_value < 500 else 0)

        # **LCD Display Updates**
        LCD.lcd_display_string(f"Temp: {'ON' if temp_humi_enabled else 'OFF'}", 1)
        LCD.lcd_display_string(f"LDR: {'ON' if ldr_enabled else 'OFF'}", 2)

        sleep(2)  

except KeyboardInterrupt:
    print("\nProgram stopped by user.")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    GPIO.output(24, 0)  
    GPIO.cleanup()
    spi.close()
    LCD.lcd_clear()
