# -*- coding: utf-8 -*-
"""
logger_util.py - Centralized logger factory for all modules

This module provides a simple way for any module to get a logger that
automatically connects to the log_handler ring buffer system.

USAGE in any module:
    from logger_util import get_logger
    logger = get_logger(__name__)
    
    logger.info("Something happened")
    logger.error("An error occurred: %s", error_msg)
    logger.debug("Debug info: %s", data)
    logger.warning("This is deprecated")
"""

import logging
import sys

# Map module names to their short identifiers (used by log_handler.py)
MODULE_MAP = {
    'pipeline': 'pipeline',
    'database': 'database',
    'general': 'general',
    'auth': 'auth',
    'device_management': 'device_management',
    'tag_mapping': 'tag_mapping',
    'mqtt_cloud': 'mqtt_cloud',
    'rules': 'rules',
    'main': 'main',
}

def get_logger(name):
    """
    Get a logger for the given module name.
    
    Args:
        name: Module name, typically __name__
        
    Returns:
        A logging.Logger instance configured for this module
        
    Example:
        logger = get_logger(__name__)  # or get_logger('pipeline')
        logger.info("Pipeline started")
    """
    # Extract clean module name (e.g., 'flask.pipeline' -> 'pipeline')
    if '.' in name:
        module_short = name.rsplit('.', 1)[-1]
    else:
        module_short = name
    
    # Get or create logger
    logger = logging.getLogger(name)
    
    # Ensure logger is configured at DEBUG level
    # (log_handler.py will filter based on module settings)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
    
    return logger
