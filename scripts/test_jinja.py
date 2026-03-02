import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from shared_bot_utils import get_birthday_settings, get_db_url
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader(os.path.join(PROJECT_ROOT, 'web_dashboard', 'app', 'templates')))
try:
    template = env.get_template('birthday.html')
    print("Template parsed successfully!")
except Exception as e:
    print(f"Jinja Error: {e}")
