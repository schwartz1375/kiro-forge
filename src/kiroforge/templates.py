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
    def get_agent_templates(self) -> List[str]:
        """Get available agent templates.
        
        Returns:
            List of agent template names
        """
        agents_dir = self.templates_dir / "agents"
        if not agents_dir.exists():
            return []
        
        return [
            item.name for item in agents_dir.iterdir()
            if item.is_dir() and (item / "agent.yaml").exists()
        ]
    
    def get_collection_templates(self) -> List[str]:
        """Get available collection templates.
        
        Returns:
            List of collection template names
        """
        collections_dir = self.templates_dir / "collections"
        if not collections_dir.exists():
            return []
        
        return [
            item.name for item in collections_dir.iterdir()
            if item.is_dir() and (item / "collection.yaml").exists()
        ]
    
    def copy_agent_template(self, template_name: str, target_dir: Path) -> None:
        """Copy agent template to target directory.
        
        Args:
            template_name: Name of the agent template
            target_dir: Target directory to copy template to
            
        Raises:
            TemplateNotFoundError: If template doesn't exist
            TemplateError: If copy fails
        """
        template_dir = self.templates_dir / "agents" / template_name
        if not template_dir.exists():
            available = self.get_agent_templates()
            raise TemplateNotFoundError(f"Agent template '{template_name}' not found. Available: {', '.join(available)}")
        
        try:
            shutil.copytree(template_dir, target_dir, dirs_exist_ok=True)
        except Exception as exc:
            raise TemplateError(f"Failed to copy agent template: {exc}")
    
    def copy_collection_template(self, template_name: str, target_dir: Path) -> None:
        """Copy collection template to target directory.
        
        Args:
            template_name: Name of the collection template
            target_dir: Target directory to copy template to
            
        Raises:
            TemplateNotFoundError: If template doesn't exist
            TemplateError: If copy fails
        """
        template_dir = self.templates_dir / "collections" / template_name
        if not template_dir.exists():
            available = self.get_collection_templates()
            raise TemplateNotFoundError(f"Collection template '{template_name}' not found. Available: {', '.join(available)}")
        
        try:
            shutil.copytree(template_dir, target_dir, dirs_exist_ok=True)
        except Exception as exc:
            raise TemplateError(f"Failed to copy collection template: {exc}")
    
    def get_agent_template_info(self, template_name: str) -> Dict[str, str]:
        """Get information about an agent template.
        
        Args:
            template_name: Name of the agent template
            
        Returns:
            Dictionary with template information
            
        Raises:
            TemplateNotFoundError: If template doesn't exist
        """
        template_dir = self.templates_dir / "agents" / template_name
        if not template_dir.exists():
            raise TemplateNotFoundError(f"Agent template '{template_name}' not found")
        
        info = {"name": template_name, "description": "Agent template"}
        
        # Try to read description from agent.yaml
        agent_yaml = template_dir / "agent.yaml"
        if agent_yaml.exists():
            try:
                import yaml
                with agent_yaml.open("r") as f:
                    data = yaml.safe_load(f)
                    if "meta" in data and "description" in data["meta"]:
                        info["description"] = data["meta"]["description"]
            except Exception:
                pass  # Use default description
        
        return info
    
    def get_collection_template_info(self, template_name: str) -> Dict[str, str]:
        """Get information about a collection template.
        
        Args:
            template_name: Name of the collection template
            
        Returns:
            Dictionary with template information
            
        Raises:
            TemplateNotFoundError: If template doesn't exist
        """
        template_dir = self.templates_dir / "collections" / template_name
        if not template_dir.exists():
            raise TemplateNotFoundError(f"Collection template '{template_name}' not found")
        
        info = {"name": template_name, "description": "Collection template"}
        
        # Try to read description from collection.yaml
        collection_yaml = template_dir / "collection.yaml"
        if collection_yaml.exists():
            try:
                import yaml
                with collection_yaml.open("r") as f:
                    data = yaml.safe_load(f)
                    if "meta" in data and "description" in data["meta"]:
                        info["description"] = data["meta"]["description"]
            except Exception:
                pass  # Use default description
        
        return info