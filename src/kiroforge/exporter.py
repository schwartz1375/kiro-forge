"""Agent and Collection Export functionality."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .models import AgentSpec, CollectionSpec, PowerReference
from .parser import load_power_spec, normalize_power_reference
from .security import validate_file_path

# Version info - will be imported from __init__.py in real implementation
__version__ = "0.3.0"


class ExportError(Exception):
    """Base exception for export errors."""
    pass


class PowerCollisionError(ExportError):
    """Power resource collision error."""
    pass


def export_agent_to_kiro_json(agent_dir: Path, spec: AgentSpec) -> Dict[str, Any]:
    """Export agent specification to Kiro-native JSON format.
    
    Args:
        agent_dir: Path to agent directory
        spec: Agent specification
        
    Returns:
        dict: Kiro-native JSON representation
        
    Raises:
        ExportError: If export fails
        PowerCollisionError: If power resources collide
    """
    # Load system prompt
    prompt_file = agent_dir / spec.identity.prompt_file
    if not prompt_file.exists():
        raise ExportError(f"System prompt file not found: {spec.identity.prompt_file}")
    
    try:
        system_prompt = prompt_file.read_text(encoding="utf-8")
    except Exception as exc:
        raise ExportError(f"Failed to read system prompt: {exc}")
    
    # Merge power resources
    merged_resources = _merge_power_resources(agent_dir, spec.powers)
    
    # Build final prompt with steering content
    final_prompt = system_prompt
    if merged_resources["steering_content"]:
        final_prompt += "\n\n" + "\n\n".join(merged_resources["steering_content"])
    
    # Build Kiro JSON
    kiro_json = {
        "name": spec.meta.name,
        "description": spec.meta.description,
        "prompt": final_prompt,
        "tools": merged_resources["tools"],
        "mcpServers": merged_resources["mcp_servers"],
        "allowedTools": spec.constraints.allowed_tools,
        "disabledTools": spec.constraints.denied_tools,
        "_kiroforge": {
            "version": spec.meta.version,
            "source_agent": str(agent_dir),
            "source_powers": [normalize_power_reference(p)["path"] for p in spec.powers],
            "subagents": spec.subagents.model_dump() if spec.subagents else None,
            "collision_resolution": merged_resources["collision_metadata"],
            "constraint_resolution": _build_constraint_metadata(spec.constraints),
            "export_timestamp": datetime.utcnow().isoformat() + "Z",
            "kiroforge_version": __version__
        }
    }
    
    return kiro_json


def export_collection_to_kiro_json(collection_dir: Path, spec: CollectionSpec) -> Dict[str, Any]:
    """Export collection to multiple Kiro-native JSON files plus manifest.
    
    Args:
        collection_dir: Path to collection directory
        spec: Collection specification
        
    Returns:
        dict: Export metadata with file paths and manifest
        
    Raises:
        ExportError: If export fails
    """
    export_data = {
        "manifest": _build_collection_manifest(spec),
        "agents": {},
        "shared_context": _process_shared_context(collection_dir, spec.shared_context)
    }
    
    # Export each agent
    for agent_ref in spec.agents:
        agent_dir = collection_dir / agent_ref.path
        agent_name = Path(agent_ref.path).name
        
        try:
            from .parser import load_agent_spec
            agent_spec = load_agent_spec(agent_dir)
            
            # Merge shared context into agent
            merged_spec = _merge_shared_context(agent_spec, spec.shared_context, collection_dir)
            
            # Export agent
            agent_json = export_agent_to_kiro_json(agent_dir, merged_spec)
            export_data["agents"][agent_name] = agent_json
            
        except Exception as exc:
            raise ExportError(f"Failed to export agent {agent_name}: {exc}")
    
    return export_data


def _merge_power_resources(agent_dir: Path, power_refs: List[str | PowerReference]) -> Dict[str, Any]:
    """Merge resources from multiple powers with collision detection.
    
    Args:
        agent_dir: Path to agent directory
        power_refs: List of power references
        
    Returns:
        dict: Merged resources with collision metadata
        
    Raises:
        PowerCollisionError: If unresolved collisions exist
    """
    merged_tools = []
    merged_servers = {}
    steering_content = []
    collision_metadata = {
        "tool_collisions": [],
        "server_collisions": [],
        "steering_collisions": []
    }
    
    tool_sources = {}  # tool_name -> source_power
    server_sources = {}  # server_name -> source_power
    
    for power_ref in power_refs:
        power_data = normalize_power_reference(power_ref)
        power_path = power_data["path"]
        power_dir = agent_dir / power_path
        
        if not power_dir.exists():
            continue  # Skip missing powers (validation should catch this)
        
        try:
            power_spec = load_power_spec(power_dir / "POWER.md")
        except Exception:
            continue  # Skip invalid powers (validation should catch this)
        
        # Process steering files
        for steering_file in power_spec.resources.steering_files:
            try:
                content = (power_dir / steering_file).read_text(encoding="utf-8")
                steering_content.append(content)
            except Exception:
                continue  # Skip unreadable files
        
        # Process tools files
        for tools_file in power_spec.resources.tools_files:
            try:
                tools_data = yaml.safe_load((power_dir / tools_file).read_text())
                
                # Handle tool collisions
                if "tools" in tools_data:
                    for tool in tools_data["tools"]:
                        tool_name = tool.get("name", "")
                        if tool_name in tool_sources:
                            # Collision detected
                            if tool_name not in power_data.get("exclude_tools", []):
                                collision_metadata["tool_collisions"].append({
                                    "name": tool_name,
                                    "powers": [tool_sources[tool_name], power_path],
                                    "resolution": "unresolved",
                                    "final_source": tool_sources[tool_name]
                                })
                                continue  # Skip conflicting tool
                        
                        # Apply tool aliases
                        if tool_name in power_data.get("tool_aliases", {}):
                            tool["name"] = power_data["tool_aliases"][tool_name]
                            tool_name = tool["name"]
                        
                        if tool_name not in power_data.get("exclude_tools", []):
                            merged_tools.append(tool)
                            tool_sources[tool_name] = power_path
                
                # Handle MCP server collisions
                if "mcpServers" in tools_data:
                    for server_name, server_config in tools_data["mcpServers"].items():
                        if server_name in server_sources:
                            # Collision detected
                            collision_metadata["server_collisions"].append({
                                "name": server_name,
                                "powers": [server_sources[server_name], power_path],
                                "resolution": "unresolved",
                                "final_source": server_sources[server_name]
                            })
                            continue  # Skip conflicting server
                        
                        # Apply server aliases
                        final_server_name = power_data.get("server_aliases", {}).get(server_name, server_name)
                        merged_servers[final_server_name] = server_config
                        server_sources[final_server_name] = power_path
                        
            except Exception:
                continue  # Skip invalid tools files
    
    return {
        "tools": merged_tools,
        "mcp_servers": merged_servers,
        "steering_content": steering_content,
        "collision_metadata": collision_metadata
    }


def _build_collection_manifest(spec: CollectionSpec) -> Dict[str, Any]:
    """Build collection manifest.
    
    Args:
        spec: Collection specification
        
    Returns:
        dict: Collection manifest
    """
    return {
        "collection": spec.meta.name,
        "description": spec.meta.description,
        "version": spec.meta.version,
        "agents": [
            {
                "name": Path(agent.path).name,
                "role": agent.role,
                "description": agent.description,
                "file": f"{Path(agent.path).name}.json",
                "can_spawn_subagents": agent.can_spawn_subagents
            }
            for agent in spec.agents
        ],
        "shared_context": {
            "powers": spec.shared_context.powers,
            "steering": spec.shared_context.steering
        },
        "coordination": spec.coordination.model_dump() if spec.coordination else None,
        "export_timestamp": datetime.utcnow().isoformat() + "Z",
        "kiroforge_version": __version__
    }


def _process_shared_context(collection_dir: Path, shared_context) -> Dict[str, Any]:
    """Process shared context for collection export.
    
    Args:
        collection_dir: Path to collection directory
        shared_context: Shared context specification
        
    Returns:
        dict: Processed shared context
    """
    processed = {
        "powers": [],
        "steering": []
    }
    
    # Process shared powers
    for power_path in shared_context.powers:
        power_dir = collection_dir / power_path
        if power_dir.exists():
            try:
                power_spec = load_power_spec(power_dir / "POWER.md")
                processed["powers"].append({
                    "path": power_path,
                    "name": power_spec.meta.name,
                    "description": power_spec.meta.description
                })
            except Exception:
                processed["powers"].append({"path": power_path, "error": "Failed to load"})
    
    # Process shared steering
    for steering_path in shared_context.steering:
        steering_file = collection_dir / steering_path
        if steering_file.exists():
            try:
                content = steering_file.read_text(encoding="utf-8")
                processed["steering"].append({
                    "path": steering_path,
                    "size": len(content)
                })
            except Exception:
                processed["steering"].append({"path": steering_path, "error": "Failed to read"})
    
    return processed


def _merge_shared_context(agent_spec: AgentSpec, shared_context, collection_dir: Path) -> AgentSpec:
    """Merge shared context into agent specification.
    
    Args:
        agent_spec: Original agent specification
        shared_context: Collection shared context
        collection_dir: Path to collection directory
        
    Returns:
        AgentSpec: Agent spec with merged shared context
    """
    # Create a copy of the agent spec
    merged_spec = agent_spec.model_copy(deep=True)
    
    # Prepend shared powers to agent powers
    shared_powers = [f"../shared/powers/{Path(p).name}" for p in shared_context.powers]
    merged_spec.powers = shared_powers + merged_spec.powers
    
    # Merge constraints if collection has shared constraints
    if shared_context.constraints:
        # Apply collection constraint resolution rules
        if not merged_spec.constraints.opt_out_collection_constraints:
            # Intersection of allowed tools
            if shared_context.constraints.allowed_tools:
                merged_allowed = set(merged_spec.constraints.allowed_tools) & set(shared_context.constraints.allowed_tools)
                merged_spec.constraints.allowed_tools = list(merged_allowed)
            
            # Union of denied tools
            if shared_context.constraints.denied_tools:
                merged_denied = set(merged_spec.constraints.denied_tools) | set(shared_context.constraints.denied_tools)
                merged_spec.constraints.denied_tools = list(merged_denied)
            
            # Collection network policy wins unless agent opts out
            if shared_context.constraints.requires_network is not None:
                merged_spec.constraints.requires_network = shared_context.constraints.requires_network
    
    return merged_spec


def _build_constraint_metadata(constraints) -> Dict[str, Any]:
    """Build constraint resolution metadata.
    
    Args:
        constraints: Agent constraints
        
    Returns:
        dict: Constraint resolution metadata
    """
    return {
        "collection_constraints_applied": not constraints.opt_out_collection_constraints,
        "opt_out": constraints.opt_out_collection_constraints,
        "opt_out_justification": constraints.opt_out_justification,
        "final_allowed_tools": constraints.allowed_tools,
        "final_denied_tools": constraints.denied_tools,
        "network_access": {
            "agent_requested": constraints.requires_network,
            "final_resolution": constraints.requires_network,
            "resolution_reason": "Agent setting" if constraints.opt_out_collection_constraints else "Collection policy applied"
        }
    }


def save_agent_export(export_data: Dict[str, Any], output_file: Path) -> None:
    """Save agent export data to JSON file.
    
    Args:
        export_data: Export data from export_agent_to_kiro_json
        output_file: Output file path
        
    Raises:
        ExportError: If save fails
    """
    try:
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        raise ExportError(f"Failed to save export to {output_file}: {exc}")


def save_collection_export(export_data: Dict[str, Any], output_dir: Path) -> List[Path]:
    """Save collection export data to multiple files.
    
    Args:
        export_data: Export data from export_collection_to_kiro_json
        output_dir: Output directory
        
    Returns:
        list[Path]: List of created files
        
    Raises:
        ExportError: If save fails
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    created_files = []
    
    try:
        # Save manifest
        manifest_file = output_dir / f"{export_data['manifest']['collection']}-manifest.json"
        with manifest_file.open("w", encoding="utf-8") as f:
            json.dump(export_data["manifest"], f, indent=2, ensure_ascii=False)
        created_files.append(manifest_file)
        
        # Save individual agent files
        for agent_name, agent_data in export_data["agents"].items():
            agent_file = output_dir / f"{agent_name}.json"
            with agent_file.open("w", encoding="utf-8") as f:
                json.dump(agent_data, f, indent=2, ensure_ascii=False)
            created_files.append(agent_file)
        
        return created_files
        
    except Exception as exc:
        raise ExportError(f"Failed to save collection export: {exc}")