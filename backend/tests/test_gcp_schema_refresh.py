import gzip
import json

from app.providers.gcp.project.refresh import DEFAULT_VERSION, SchemaRefresher, main, run

SCHEMA = {"provider_schemas": {"registry.terraform.io/hashicorp/google": {"resource_schemas": {
    "google_x": {"block": {"attributes": {"name": {"required": True}}}}}}}}


class FakeTerraform:
    def __init__(self):
        self.calls = []

    def __call__(self, command, workdir):
        self.calls.append((command, json.loads((workdir / "main.tf.json").read_text())))
        return json.dumps(SCHEMA) if "schema" in command else ""


def written(path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()))


def test_refresh_pins_the_provider_and_writes_the_trimmed_schema(tmp_path):
    terraform = FakeTerraform()
    SchemaRefresher(terraform).refresh("9.0.0", tmp_path / "schema.json.gz")
    (init, pinned), (dump, _) = terraform.calls
    assert (init[:2], dump, pinned["terraform"]["required_providers"]["google"]["version"],
            written(tmp_path / "schema.json.gz")["version"]) == (
        ["terraform", "init"], ["terraform", "providers", "schema", "-json"], "9.0.0", "9.0.0")


def test_main_refreshes_the_default_version(tmp_path, capsys):
    main([], SchemaRefresher(FakeTerraform()), tmp_path / "schema.json.gz")
    assert (written(tmp_path / "schema.json.gz")["version"], DEFAULT_VERSION in capsys.readouterr().out) == (
        DEFAULT_VERSION, True)


def test_commands_run_in_the_working_directory(tmp_path):
    assert run(["pwd"], tmp_path).strip().endswith(tmp_path.name)
