"""Logging configuration module for the voice assistant.

This module provides a configured logger instance with console output,
formatted timestamps and proper log levels for the voice assistant application.

Attributes:
    logger (logging.Logger): Configured logger instance for the application
"""

import logging
from logging import Logger


def configure_logger() -> Logger:
    """Creates and configures a logger with console output.

    Configures a logger with:
    - INFO log level
    - Console output handler
    - Timestamp formatting
    - No propagation to parent loggers

    Returns:
        Logger: Configured logger instance
    """
    logger = logging.getLogger("my_logger")
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger


logger = configure_logger()
