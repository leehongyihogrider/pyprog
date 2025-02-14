from flask import Flask, render_template, jsonify, request
import json
import os

app = Flask(__name__)

# Path to the system state JSON file
STATE_FILE = "system_state.json"

# Function to load system state
def load_system_state():
    if not os.path.exists(STATE_FILE):
        return {"system_enabled": True, "temp_humi_enabled": True, "ldr_enabled": True}
    
    with open(STATE_FILE, "r") as f:
        return json.load(f)

# Function to save system state
def save_system_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

@app.route("/")
def home():
    system_state = load_system_state()
    return render_template("index.html", **system_state)

@app.route("/toggle", methods=["POST"])
def toggle():
    system_state = load_system_state()
    toggle_type = request.form["toggle"]

    if toggle_type == "system":
        system_state["system_enabled"] = not system_state["system_enabled"]
    elif toggle_type == "temp_humi":
        system_state["temp_humi_enabled"] = not system_state["temp_humi_enabled"]
    elif toggle_type == "ldr":
        system_state["ldr_enabled"] = not system_state["ldr_enabled"]

    save_system_state(system_state)
    return jsonify(system_state)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
