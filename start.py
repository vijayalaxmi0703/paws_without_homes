"""Quick launcher for the Flask version of Paws Without Homes."""

import os
import subprocess
import sys
import time
import webbrowser


os.chdir(os.path.dirname(os.path.abspath(__file__)))
print("Starting Paws Without Homes Flask app...")
proc = subprocess.Popen([sys.executable, "server1.py"])
time.sleep(2)
webbrowser.open("http://127.0.0.1:5000")
print("Opened http://127.0.0.1:5000 in your browser.")
print("Press Ctrl+C to stop.\n")

try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
    print("\nServer stopped.")
