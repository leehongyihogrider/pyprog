from flask import Flask, render_template, request, redirect, jsonify
import json

app = Flask(__name__)

# Load System State
def load_system_state():
    try:
        with open("system_state.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"system": True, "temp_humi": True, "ldr": True}

def save_system_state(state):
    with open("system_state.json", "w") as file:
        json.dump(state, file)

@app.route("/")
def home():
    system_state = load_system_state()
    return render_template("index.html", system=system_state)

@app.route("/toggle", methods=["POST"])
def toggle():
    system_state = load_system_state()
    toggle_type = request.form["toggle"]

    if toggle_type == "system":
        system_state["system"] = not system_state["system"]
    elif toggle_type == "temp_humi":
        system_state["temp_humi"] = not system_state["temp_humi"]
    elif toggle_type == "ldr":
        system_state["ldr"] = not system_state["ldr"]

    save_system_state(system_state)
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
