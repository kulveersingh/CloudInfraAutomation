from fastapi import FastAPI


def test_module_exposes_asgi_application():
    from app.main import app

    assert isinstance(app, FastAPI)
