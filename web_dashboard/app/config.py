import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-me'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Bot Settings
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    
    # Dashboard Settings
    TITLE = "Bot Dashboard"
