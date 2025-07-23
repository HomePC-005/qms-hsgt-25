import os
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

# --- Application Setup ---
app = Flask(__name__, static_url_path='/static')
# It's better to load secrets from environment variables
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_secret_key')
socketio = SocketIO(app, cors_allowed_origins="*")

# --- State Management ---
# Use a single list to store the call history.
# The most recent call is always at index 0.
# Let's store one current call + three history calls.
MAX_CALLS = 4
call_history = []

# --- Helper Function for Centralized Logic ---
def update_and_broadcast_call(number, counter):
    """
    Central function to handle a new call.
    It updates the history and emits events to all clients.
    """
    global call_history

    # Create the new call object
    new_call = {"number": number, "counter": counter}

    # Add the new call to the front of the list
    call_history.insert(0, new_call)

    # Trim the list to keep only the last 4 calls
    call_history = call_history[:MAX_CALLS]

    # Prepare data for clients
    current_state = {
        "current": call_history[0] if call_history else {},
        "history": call_history[1:] # The rest of the list is history
    }

    # Emit the updated state to all connected display clients
    socketio.emit("current_state", current_state)


# --- SocketIO Event Handlers ---
@socketio.on("connect")
def handle_connect():
    """
    Sends the current state to a client when they first connect.
    This ensures new displays get the current numbers immediately.
    """
    current_state = {
        "current": call_history[0] if call_history else {},
        "history": call_history[1:]
    }
    emit("current_state", current_state)


@socketio.on("call_number")
def handle_call_event(data):
    """Handles a new call coming from a SocketIO client."""
    number = data.get("number")
    counter = data.get("counter")
    if number and counter:
        update_and_broadcast_call(number, counter)


# --- HTTP Route Handlers ---
@app.route("/")
def index():
    """Serves the staff page."""
    return render_template("staff.html")


@app.route("/display")
def display():
    """Serves the display page."""
    return render_template("display.html")


@app.route("/api/call_number", methods=["POST"])
def call_number_api():
    """Handles a new call coming from an HTTP POST request."""
    data = request.get_json()
    number = data.get("number")
    counter = data.get("counter")
    if number and counter:
        update_and_broadcast_call(number, counter)
        return jsonify({"status": "ok", "message": "Call processed."})
    return jsonify({"status": "error", "message": "Missing number or counter"}), 400


# The /api/current endpoint is no longer needed because the 'connect'
# event handler now provides the same functionality more efficiently.


# Generate the media list once at startup for better performance
MEDIA_FOLDER = 'static/media'
MEDIA_FILES = [f'/static/media/{f}' for f in os.listdir(MEDIA_FOLDER) if f.endswith('.mp4')]

@app.route('/media-list')
def media_list():
    """Returns the cached list of media files."""
    return jsonify(MEDIA_FILES)


# --- Main Execution ---
if __name__ == "__main__":
    # For production, you should turn debug mode off.
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)