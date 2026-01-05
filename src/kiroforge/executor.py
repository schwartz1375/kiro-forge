from __future__ import annotations

import subprocess
import tempfile
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .harness import PowerContext
from .security import validate_command_input, redact_secrets
from .config import get_config


@dataclass
class ExecutionResult:
    output: str
    actions: list[str]
    success: bool = True
    error: Optional[str] = None


class PowerExecutor:
    """Executes powers using real Kiro CLI integration."""
    
    def __init__(self):
        self.config = get_config()
    
    def _prepare_steering_context(self, context: PowerContext, temp_dir: Path) -> List[str]:
        """Prepare steering files for execution."""
        steering_args = []
        
        if context.steering_files:
            # Copy steering files to temp directory
            steering_dir = temp_dir / "steering"
            steering_dir.mkdir(exist_ok=True)
            
            for steering_file in context.steering_files:
                steering_path = Path(steering_file)
                if steering_path.exists():
                    dest_path = steering_dir / steering_path.name
                    shutil.copy2(steering_path, dest_path)
                    # Note: In real implementation, kiro-cli would load these automatically
                    # from .kiro/steering/ directory
        
        return steering_args
    
    def _prepare_tools_context(self, context: PowerContext) -> List[str]:
        """Prepare tool constraints for execution."""
        tool_args = []
        
        # Handle allowed tools
        if context.allowed_tools:
            # In a real implementation, this would configure MCP tool access
            # For now, we'll pass as trust-tools argument
            allowed_tools_str = ",".join(context.allowed_tools)
            tool_args.extend(["--trust-tools", allowed_tools_str])
        elif context.denied_tools:
            # If we have denied tools but no allowed tools, trust none
            tool_args.extend(["--trust-tools", ""])
        
        return tool_args
    
    def _build_kiro_command(self, prompt: str, context: PowerContext, temp_dir: Path) -> List[str]:
        """Build the kiro-cli command with power context."""
        # Security: Validate prompt input
        validate_command_input(prompt)
        
        command = ["kiro-cli", "chat"]
        
        # Add non-interactive mode
        command.append("--no-interactive")
        
        # Add tool constraints
        tool_args = self._prepare_tools_context(context)
        command.extend(tool_args)
        
        # Add timeout from config
        timeout = self.config.kiro.timeout
        
        # Add wrap mode from config
        if self.config.kiro.wrap_mode != "auto":
            command.extend(["--wrap", self.config.kiro.wrap_mode])
        
        # Add the prompt (will be quoted by subprocess)
        command.append(prompt)
        
        return command
    
    def execute(self, prompt: str, context: PowerContext) -> ExecutionResult:
        """Execute a prompt with the given power context."""
        actions = []
        
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            
            # Prepare steering context
            steering_args = self._prepare_steering_context(context, temp_dir)
            if steering_args:
                actions.append("steering_prepared")
            
            # Track what was loaded
            if context.allowed_tools:
                actions.append("allowed_tools_configured")
            if context.denied_tools:
                actions.append("denied_tools_configured")
            if context.hooks_files:
                actions.append("hooks_available")
            if context.tools_files:
                actions.append("tools_available")
            if context.steering_files:
                actions.append("steering_loaded")
            
            # Build and execute command
            try:
                command = self._build_kiro_command(prompt, context, temp_dir)
                actions.append("kiro_command_built")
                
                if self.config.kiro.debug:
                    print(f"Executing: {' '.join(command)}")
                
                # Execute with timeout
                process = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.config.kiro.timeout,
                    cwd=temp_dir,  # Run in temp directory
                )
                
                actions.append("kiro_executed")
                
                if process.returncode == 0:
                    output = process.stdout.strip()
                    # Clean and redact the output
                    output = redact_secrets(output)
                    
                    return ExecutionResult(
                        output=output,
                        actions=actions,
                        success=True
                    )
                else:
                    error_msg = process.stderr.strip() or process.stdout.strip()
                    return ExecutionResult(
                        output=f"Execution failed: {error_msg}",
                        actions=actions,
                        success=False,
                        error=error_msg
                    )
                    
            except subprocess.TimeoutExpired as exc:
                actions.append("kiro_timeout")
                return ExecutionResult(
                    output=f"Execution timed out after {self.config.kiro.timeout}s",
                    actions=actions,
                    success=False,
                    error="timeout"
                )
            except FileNotFoundError:
                actions.append("kiro_not_found")
                return ExecutionResult(
                    output="kiro-cli not found. Please install Kiro CLI.",
                    actions=actions,
                    success=False,
                    error="kiro_not_found"
                )
            except Exception as exc:
                actions.append("execution_error")
                return ExecutionResult(
                    output=f"Execution error: {exc}",
                    actions=actions,
                    success=False,
                    error=str(exc)
                )


# Global executor instance
_executor = None


def get_executor() -> PowerExecutor:
    """Get the global power executor instance."""
    global _executor
    if _executor is None:
        _executor = PowerExecutor()
    return _executor


def run_prompt(prompt: str, context: PowerContext) -> ExecutionResult:
    """Execute a prompt with the given power context (backward compatibility)."""
    executor = get_executor()
    return executor.execute(prompt, context)
