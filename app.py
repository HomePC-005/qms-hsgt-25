import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from threading import Lock

# --- Configuration ---
@dataclass
class Config:
    SECRET_KEY: str = os.environ.get('SECRET_KEY', 'a_default_secret_key_change_in_production')
    HOST: str = os.environ.get('HOST', '10.77.235.225')
    PORT: int = int(os.environ.get('PORT', '5000'))
    DEBUG: bool = os.environ.get('DEBUG', 'False').lower() == 'true'
    MAX_CALLS: int = int(os.environ.get('MAX_CALLS', '4'))
    MEDIA_FOLDER: str = os.environ.get('MEDIA_FOLDER', 'static/media')
    CORS_ORIGINS: str = os.environ.get('CORS_ORIGINS', '*')

config = Config()

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Data Models ---
@dataclass
class Call:
    number: str
    counter: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'number': self.number,
            'counter': self.counter,
            'timestamp': self.timestamp.isoformat()
        }

# --- Application Setup ---
app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins=config.CORS_ORIGINS)

# --- Thread-Safe State Management ---
class CallManager:
    def __init__(self, max_calls: int = 4):
        self.max_calls = max_calls
        self.call_history: List[Call] = []
        self._lock = Lock()
    
    def add_call(self, number: str, counter: str) -> Call:
        """Thread-safe method to add a new call."""
        new_call = Call(number=number, counter=counter, timestamp=datetime.now())
        
        with self._lock:
            self.call_history.insert(0, new_call)
            self.call_history = self.call_history[:self.max_calls]
            logger.info(f"New call added: {number} at {counter}")
        
        return new_call
    
    def get_current_state(self) -> Dict[str, Any]:
        """Thread-safe method to get current state."""
        with self._lock:
            return {
                "current": self.call_history[0].to_dict() if self.call_history else {},
                "history": [call.to_dict() for call in self.call_history[1:]]
            }

call_manager = CallManager(config.MAX_CALLS)

# --- Media Management ---
class MediaManager:
    def __init__(self, media_folder: str):
        self.media_folder = media_folder
        self._media_files: List[str] = []
        self._last_scan = None
        self.refresh_media_files()
    
    def refresh_media_files(self) -> None:
        """Refresh the media files list."""
        try:
            if not os.path.exists(self.media_folder):
                logger.warning(f"Media folder {self.media_folder} does not exist")
                self._media_files = []
                return
                
            files = os.listdir(self.media_folder)
            self._media_files = [
                f'/static/media/{f}' for f in files 
                if f.lower().endswith(('.mp4', '.webm', '.ogg'))
            ]
            self._last_scan = datetime.now()
            logger.info(f"Found {len(self._media_files)} media files")
        except OSError as e:
            logger.error(f"Error scanning media folder: {e}")
            self._media_files = []
    
    def get_media_files(self) -> List[str]:
        """Get list of media files, refresh if needed."""
        # Refresh every 5 minutes in production
        if (self._last_scan is None or 
            (datetime.now() - self._last_scan).seconds > 300):
            self.refresh_media_files()
        return self._media_files

media_manager = MediaManager(config.MEDIA_FOLDER)

# --- Helper Functions ---
def validate_call_data(data: Dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Validate and extract call data."""
    if not data:
        return None, None, "No data provided"
    
    number = data.get("number", "").strip()
    counter = data.get("counter", "").strip()
    
    if not number:
        return None, None, "Number is required"
    if not counter:
        return None, None, "Counter is required"
    
    # Additional validation
    if len(number) > 50:
        return None, None, "Number too long"
    if len(counter) > 50:
        return None, None, "Counter name too long"
    
    return number, counter, None

def update_and_broadcast_call(number: str, counter: str) -> None:
    """
    Central function to handle a new call.
    Updates history and emits events to all clients.
    """
    try:
        call_manager.add_call(number, counter)
        current_state = call_manager.get_current_state()
        socketio.emit("current_state", current_state)
        logger.info(f"Broadcasted call update: {number} at {counter}")
    except Exception as e:
        logger.error(f"Error updating and broadcasting call: {e}")
        raise

# --- SocketIO Event Handlers ---
@socketio.on("connect")
def handle_connect():
    """Send current state to newly connected clients."""
    try:
        current_state = call_manager.get_current_state()
        emit("current_state", current_state)
        logger.info("Client connected and received current state")
    except Exception as e:
        logger.error(f"Error handling client connection: {e}")

@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected")

@socketio.on("call_number")
def handle_call_event(data):
    """Handle new call from SocketIO client."""
    try:
        number, counter, error = validate_call_data(data)
        if error:
            emit("error", {"message": error})
            return
        
        update_and_broadcast_call(number, counter)
    except Exception as e:
        logger.error(f"Error handling call event: {e}")
        emit("error", {"message": "Internal server error"})

# --- HTTP Route Handlers ---
@app.route("/")
def index():
    """Serve the staff page."""
    return render_template("staff.html")

@app.route("/display")
def display():
    """Serve the display page."""
    return render_template("display.html")

@app.route("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "calls_in_history": len(call_manager.call_history)
    })

@app.route("/api/call_number", methods=["POST"])
def call_number_api():
    """Handle new call from HTTP POST request."""
    try:
        data = request.get_json()
        number, counter, error = validate_call_data(data)
        
        if error:
            return jsonify({
                "status": "error", 
                "message": error
            }), 400
        
        update_and_broadcast_call(number, counter)
        return jsonify({
            "status": "success", 
            "message": "Call processed successfully",
            "data": {"number": number, "counter": counter}
        })
        
    except Exception as e:
        logger.error(f"Error in call_number_api: {e}")
        return jsonify({
            "status": "error", 
            "message": "Internal server error"
        }), 500

@app.route('/api/media-list')
def media_list():
    """Return list of available media files."""
    try:
        files = media_manager.get_media_files()
        return jsonify({
            "status": "success",
            "media_files": files,
            "count": len(files)
        })
    except Exception as e:
        logger.error(f"Error getting media list: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to retrieve media files"
        }), 500

@app.route('/api/current_state')
def current_state_api():
    """Get current state via HTTP (useful for debugging/monitoring)."""
    try:
        current_state = call_manager.get_current_state()
        return jsonify({
            "status": "success",
            "data": current_state
        })
    except Exception as e:
        logger.error(f"Error getting current state: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to retrieve current state"
        }), 500

# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": "error", "message": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"status": "error", "message": "Internal server error"}), 500

# --- Main Execution ---
if __name__ == "__main__":
    logger.info(f"Starting application on {config.HOST}:{config.PORT}")
    logger.info(f"Debug mode: {config.DEBUG}")
    socketio.run(
        app, 
        host=config.HOST, 
        port=config.PORT, 
        debug=config.DEBUG
    )
