import logging
import os
from datetime import datetime
from app.config import settings

# Ensure log directory exists
os.makedirs(settings.LOG_DIR, exist_ok=True)

def setup_logger(name: str, log_file: str, level=logging.INFO):
    """Function setup as many loggers as you want"""
    formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')
    
    handler = logging.FileHandler(os.path.join(settings.LOG_DIR, log_file))        
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        logger.addHandler(handler)
        
        # Also add stream handler for console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

# Create specific loggers
execution_logger = setup_logger('execution', 'execution.log', level=settings.LOG_LEVEL)
audit_logger = setup_logger('audit', 'audit.log', level=settings.LOG_LEVEL)
error_logger = setup_logger('error', 'error.log', level=logging.ERROR)

def log_audit(session_id: str, action: str, details: dict):
    """Standardized format for audit logging"""
    audit_logger.info(f"Session: {session_id} | Action: {action} | Details: {details}")

def log_execution(session_id: str, tool: str, status: str, result: str):
    """Standardized format for execution logging"""
    execution_logger.info(f"Session: {session_id} | Tool: {tool} | Status: {status} | Result: {result}")
