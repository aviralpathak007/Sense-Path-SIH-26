#!/bin/bash
echo "Setting up SensePath Edge Engine..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "Starting Edge Server..."
python3 server.py
