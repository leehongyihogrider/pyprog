import I2C_LCD_driver
from time import sleep
import telegram

bot = telegram.Bot(token="7094057858:AAGU0CMWAcTnuMBJoUmBlg8HxUc8c1Mx3jw")
chat_id = "6925171641"
lcd = I2C_LCD_driver.lcd()

try:
    lcd.lcd_display_string("Hello, World!", 1)
    lcd.lcd_display_string("I2C Address: 0x3f", 2)
    message = f"hello prok!"
    bot.send_message(chat_id=chat_id, text=message)
    sleep(5)
    lcd.lcd_clear()
except Exception as e:
    print(f"Error: {e}")
