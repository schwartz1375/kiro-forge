from kiroforge.models import PowerSpec
from kiroforge.router import select_powers


def test_route_matches_phrase() -> None:
    spec = PowerSpec.model_validate(
        {
            "meta": {
                "name": "demo",
                "description": "Demo power for routing.",
                "version": "0.1.0",
            },
            "triggers": {"phrases": ["demo power"]},
        }
    )
    matches = select_powers([spec], "Use the demo power now")
    assert matches
    assert matches[0].name == "demo"
