import logging
import os
import sys
from pathlib import Path

def setup_logger(name: str = "app", log_file: str = "data/app.log", level=logging.INFO) -> logging.Logger:
    """
    Configure and return a logger with console and file handlers.
    
    Args:
        name: The name of the logger (default: "app")
        log_file: Path to the log file (relative to project root if not absolute)
        level: Logging level (default: logging.INFO)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding handlers multiple times if logger is already configured
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    # Ensure log directory exists
    try:
        log_path = Path(log_file)
        if not log_path.is_absolute():
            # Assuming run from project root
            log_path = Path.cwd() / log_file
        
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(str(log_path), encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Failed to setup file logging: {e}")

    return logger

# Default logger instance
logger = setup_logger()
