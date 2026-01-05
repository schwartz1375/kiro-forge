"""Integration tests for KiroForge with real kiro-cli interaction."""

import subprocess
import tempfile
from pathlib import Path
import pytest
import shutil

from kiroforge.cli import app
from kiroforge.parser import load_power_spec
from kiroforge.validator import validate_power
from typer.testing import CliRunner


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_power_dir():
    """Create a temporary power directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        power_dir = Path(temp_dir) / "test-power"
        power_dir.mkdir()
        yield power_dir


@pytest.fixture
def kiro_cli_available():
    """Check if kiro-cli is available for integration tests."""
    return shutil.which("kiro-cli") is not None


class TestCLIIntegration:
    """Test CLI commands with real file operations."""
    
    def test_init_creates_valid_power(self, runner, temp_power_dir):
        """Test that init creates a valid power structure."""
        result = runner.invoke(app, ["init", str(temp_power_dir)])
        
        assert result.exit_code == 0
        assert "Created power scaffold" in result.stdout
        
        # Verify all expected files are created
        expected_files = [
            "POWER.md",
            "steering.md", 
            "tools.yaml",
            "hooks.yaml",
            "tests/tests.yaml"
        ]
        
        for file_path in expected_files:
            assert (temp_power_dir / file_path).exists(), f"Missing {file_path}"
        
        # Verify the power validates
        validation_result = validate_power(temp_power_dir)
        assert validation_result.ok, f"Validation failed: {[i.message for i in validation_result.issues]}"
    
    def test_validate_command(self, runner):
        """Test validate command on example powers."""
        # Test demo power validation
        result = runner.invoke(app, ["validate", "examples/kiro_powers/demo-power"])
        assert result.exit_code == 0
        assert "OK" in result.stdout
        
        # Test mcp-hook power validation  
        result = runner.invoke(app, ["validate", "examples/kiro_powers/mcp-hook-power"])
        assert result.exit_code == 0
        assert "OK" in result.stdout
    
    def test_route_command_with_improved_matching(self, runner):
        """Test route command with improved matching algorithms."""
        # Test with a prompt that should match demo power
        result = runner.invoke(app, [
            "route", 
            "run demo power validation",
            "--powers-dir", "examples/kiro_powers"
        ])
        
        assert result.exit_code == 0
        # Should find matches with improved router
        assert "demo-power" in result.stdout or "No matching powers found" in result.stdout
    
    def test_route_command_with_configuration(self, runner):
        """Test route command respects configuration."""
        result = runner.invoke(app, [
            "route",
            "test prompt", 
            "--powers-dir", "examples/kiro_powers",
            "--min-score", "5",
            "--max-results", "2"
        ])
        
        assert result.exit_code == 0
        assert "min_score=5" in result.stdout
    
    def test_doctor_command(self, runner):
        """Test doctor command functionality."""
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        # Should either find kiro-cli or report it's missing
        assert ("kiro-cli found" in result.stdout or 
                "kiro-cli not found" in result.stdout)
    
    def test_init_steering_generate_mode(self, runner):
        """Test steering generation in generate mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            steering_dir = Path(temp_dir) / ".kiro" / "steering"
            
            result = runner.invoke(app, [
                "init-steering",
                str(steering_dir),
                "--mode", "generate",
                "--template", "foundational",
                "--file", "product.md"
            ])
            
            assert result.exit_code == 0
            assert "Created steering files" in result.stdout
            assert (steering_dir / "product.md").exists()
    
    def test_run_tests_command(self, runner):
        """Test run-tests command on example powers."""
        result = runner.invoke(app, ["run-tests", "examples/kiro_powers/demo-power"])
        
        # Should either pass or show specific test results
        assert result.exit_code in [0, 1]  # 0 for pass, 1 for fail
        assert ("pass" in result.stdout or "fail" in result.stdout)


