#!/bin/sh
source .venv/bin/activate
export FLASK_APP=main
export FLASK_DEBUG=1
python -m flask run --port $PORT
