"""Configuration management for KiroForge."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field


class RouterConfig(BaseModel):
    """Configuration for power routing."""
    min_score: int = Field(default=1, ge=0, description="Minimum score for power selection")
    max_results: int = Field(default=10, ge=1, le=50, description="Maximum results to return")
    fuzzy_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="Fuzzy matching threshold")
    keyword_threshold: float = Field(default=0.3, ge=0.0, le=1.0, description="Keyword overlap threshold")
    semantic_threshold: float = Field(default=0.2, ge=0.0, le=1.0, description="Semantic matching threshold")


class ValidationConfig(BaseModel):
    """Configuration for power validation."""
    max_file_size: int = Field(default=1024*1024, ge=1024, description="Maximum YAML file size in bytes")
    strict_spdx: bool = Field(default=False, description="Require strict SPDX license identifiers")
    require_tests: bool = Field(default=False, description="Require test files for all powers")


class TemplateConfig(BaseModel):
    """Configuration for templates."""
    custom_templates_dir: Optional[Path] = Field(default=None, description="Custom templates directory")
    default_template_set: str = Field(default="common", description="Default template set for steering")


class KiroConfig(BaseModel):
    """Configuration for Kiro CLI integration."""
    timeout: int = Field(default=60, ge=1, description="Timeout for kiro-cli calls in seconds")
    trust_mode: str = Field(default="none", description="Default trust mode: all, none, or custom")
    wrap_mode: str = Field(default="auto", description="Output wrapping mode: auto, never, always")
    debug: bool = Field(default=False, description="Enable debug output for kiro-cli calls")


class KiroForgeConfig(BaseModel):
    """Main KiroForge configuration."""
    router: RouterConfig = Field(default_factory=RouterConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    templates: TemplateConfig = Field(default_factory=TemplateConfig)
    kiro: KiroConfig = Field(default_factory=KiroConfig)


class ConfigManager:
    """Manages KiroForge configuration."""
    
    def __init__(self):
        self._config: Optional[KiroForgeConfig] = None
        self._config_paths = self._get_config_paths()
    
    def _get_config_paths(self) -> list[Path]:
        """Get potential configuration file paths in order of precedence."""
        paths = []
        
        # 1. Environment variable
        if env_config := os.getenv("KIROFORGE_CONFIG"):
            paths.append(Path(env_config))
        
        # 2. Current directory
        paths.append(Path.cwd() / "kiroforge.yaml")
        paths.append(Path.cwd() / "kiroforge.yml")
        paths.append(Path.cwd() / ".kiroforge.yaml")
        paths.append(Path.cwd() / ".kiroforge.yml")
        
        # 3. User home directory
        home = Path.home()
        paths.append(home / ".kiroforge" / "config.yaml")
        paths.append(home / ".kiroforge" / "config.yml")
        paths.append(home / ".config" / "kiroforge" / "config.yaml")
        paths.append(home / ".config" / "kiroforge" / "config.yml")
        
        return paths
    
    def _load_config_file(self, path: Path) -> Dict[str, Any]:
        """Load configuration from a YAML file."""
        try:
            with path.open('r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                if not isinstance(data, dict):
                    raise ValueError(f"Configuration file must contain a YAML object: {path}")
                return data
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in configuration file {path}: {exc}") from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"Cannot read configuration file {path}: {exc}") from exc
    
    def load_config(self) -> KiroForgeConfig:
        """Load configuration from files and environment."""
        if self._config is not None:
            return self._config
        
        # Start with default configuration
        config_data = {}
        
        # Load from configuration files (later files override earlier ones)
        for config_path in self._config_paths:
            if config_path.exists() and config_path.is_file():
                try:
                    file_data = self._load_config_file(config_path)
                    # Merge configuration (simple dict update for now)
                    config_data.update(file_data)
                    break  # Use first found config file
                except ValueError as exc:
                    # Log warning but continue with other config files
                    print(f"Warning: {exc}")
                    continue
        
        # Override with environment variables
        self._apply_env_overrides(config_data)
        
        # Validate and create configuration object
        try:
            self._config = KiroForgeConfig.model_validate(config_data)
        except Exception as exc:
            raise ValueError(f"Invalid configuration: {exc}") from exc
        
        return self._config
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> None:
        """Apply environment variable overrides to configuration."""
        env_mappings = {
            'KIROFORGE_ROUTER_MIN_SCORE': ('router', 'min_score', int),
            'KIROFORGE_ROUTER_MAX_RESULTS': ('router', 'max_results', int),
            'KIROFORGE_VALIDATION_MAX_FILE_SIZE': ('validation', 'max_file_size', int),
            'KIROFORGE_VALIDATION_STRICT_SPDX': ('validation', 'strict_spdx', lambda x: x.lower() in ('true', '1', 'yes')),
            'KIROFORGE_KIRO_TIMEOUT': ('kiro', 'timeout', int),
            'KIROFORGE_KIRO_TRUST_MODE': ('kiro', 'trust_mode', str),
            'KIROFORGE_KIRO_DEBUG': ('kiro', 'debug', lambda x: x.lower() in ('true', '1', 'yes')),
        }
        
        for env_var, (section, key, converter) in env_mappings.items():
            if value := os.getenv(env_var):
                try:
                    converted_value = converter(value)
                    if section not in config_data:
                        config_data[section] = {}
                    config_data[section][key] = converted_value
                except (ValueError, TypeError) as exc:
                    print(f"Warning: Invalid value for {env_var}: {value} ({exc})")
    
    def get_config(self) -> KiroForgeConfig:
        """Get the current configuration, loading if necessary."""
        return self.load_config()
    
    def reload_config(self) -> KiroForgeConfig:
        """Reload configuration from files."""
        self._config = None
        return self.load_config()
    
    def save_config(self, config: KiroForgeConfig, path: Optional[Path] = None) -> None:
        """Save configuration to a file."""
        if path is None:
            # Use first writable config path
            config_dir = Path.home() / ".kiroforge"
            config_dir.mkdir(exist_ok=True)
            path = config_dir / "config.yaml"
        
        try:
            with path.open('w', encoding='utf-8') as f:
                yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=True)
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f"Cannot save configuration to {path}: {exc}") from exc


# Global configuration manager
_config_manager = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> KiroForgeConfig:
    """Get the current KiroForge configuration."""
    return get_config_manager().get_config()