from pathlib import Path

from kiroforge.validator import validate_power


def test_demo_power_validates() -> None:
    power_dir = Path(__file__).parents[1] / "examples" / "kiro_powers" / "demo-power"
    result = validate_power(power_dir)
    assert result.ok, [issue.message for issue in result.issues]


def test_mcp_hook_power_validates() -> None:
    power_dir = (
        Path(__file__).parents[1] / "examples" / "kiro_powers" / "mcp-hook-power"
    )
    result = validate_power(power_dir)
    assert result.ok, [issue.message for issue in result.issues]
