from pathlib import Path

from kiroforge.steering import validate_steering


def test_validate_steering_ok(tmp_path: Path) -> None:
    steering = tmp_path / "steering.md"
    steering.write_text("# Project Steering\n\nContent", encoding="utf-8")
    result = validate_steering(steering)
    assert result.ok
