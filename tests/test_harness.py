from kiroforge.harness import TestCase, TestSuite, run_suite


def test_run_suite_without_context_uses_prompt() -> None:
    suite = TestSuite(
        cases=[TestCase(name="case", prompt="Hello", expected=["Hello"])],
    )
    results = run_suite(suite)
    assert results[0].status == "pass"
