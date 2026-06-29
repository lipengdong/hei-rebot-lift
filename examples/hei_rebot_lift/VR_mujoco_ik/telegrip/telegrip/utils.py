"""
Utility functions for the teleoperation system.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

def get_package_dir() -> Path:
    """
    Get the directory where the telegrip package is installed.
    This allows us to find package files regardless of current working directory.
    """
    # Get the directory containing this utils.py file
    # which is the telegrip package directory
    return Path(__file__).parent

def get_project_root() -> Path:
    """
    Get the project root directory (parent of the telegrip package).
    This is where config files, SSL certificates, and the web UI are located.
    """
    return get_package_dir().parent

def get_absolute_path(relative_path: str) -> Path:
    """
    Convert a relative path to an absolute path relative to the project root.
    
    Args:
        relative_path: Path relative to project root
        
    Returns:
        Absolute Path object
    """
    return get_project_root() / relative_path

def generate_ssl_certificates(cert_path: str = "cert.pem", key_path: str = "key.pem") -> bool:
    """
    Automatically generate self-signed SSL certificates if they don't exist.
    
    Args:
        cert_path: Path where to save the certificate file (relative to project root)
        key_path: Path where to save the private key file (relative to project root)
        
    Returns:
        True if certificates exist or were generated successfully, False otherwise
    """
    # Convert to absolute paths
    cert_abs_path = get_absolute_path(cert_path)
    key_abs_path = get_absolute_path(key_path)
    
    # Check if certificates already exist
    if cert_abs_path.exists() and key_abs_path.exists():
        logger.info(f"SSL certificates already exist: {cert_abs_path}, {key_abs_path}")
        return True
    
    logger.info("SSL certificates not found, generating self-signed certificates...")
    
    try:
        # Generate self-signed certificate using openssl
        cmd = [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key_abs_path),
            "-out", str(cert_abs_path),
            "-sha256", "-days", "365", "-nodes",
            "-subj", "/C=US/ST=Test/L=Test/O=Test/OU=Test/CN=localhost"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Set appropriate permissions (readable by owner only for security)
        os.chmod(key_abs_path, 0o600)
        os.chmod(cert_abs_path, 0o644)
        
        logger.info(f"SSL certificates generated successfully: {cert_abs_path}, {key_abs_path}")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate SSL certificates: {e}")
        logger.error(f"Command output: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.error("OpenSSL not found. Please install OpenSSL to generate certificates.")
        logger.error("On Ubuntu/Debian: sudo apt-get install openssl")
        logger.error("On macOS: brew install openssl")
        return False
    except Exception as e:
        logger.error(f"Unexpected error generating SSL certificates: {e}")
        return False

def ensure_ssl_certificates(cert_path: str = "cert.pem", key_path: str = "key.pem") -> bool:
    """
    Ensure SSL certificates exist, generating them if necessary.
    
    Args:
        cert_path: Path to certificate file (relative to project root)
        key_path: Path to private key file (relative to project root)
        
    Returns:
        True if certificates are available, False if generation failed
    """
    if not generate_ssl_certificates(cert_path, key_path):
        logger.error("Could not ensure SSL certificates are available")
        logger.error("Manual certificate generation may be required:")
        logger.error("openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes -subj \"/C=US/ST=Test/L=Test/O=Test/OU=Test/CN=localhost\"")
        return False
    
    return True 
