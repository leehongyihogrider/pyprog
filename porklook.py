import Adafruit_DHT
import requests
import spidev
import I2C_LCD_driver
import RPi.GPIO as GPIO
from time import sleep, time
from datetime import datetime, timedelta

# Sensor type: DHT11 or DHT22
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21  # GPIO pin where the sensor is connected

# Telegram Bot
TOKEN = "7094057858:AAGU0CMWAcTnuMBJoUmBlg8HxUc8c1Mx3jw"
chat_id = "-1002405515611"

# SPI and GPIO setup
spi = spidev.SpiDev()
spi.open(0, 0)  # Open SPI port 0, device 0
spi.max_speed_hz = 1350000

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(24, GPIO.OUT)

# LCD Initialization
LCD = I2C_LCD_driver.lcd()

# Track the last message sent time for temperature and humidity
last_temp_alert_time = None
last_humidity_alert_time = None

# Define a function to check if 24 hours have passed
def can_send_alert(last_alert_time):
    if last_alert_time is None:
        return True
    return datetime.now() - last_alert_time > timedelta(days=1)


def readadc(adcnum):
    # Read SPI data from the MCP3008, 8 channels in total
    if adcnum > 7 or adcnum < 0:
        return -1
    r = spi.xfer2([1, (8 + adcnum) << 4, 0])
    data = ((r[1] & 3) << 8) + r[2]
    return data


try:
    while True:
        # Read humidity and temperature
        humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)

        if humidity is not None and temperature is not None:
            # Temperature alert
            if (temperature < 18 or temperature > 28) and can_send_alert(last_temp_alert_time):
                message = f"Alert! The current temperature is {temperature}°C, outside of set threshold!"
                url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}"
                response = requests.get(url).json()
                print(response)
                last_temp_alert_time = datetime.now()  # Update the last alert time

            # Humidity alert
            if humidity > 80 and can_send_alert(last_humidity_alert_time):
                message = f"Alert! The current humidity is {humidity}%, too high for optimal plant growth!"
                url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}"
                response = requests.get(url).json()
                print(response)
                last_humidity_alert_time = datetime.now()  # Update the last alert time

            # Read LDR value
            LDR_value = readadc(0)  # Read ADC channel 0 (LDR)
            print(f"LDR = {LDR_value}")
            GPIO.output(24, 1 if LDR_value < 500 else 0)

            # Display on LCD
            LCD.lcd_display_string(f"Temp: {temperature:.1f}°C", 1)
            LCD.lcd_display_string(f"Humidity: {humidity:.1f}%", 2)

        else:
            print("Failed to retrieve data from the sensor. Check wiring!")

        sleep(2)  # Add delay for stability

except KeyboardInterrupt:
    print("\nProgram stopped by user.")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    GPIO.output(24, 0)  # Ensure LED is off
    GPIO.cleanup()
    spi.close()
    LCD.lcd_clear()