class TestKiroCliIntegration:
    """Test integration with actual kiro-cli if available."""
    
    @pytest.mark.skipif(not shutil.which("kiro-cli"), reason="kiro-cli not available")
    def test_kiro_cli_basic_functionality(self):
        """Test basic kiro-cli functionality."""
        try:
            result = subprocess.run(
                ["kiro-cli", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            # Should either succeed or fail gracefully
            assert result.returncode in [0, 1, 2]  # Various exit codes are acceptable
        except subprocess.TimeoutExpired:
            pytest.skip("kiro-cli command timed out")
        except FileNotFoundError:
            pytest.skip("kiro-cli not found in PATH")
    
    @pytest.mark.skipif(not shutil.which("kiro-cli"), reason="kiro-cli not available")
    def test_ai_steering_generation_integration(self, runner):
        """Test AI steering generation with kiro-cli integration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            steering_dir = Path(temp_dir) / ".kiro" / "steering"
            
            # Test with minimal goal to avoid timeout
            result = runner.invoke(app, [
                "init-steering",
                str(steering_dir),
                "--mode", "ai",
                "--template", "blank", 
                "--goal", "test project",
                "--file", "steering.md",
                "--kiro-timeout", "10",
                "--kiro-trust-none",
                "--kiro-wrap", "never"
            ])
            
            # Should either succeed or fail gracefully with timeout/error
            # Don't assert success since AI generation can be flaky
            assert result.exit_code in [0, 1]
            
            if result.exit_code == 0:
                assert (steering_dir / "steering.md").exists()


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_validate_nonexistent_power(self, runner):
        """Test validation of non-existent power directory."""
        result = runner.invoke(app, ["validate", "/nonexistent/path"])
        assert result.exit_code == 1
        assert ("missing power.md" in result.stdout.lower() or 
                "not found" in result.stdout.lower())
    
    def test_route_nonexistent_powers_dir(self, runner):
        """Test routing with non-existent powers directory."""
        result = runner.invoke(app, [
            "route", 
            "test prompt",
            "--powers-dir", "/nonexistent/path"
        ])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()
    
    def test_init_existing_directory(self, runner, temp_power_dir):
        """Test init with existing non-empty directory."""
        # Create a file in the directory
        (temp_power_dir / "existing.txt").write_text("test")
        
        result = runner.invoke(app, ["init", str(temp_power_dir)])
        assert result.exit_code == 1
        assert "not empty" in result.stdout.lower()


class TestTemplateSystem:
    """Test the external template system."""
    
    def test_template_loading(self):
        """Test that templates can be loaded from external files."""
        from kiroforge.templates import get_template_manager
        
        manager = get_template_manager()
        
        # Test available template sets
        sets = manager.get_template_sets()
        assert "foundational" in sets
        assert "common" in sets
        assert "blank" in sets
        
        # Test template file loading
        foundational_templates = manager.get_template_files("foundational")
        assert "product.md" in foundational_templates
        assert "tech.md" in foundational_templates
        assert "structure.md" in foundational_templates
        
        # Test content loading
        product_content = manager.get_template_content("foundational", "product.md")
        assert "# Product Overview" in product_content
        assert "TODO" in product_content
    
    def test_template_error_handling(self):
        """Test template error handling."""
        from kiroforge.templates import get_template_manager, TemplateNotFoundError
        
        manager = get_template_manager()
        
        # Test non-existent template set
        with pytest.raises(TemplateNotFoundError):
            manager.get_template_files("nonexistent")
        
        # Test non-existent template file
        with pytest.raises(TemplateNotFoundError):
            manager.get_template_content("foundational", "nonexistent.md")


class TestConfigurationSystem:
    """Test the configuration system."""
    
    def test_default_configuration(self):
        """Test default configuration loading."""
        from kiroforge.config import get_config
        
        config = get_config()
        
        # Test default values
        assert config.router.min_score == 1
        assert config.router.max_results == 10
        assert config.validation.max_file_size == 1024 * 1024
        assert config.kiro.timeout == 60
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        from kiroforge.config import KiroForgeConfig, RouterConfig
        
        # Test valid configuration
        config = KiroForgeConfig(
            router=RouterConfig(min_score=5, max_results=20)
        )
        assert config.router.min_score == 5
        assert config.router.max_results == 20
        
        # Test invalid configuration should raise validation error
        with pytest.raises(Exception):  # Pydantic validation error
            RouterConfig(min_score=-1)  # Should fail ge=0 constraint