"""Tests for security module."""

from pathlib import Path
import pytest

from kiroforge.security import (
    validate_file_path,
    validate_command_input,
    validate_identifier,
    validate_tool_pattern,
    redact_secrets,
)


def test_validate_file_path_prevents_traversal():
    """Test that path validation prevents directory traversal."""
    base_dir = Path("/tmp/test")
    
    # Valid paths
    assert validate_file_path(base_dir, "file.txt")
    assert validate_file_path(base_dir, "subdir/file.txt")
    
    # Invalid paths (traversal attempts)
    assert not validate_file_path(base_dir, "../file.txt")
    assert not validate_file_path(base_dir, "../../etc/passwd")
    assert not validate_file_path(base_dir, "/etc/passwd")


def test_validate_command_input_rejects_dangerous_input():
    """Test that command input validation rejects dangerous patterns."""
    # Valid input
    validate_command_input("normal text input")
    validate_command_input("create a function")
    
    # Invalid input - empty
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_command_input("")
    
    # Invalid input - too long
    with pytest.raises(ValueError, match="too long"):
        validate_command_input("x" * 60000)
    
    # Invalid input - shell metacharacters
    with pytest.raises(ValueError, match="suspicious characters"):
        validate_command_input("rm -rf /; echo 'pwned'")
    
    with pytest.raises(ValueError, match="suspicious characters"):
        validate_command_input("$(cat /etc/passwd)")


def test_validate_identifier():
    """Test identifier validation."""
    # Valid identifiers
    assert validate_identifier("valid-name")
    assert validate_identifier("valid_name")
    assert validate_identifier("valid123")
    
    # Invalid identifiers
    assert not validate_identifier("invalid name")  # space
    assert not validate_identifier("invalid@name")  # special char
    assert not validate_identifier("../invalid")    # path traversal


def test_validate_tool_pattern():
    """Test tool pattern validation."""
    # Valid patterns
    is_valid, _ = validate_tool_pattern("filesystem.read")
    assert is_valid
    
    is_valid, _ = validate_tool_pattern("network.*")
    assert is_valid
    
    # Invalid patterns - overly broad
    is_valid, error = validate_tool_pattern("*")
    assert not is_valid
    assert "broad" in error
    
    # Invalid patterns - suspicious
    is_valid, error = validate_tool_pattern("../etc")
    assert not is_valid
    assert "Suspicious" in error


def test_redact_secrets():
    """Test secret redaction functionality."""
    # Test various secret types
    text_with_secrets = """
    API_KEY=sk_live_1234567890abcdef
    Bearer abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
    EMAIL=user@example.com
    PHONE=555-123-4567
    """
    
    redacted = redact_secrets(text_with_secrets)
    
    # Verify secrets are redacted
    assert "sk_live_REDACTED" in redacted
    assert "Bearer REDACTED" in redacted
    assert "EMAIL_REDACTED" in redacted
    assert "PHONE_REDACTED" in redacted
    
    # Verify original secrets are not present
    assert "sk_live_1234567890abcdef" not in redacted
    assert "user@example.com" not in redacted
    assert "555-123-4567" not in redacted


def test_redact_secrets_comprehensive():
    """Test comprehensive secret redaction patterns."""
    secrets_text = """
    AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
    GITHUB_TOKEN=ghp_1234567890abcdef1234567890abcdef123456
    STRIPE_KEY=sk_test_1234567890abcdef
    DATABASE_URL=postgres://user:password@localhost/db
    SSH_KEY=ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...
    """
    
    redacted = redact_secrets(secrets_text)
    
    # Check that various secret types are redacted
    assert "AKIA_REDACTED" in redacted
    assert "ghp_REDACTED" in redacted
    assert "sk_test_REDACTED" in redacted
    assert "DATABASE_URL_REDACTED" in redacted
    assert "SSH_KEY_REDACTED" in redacted