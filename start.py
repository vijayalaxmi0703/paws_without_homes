#!/usr/bin/env python3
"""
Quick launcher for Paws Without Homes
"""
import subprocess, sys, os, webbrowser, time

os.chdir(os.path.dirname(os.path.abspath(__file__)))
print("🐾 Starting Paws Without Homes...")
proc = subprocess.Popen([sys.executable, "server.py"])
time.sleep(1)
webbrowser.open("http://localhost:8080")
print("   Opened http://localhost:8080 in your browser.")
print("   Press Ctrl+C to stop.\n")
try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
    print("\n✅ Server stopped.")
