#!/bin/bash
# Start script pointing to the correct app.py location
# We use the absolute path to python in the venv to ensure modules are found
$(pwd)/.venv/bin/python web_dashboard/app.py