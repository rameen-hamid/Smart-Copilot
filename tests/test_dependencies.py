import importlib


def test_session_and_form_dependencies_import() -> None:
    assert importlib.import_module("itsdangerous")
    assert importlib.import_module("python_multipart")
    from starlette.middleware.sessions import SessionMiddleware

    assert SessionMiddleware is not None


def test_hypothesis_available() -> None:
    assert importlib.import_module("hypothesis")
