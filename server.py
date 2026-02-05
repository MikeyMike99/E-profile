import socketio
import os
from gevent.pywsgi import WSGIServer  
from logger import LOGG

# Create a Socket.IO server with low-latency configuration
sio = socketio.Server(
    async_mode="gevent",
    ping_interval=0.5,  # Send pings every 0.5 seconds to check connectivity
    ping_timeout=2,     # Disconnect clients if no response within 2 seconds
    cors_allowed_origins="*",  # Allow all origins to reduce connection restrictions
    logger=False,  # Disable built-in logging
    engineio_logger=False  # Disable engine.io logging
)

# Create a WSGI application
app = socketio.WSGIApp(sio)

# Dictionary to map commands to their respective functions
command_handlers = {}

# Decorator to register command handlers
def register_command(command_name):
    def decorator(func):
        command_handlers[command_name] = func
        return func
    return decorator

# Example command: Move forward
@register_command("forward")
def move_forward(sid, data):
    LOGG(f"Executing 'forward' for client {sid}")
    sio.emit("response", {"message": "You have moved forward."}, to=sid)

# Example command: Move backward
@register_command("backward")
def move_backward(sid, data):
    LOGG(f"Executing 'backward' for client {sid}")
    sio.emit("response", {"message": "You have moved backward."}, to=sid)

# Event when a client connects
@sio.event
def connect(sid, environ):
    LOGG(f"Client connected: {sid}")

# Event when a client sends a command
@sio.event
def message(sid, data):
    LOGG(f"Message from {sid}: {data}")

    # Ensure the data has the required structure
    if isinstance(data, dict) and "action" in data:
        action = data["action"]
        params = data.get("params", {})  # Optional parameters

        # Dynamically dispatch the command
        if action in command_handlers:
            command_handlers[action](sid, params)  # Call the registered handler
        else:
            LOGG(f"Unknown action: {action}")
            sio.emit("response", {"error": f"Unknown action: {action}"}, to=sid)
    else:
        LOGG(f"Invalid message format from {sid}")
        sio.emit("response", {"error": "Invalid message format"}, to=sid)

# Event when a client disconnects
@sio.event
def disconnect(sid):
    LOGG(f"Client disconnected: {sid}")


if __name__ == "__main__":
    # Use Gevent WSGI server to serve the app
    server = WSGIServer(("0.0.0.0", 12345), app)  # Run the server on all interfaces, port 12345
    LOGG("Starting server on ws://localhost:12345...")
    server.serve_forever()  # Start the server and listen indefinitely
