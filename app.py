from flask import Flask, render_template, request, redirect, jsonify
import json
import os

app = Flask(__name__)

def load_system_state():
    """Loads the system state from JSON file."""
    default_state = {"system": True, "temp_humi": True, "ldr": True}

    if not os.path.exists("system_state.json"):
        save_system_state(default_state)
        return default_state

    try:
        with open("system_state.json", "r") as file:
            return json.load(file)
    except (json.JSONDecodeError, ValueError):
        print("[ERROR] Corrupted system_state.json. Resetting...")
        save_system_state(default_state)
        return default_state


def save_system_state(state):
    """Writes system state to JSON file."""
    with open("system_state.json", "w") as file:
        json.dump(state, file)


@app.route("/")
def home():
    state = load_system_state()
    return render_template("index.html", state=state)


@app.route("/toggle", methods=["POST"])
def toggle():
    """Handles toggling of system settings."""
    state = load_system_state()

    toggle_type = request.form.get("toggle")

    if toggle_type in state:
        state[toggle_type] = not state[toggle_type]
        save_system_state(state)
        return redirect("/")
    
    return "Invalid toggle request", 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
