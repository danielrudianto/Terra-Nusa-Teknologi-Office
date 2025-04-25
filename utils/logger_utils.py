import logging

logger = logging.getLogger(__name__)

class CustomFormatter(logging.Formatter):
    # Define ANSI escape codes for colors
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    WHITE = "\033[97m"
    RESET = "\033[0m"

    def format(self, record):
        # Apply green color to the log level
        if record.levelname == "INFO":
            record.levelname = f"{self.GREEN}{record.levelname}{self.RESET}"
        # Apply yellow to warning level
        elif record.levelname == "WARNING":
            record.levelname = f"{self.YELLOW}{record.levelname}{self.RESET}"
        # Apply red to error level
        elif record.levelname == "ERROR":
            record.levelname = f"{self.RED}{record.levelname}{self.RESET}"
        # Apply white to debug level
        elif record.levelname == "DEBUG":
            record.levelname = f"{self.WHITE}{record.levelname}{self.RESET}"
        return super().format(record)

def setup_logger():
    """
    Set up the logger configuration.
    """
    # Create a custom formatter
    formatter = CustomFormatter("%(levelname)s:     %(message)s")

    # Create a console handler and set the formatter
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    # Configure the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    
def log_request(request):
    """
    Log the incoming request details.
    """
    logger.info(f"Request: {request.method} {request.url}")
    logger.info(f"Headers: {request.headers}")
    logger.info(f"Body: {request.body()}")
    
def log_response(response):
    """
    Log the outgoing response details.
    """
    logger.info(f"Response: {response.status_code}")
    logger.info(f"Headers: {response.headers}")
    logger.info(f"Body: {response.body()}")
    
def log_error(error):
    """
    Log the error details.
    """
    logger.error(f"Error: {error}")
    logger.error(f"Traceback: {error.__traceback__}")
    
def log_info(message):
    """
    Log informational messages.
    """
    logger.info(f"{message}")