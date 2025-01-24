import Adafruit_DHT
import telegram
import spidev
import I2C_LCD_driver
import RPi.GPIO as GPIO
from time import sleep

# Sensor type: DHT11 or DHT22
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 21  # GPIO pin where the sensor is connected

# Telegram Bot
bot = telegram.Bot(token="7094057858:AAGU0CMWAcTnuMBJoUmBlg8HxUc8c1Mx3jw")
chat_id = "6925171641"

# SPI and GPIO setup
spi = spidev.SpiDev()
spi.open(0, 0)  # Open SPI port 0, device 0
spi.max_speed_hz = 1350000

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(24, GPIO.OUT)

# LCD Initialization
LCD = I2C_LCD_driver.lcd()


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
            if temperature < 18 or temperature > 28:
                message = f"Alert! The current temperature is {temperature}°C, outside of set threshold!"
                bot.send_message(chat_id=chat_id, text=message)

            # Humidity alert
            if humidity > 80:
                message = f"Alert! The current humidity is {humidity}%, too high for optimal plant growth!"
                bot.send_message(chat_id=chat_id, text=message)

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
