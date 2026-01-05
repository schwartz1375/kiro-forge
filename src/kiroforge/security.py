"""Security utilities for KiroForge."""

from __future__ import annotations

import re
from pathlib import Path


def validate_file_path(base_dir: Path, file_path: Path | str) -> bool:
    """
    Validate that a file path is safe and within the base directory.
    
    Args:
        base_dir: The base directory that should contain the file
        file_path: The file path to validate
        
    Returns:
        True if the path is safe, False otherwise
    """
    try:
        if isinstance(file_path, str):
            file_path = Path(file_path)
        
        # Resolve both paths to handle .. and . components
        base_resolved = base_dir.resolve()
        target_resolved = (base_dir / file_path).resolve()
        
        # Check if target is within base directory
        return target_resolved.is_relative_to(base_resolved)
    except (OSError, ValueError):
        return False


def validate_command_input(input_text: str, max_length: int = 50000) -> None:
    """
    Validate command input for security issues.
    
    Args:
        input_text: The input text to validate
        max_length: Maximum allowed length
        
    Raises:
        ValueError: If input is invalid or potentially dangerous
    """
    if not input_text or not input_text.strip():
        raise ValueError("Input cannot be empty")
    
    if len(input_text) > max_length:
        raise ValueError(f"Input too long (max {max_length} characters)")
    
    # Check for suspicious patterns that could indicate injection attempts
    suspicious_patterns = [
        r'[;&|`$()]',  # Shell metacharacters
        r'\\x[0-9a-fA-F]{2}',  # Hex escape sequences
        r'[\x00-\x1f\x7f-\x9f]',  # Control characters
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, input_text):
            raise ValueError(f"Input contains suspicious characters: {pattern}")


def validate_identifier(identifier: str, pattern: str = r'^[a-zA-Z0-9_-]+$') -> bool:
    """
    Validate that an identifier matches a safe pattern.
    
    Args:
        identifier: The identifier to validate
        pattern: The regex pattern to match against
        
    Returns:
        True if valid, False otherwise
    """
    return bool(re.match(pattern, identifier))


def redact_secrets(text: str) -> str:
    """
    Redact sensitive information from text.
    
    Args:
        text: The text to redact
        
    Returns:
        Text with sensitive information redacted
    """
    patterns = {
        # Stripe keys
        r"sk_live_[A-Za-z0-9]+": "sk_live_REDACTED",
        r"sk_test_[A-Za-z0-9]+": "sk_test_REDACTED",
        r"pk_live_[A-Za-z0-9]+": "pk_live_REDACTED",
        r"pk_test_[A-Za-z0-9]+": "pk_test_REDACTED",
        r"rk_live_[A-Za-z0-9]+": "rk_live_REDACTED",
        r"rk_test_[A-Za-z0-9]+": "rk_test_REDACTED",
        
        # JWT tokens
        r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+": "jwt_REDACTED",
        
        # AWS keys
        r"AKIA[0-9A-Z]{16}": "AKIA_REDACTED",
        r"ASIA[0-9A-Z]{16}": "ASIA_REDACTED",
        r"[A-Za-z0-9/+=]{40}": "aws_secret_REDACTED",
        
        # GitHub tokens
        r"ghp_[A-Za-z0-9]{36}": "ghp_REDACTED",
        r"gho_[A-Za-z0-9]{36}": "gho_REDACTED",
        r"ghu_[A-Za-z0-9]{36}": "ghu_REDACTED",
        r"ghs_[A-Za-z0-9]{36}": "ghs_REDACTED",
        r"ghr_[A-Za-z0-9]{36}": "ghr_REDACTED",
        
        # Generic API keys and tokens
        r"[Aa][Pp][Ii]_?[Kk][Ee][Yy]\s*[:=]\s*['\"]?([A-Za-z0-9_-]{20,})['\"]?": "API_KEY=REDACTED",
        r"[Aa][Cc][Cc][Ee][Ss][Ss]_?[Tt][Oo][Kk][Ee][Nn]\s*[:=]\s*['\"]?([A-Za-z0-9_-]{20,})['\"]?": "ACCESS_TOKEN=REDACTED",
        r"[Bb][Ee][Aa][Rr][Ee][Rr]\s+([A-Za-z0-9_-]{20,})": "Bearer REDACTED",
        
        # Database URLs
        r"(postgres|mysql|mongodb)://[^:]+:[^@]+@[^/]+/[^\s]+": "DATABASE_URL_REDACTED",
        
        # Private keys
        r"-----BEGIN [A-Z ]+PRIVATE KEY-----[^-]+-----END [A-Z ]+PRIVATE KEY-----": "PRIVATE_KEY_REDACTED",
        
        # SSH keys
        r"ssh-rsa [A-Za-z0-9+/=]+": "SSH_KEY_REDACTED",
        r"ssh-ed25519 [A-Za-z0-9+/=]+": "SSH_KEY_REDACTED",
        
        # Environment variables with secrets
        r"[A-Z_]+_SECRET\s*[:=]\s*['\"]?([A-Za-z0-9_-]{8,})['\"]?": "SECRET_REDACTED",
        r"[A-Z_]+_PASSWORD\s*[:=]\s*['\"]?([A-Za-z0-9_-]{8,})['\"]?": "PASSWORD_REDACTED",
        
        # Credit card numbers
        r"\b(?:\d{4}[-\s]?){3}\d{4}\b": "CREDIT_CARD_REDACTED",
        
        # Email addresses
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b": "EMAIL_REDACTED",
        
        # Phone numbers
        r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b": "PHONE_REDACTED",
        
        # IP addresses
        r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b": "IP_REDACTED",
        
        # UUIDs
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b": "UUID_REDACTED",
        
        # Platform-specific tokens
        r"xox[baprs]-[0-9a-zA-Z-]+": "SLACK_TOKEN_REDACTED",
        r"[MN][A-Za-z0-9]{23}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27}": "DISCORD_TOKEN_REDACTED",
        r"AIza[0-9A-Za-z-_]{35}": "GOOGLE_API_KEY_REDACTED",
        r"EAA[0-9A-Za-z]+": "FACEBOOK_TOKEN_REDACTED",
        r"[1-9][0-9]+-[0-9a-zA-Z]{40}": "TWITTER_TOKEN_REDACTED",
    }
    
    for pattern, replacement in patterns.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text


def validate_tool_pattern(pattern: str) -> tuple[bool, str]:
    """
    Validate a tool pattern for security issues.
    
    Args:
        pattern: The tool pattern to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not pattern:
        return False, "Tool pattern cannot be empty"
    
    # Check for overly broad patterns
    if pattern in {"*", "**", ".*"}:
        return False, f"Overly broad tool pattern: {pattern}"
    
    # Check for suspicious patterns
    if ".." in pattern or pattern.startswith("/"):
        return False, f"Suspicious tool pattern: {pattern}"
    
    # Validate pattern format
    if not re.match(r'^[a-zA-Z0-9_.*-]+$', pattern):
        return False, f"Tool pattern contains invalid characters: {pattern}"
    
    return True, ""