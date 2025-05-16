import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Base directory of the application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Ensure instance directory exists
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)
logger.debug(f"Instance directory: {INSTANCE_DIR}")

# Database path
DB_PATH = os.path.join(INSTANCE_DIR, 'cloner.db').replace('\\', '/')
logger.debug(f"Database path: {DB_PATH}")

# Flask configuration class
class Config:
    SECRET_KEY = os.urandom(24).hex()
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    UPLOAD_FOLDER = 'user_uploads'
    SQLALCHEMY_TRACK_MODIFICATIONS = False