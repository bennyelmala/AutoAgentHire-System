"""
Logger utility using Loguru.
Configures structured logging for the application.
"""
import sys
from pathlib import Path
from loguru import logger
from backend.config import settings


def setup_logger(name: str = "autoagenthire"):
    """
    Setup and configure the logger.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    # Remove default handler
    logger.remove()
    
    # Console handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True,
    )
    
    # File handler
    log_path = Path(settings.LOG_FILE_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        settings.LOG_FILE_PATH,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        level=settings.LOG_LEVEL,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        serialize=False,  # Set to True for JSON logging
    )
    
    # Add error-specific log file
    logger.add(
        log_path.parent / "errors.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        level="ERROR",
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
    )
    
    return logger


# Initialize logger
app_logger = setup_logger()
