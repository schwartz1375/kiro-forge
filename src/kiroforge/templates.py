"""Template management for KiroForge."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import importlib.resources


class TemplateError(Exception):
    """Base exception for template-related errors."""
    pass


class TemplateNotFoundError(TemplateError):
    """Raised when a template is not found."""
    pass


class TemplateManager:
    """Manages steering templates for KiroForge."""
    
    def __init__(self, templates_dir: Path | None = None):
        """Initialize template manager.
        
        Args:
            templates_dir: Custom templates directory. If None, uses built-in templates.
        """
        if templates_dir is None:
            # Use package templates
            try:
                import kiroforge
                package_root = Path(kiroforge.__file__).parent.parent.parent
                self.templates_dir = package_root / "templates"
            except (ImportError, AttributeError):
                # Fallback to relative path
                self.templates_dir = Path(__file__).parent.parent.parent / "templates"
        else:
            self.templates_dir = templates_dir
    
    def get_template_sets(self) -> List[str]:
        """Get available template sets.
        
        Returns:
            List of template set names
        """
        steering_dir = self.templates_dir / "steering"
        if not steering_dir.exists():
            return []
        
        return [
            d.name for d in steering_dir.iterdir() 
            if d.is_dir() and not d.name.startswith('.')
        ]
    
    def get_template_files(self, template_set: str) -> Dict[str, str]:
        """Get template files for a given set.
        
        Args:
            template_set: Name of the template set
            
        Returns:
            Dictionary mapping filename to content
            
        Raises:
            TemplateNotFoundError: If template set doesn't exist
        """
        set_dir = self.templates_dir / "steering" / template_set
        if not set_dir.exists():
            available = self.get_template_sets()
            raise TemplateNotFoundError(
                f"Template set '{template_set}' not found. Available: {available}"
            )
        
        templates = {}
        for template_file in set_dir.glob("*.md"):
            try:
                content = template_file.read_text(encoding="utf-8")
                templates[template_file.name] = content
            except (OSError, UnicodeDecodeError) as exc:
                raise TemplateError(f"Cannot read template {template_file}: {exc}") from exc
        
        return templates
    
    def get_template_content(self, template_set: str, filename: str) -> str:
        """Get content of a specific template file.
        
        Args:
            template_set: Name of the template set
            filename: Name of the template file
            
        Returns:
            Template content
            
        Raises:
            TemplateNotFoundError: If template or file doesn't exist
        """
        templates = self.get_template_files(template_set)
        if filename not in templates:
            available = list(templates.keys())
            raise TemplateNotFoundError(
                f"Template file '{filename}' not found in set '{template_set}'. "
                f"Available: {available}"
            )
        
        return templates[filename]
    
    def list_template_files(self, template_set: str) -> List[str]:
        """List available template files in a set.
        
        Args:
            template_set: Name of the template set
            
        Returns:
            List of template filenames
        """
        templates = self.get_template_files(template_set)
        return list(templates.keys())


# Global template manager instance
_template_manager = None


def get_template_manager() -> TemplateManager:
    """Get the global template manager instance."""
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager()
    return _template_manager


def get_steering_templates(template_type: str) -> Dict[str, str]:
    """Get steering templates for backward compatibility.
    
    Args:
        template_type: Template set name (foundational, common, blank)
        
    Returns:
        Dictionary mapping filename to content
    """
    manager = get_template_manager()
    try:
        return manager.get_template_files(template_type)
    except TemplateNotFoundError:
        # Fallback to empty templates for unknown sets
        return {"steering.md": "# Steering\n\nAdd steering guidance here.\n"}