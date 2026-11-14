import importlib


def test_package_is_importable() -> None:
    package = importlib.import_module("emotion_painting")

    assert package.__doc__
