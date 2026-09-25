from example_api import greet


def test_greet() -> None:
    assert greet("monorepo") == "hello, monorepo"
