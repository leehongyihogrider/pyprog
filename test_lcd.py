import I2C_LCD_driver
from time import sleep

lcd = I2C_LCD_driver.lcd()

try:
    lcd.lcd_display_string("Hello, World!", 1)
    lcd.lcd_display_string("I2C Address: 0x3f", 2)
    sleep(5)
    lcd.lcd_clear()
except Exception as e:
    print(f"Error: {e}")
