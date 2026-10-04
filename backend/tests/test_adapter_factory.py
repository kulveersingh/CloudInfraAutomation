import pytest

from app.adapters.factory import AdapterFactory, UnsupportedAdapterModeError
from app.adapters.local_aws import LocalAws
from app.adapters.local_github import LocalGitHub
from app.config import Settings


def test_local_github_by_default(tmp_path):
    assert isinstance(AdapterFactory().github(Settings(local_state_dir=str(tmp_path))), LocalGitHub)


def test_local_aws_by_default(tmp_path):
    assert isinstance(AdapterFactory().aws(Settings(local_state_dir=str(tmp_path))), LocalAws)


def test_unregistered_github_mode(tmp_path):
    with pytest.raises(UnsupportedAdapterModeError, match="real"):
        AdapterFactory().github(Settings(local_state_dir=str(tmp_path), github_mode="real"))


def test_unregistered_aws_mode(tmp_path):
    with pytest.raises(UnsupportedAdapterModeError, match="real"):
        AdapterFactory().aws(Settings(local_state_dir=str(tmp_path), aws_mode="real"))


def test_new_mode_can_be_registered(tmp_path):
    factory = AdapterFactory()
    factory.register_github("real", LocalGitHub)
    assert isinstance(factory.github(Settings(local_state_dir=str(tmp_path), github_mode="real")), LocalGitHub)


def test_new_aws_mode_can_be_registered(tmp_path):
    factory = AdapterFactory()
    factory.register_aws("real", LocalAws)
    assert isinstance(factory.aws(Settings(local_state_dir=str(tmp_path), aws_mode="real")), LocalAws)
