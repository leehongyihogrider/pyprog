import Adafruit_DHT
import requests
import spidev
import I2C_LCD_driver
import RPi.GPIO as GPIO
import json
import time
from datetime import datetime, timedelta

# Path to system state JSON file
STATE_FILE = "system_state.json"

# Function to load system state
def load_system_state():
    with open(STATE_FILE, "r") as f:
        return json.load(f)

# Initialize sensors and LCD
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(24, GPIO.OUT)
LCD = I2C_LCD_driver.lcd()

def readadc(adcnum):
    """Read LDR sensor data from SPI"""
    if adcnum > 7 or adcnum < 0:
        return -1
    r = spi.xfer2([1, (8 + adcnum) << 4, 0])
    return ((r[1] & 3) << 8) + r[2]

def update_lcd(temp, humi, ldr, system_state):
    """Update LCD Display"""
    LCD.lcd_clear()
    
    if not system_state["system_enabled"]:
        LCD.lcd_display_string("System DISABLED", 1)
        LCD.lcd_display_string("Press 't' to enable", 2)
    else:
        LCD.lcd_display_string(f"T:{temp:.1f}C H:{humi:.1f}%", 1)
        LCD.lcd_display_string(f"LDR:{ldr}" if system_state["ldr_enabled"] else "LDR:OFF", 2)

try:
    while True:
        # Load updated system state from JSON
        system_state = load_system_state()

        # Skip if system is disabled
        if not system_state["system_enabled"]:
            update_lcd(0, 0, 0, system_state)
            time.sleep(2)
            continue

        temp, humi = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
        ldr_value = readadc(0) if system_state["ldr_enabled"] else 0

        if system_state["temp_humi_enabled"] and temp is not None and humi is not None:
            print(f"Temp: {temp}°C, Humi: {humi}%, LDR: {ldr_value}")

        update_lcd(temp, humi, ldr_value, system_state)
        time.sleep(2)

except KeyboardInterrupt:
    print("\n[INFO] Program stopped by user.")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    print("\n[INFO] Cleaning up resources before exit...")
    GPIO.output(24, 0)  # Turn off LED
    GPIO.cleanup()
    spi.close()  # Close SPI safely
    LCD.lcd_clear()
    print("[INFO] System has safely shut down.")