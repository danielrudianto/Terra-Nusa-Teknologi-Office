from dotenv import load_dotenv
from utils.logger_utils import setup_logger

# Load environment variables from .env file
load_dotenv(dotenv_path=".env")
setup_logger()

