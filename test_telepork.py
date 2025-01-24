from time import sleep
import telegram
import requests

TOKEN="7094057858:AAGU0CMWAcTnuMBJoUmBlg8HxUc8c1Mx3jw"
chat_id = "-1002405515611"


try:


    message = f"hello prok!"
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}"
    print(requests.get(url).json())
    
    sleep(5)

except Exception as e:
    print(f"Error: {e}")