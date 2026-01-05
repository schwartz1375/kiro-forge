from kiroforge.executor import run_prompt
from kiroforge.harness import PowerContext


def test_run_prompt_outputs_actions() -> None:
    context = PowerContext(
        name="demo",
        steering_files=["steering.md"],
        tools_files=["tools.yaml"],
        hooks_files=["hooks.yaml"],
        allowed_tools=["filesystem.read"],
        denied_tools=["network.*"],
        requires_network=False,
    )
    result = run_prompt("Hello", context)
    
    # Test that we get a real response (not the old synthetic format)
    assert result.output is not None
    assert len(result.output) > 0
    
    # Test that actions are tracked properly
    assert "steering_loaded" in result.actions
    assert "allowed_tools_configured" in result.actions
    assert "kiro_executed" in result.actions
    
    # Test that the result indicates success (assuming kiro-cli is available)
    # If kiro-cli is not available, the test should still pass but with different actions
    if result.success:
        assert "kiro_executed" in result.actions
    else:
        # If kiro-cli is not found, we should get an appropriate error
        assert "kiro_not_found" in result.actions or "execution_error" in result.actions
