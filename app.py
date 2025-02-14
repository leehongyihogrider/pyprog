from flask import Flask, render_template, request, redirect
import json
import os

app = Flask(__name__)

# Ensure system_state.json exists with default values
SYSTEM_STATE_FILE = "system_state.json"
DEFAULT_STATE = {
    "system": True,
    "temperature_humidity": True,
    "ldr": True
}

# Function to read system state
def read_system_state():
    if not os.path.exists(SYSTEM_STATE_FILE):
        with open(SYSTEM_STATE_FILE, "w") as f:
            json.dump(DEFAULT_STATE, f)
    with open(SYSTEM_STATE_FILE, "r") as f:
        return json.load(f)

# Function to update system state
def write_system_state(state):
    with open(SYSTEM_STATE_FILE, "w") as f:
        json.dump(state, f)

@app.route("/")
def home():
    system_state = read_system_state()
    return render_template("index.html", state=system_state)

@app.route("/toggle", methods=["POST"])
def toggle():
    toggle_type = request.form.get("toggle")
    system_state = read_system_state()
    
    if toggle_type in system_state:
        system_state[toggle_type] = not system_state[toggle_type]  # Toggle on/off
        write_system_state(system_state)
        print(f"[INFO] {toggle_type} set to {system_state[toggle_type]}")
    
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
