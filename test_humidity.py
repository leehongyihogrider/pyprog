import requests

THINGSPEAK_UPDATE_URL = "https://api.thingspeak.com/update"

test_humidity = 60  # Set any value to test

payload = {
    "api_key": "ATNCBN0ZUFSYGREX",
    "field2": test_humidity
}

response = requests.get(THINGSPEAK_UPDATE_URL, params=payload)
print(f"Test Humidity Upload Response: {response.status_code}")
