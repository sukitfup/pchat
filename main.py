import asyncio
import tkinter as tk
import threading
import time
import json
from client import AsyncClient
from ui import BotUI

# Global variable to hold the asyncio loop
async_loop = None

def start_asyncio_loop():
    global async_loop
    async_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(async_loop)
    print("Async loop started")
    async_loop.run_forever()
    print("Async loop stopped")

# Load settings from config.json
try:
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    HOST = config['host']
    PORT = config['port']
    USERNAME = config['username']
    PASSWORD = config['password']
    HOME_CHANNEL = config['home_channel']
except FileNotFoundError:
    print("Error: config.json not found")
    exit(1)
except KeyError as e:
    print(f"Error: Missing key {e} in config.json")
    exit(1)

# Start the asyncio thread
loop_thread = threading.Thread(target=start_asyncio_loop, daemon=True)
loop_thread.start()

# Wait until the loop is initialized
while async_loop is None:
    time.sleep(0.1)

# Create the client and UI
root = tk.Tk()
root.title("pchat")
client = AsyncClient(HOST, PORT, USERNAME, PASSWORD, HOME_CHANNEL, None, async_loop)
app = BotUI(root, client) # Create client
client.log_callback = app.log  # Set the log callback
client.set_ui_callback(app.update_user_list)  # Set ui_callback
client.start()  # Start the client
root.mainloop()