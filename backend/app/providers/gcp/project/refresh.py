"""Refreshes the bundled google provider schema: `uv run python -m app.providers.gcp.project.refresh [version]`.

Needs Terraform on the PATH and network access to the Terraform registry."""

import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from app.providers.gcp.project.schema import BUNDLED_PATH, GoogleProviderSchema

DEFAULT_VERSION = "8.5.0"
Runner = Callable[[list[str], Path], str]


def run(command: list[str], workdir: Path) -> str:
    return subprocess.run(command, cwd=workdir, check=True, capture_output=True, text=True).stdout


class SchemaRefresher:
    """Pins the provider version in an empty configuration, initializes it and dumps the provider schema."""

    def __init__(self, runner: Runner = run):
        self._runner = runner

    def refresh(self, version: str, target: Path = BUNDLED_PATH) -> GoogleProviderSchema:
        with tempfile.TemporaryDirectory() as directory:
            workdir = Path(directory)
            requirement = {"google": {"source": "hashicorp/google", "version": version}}
            (workdir / "main.tf.json").write_text(json.dumps({"terraform": {"required_providers": requirement}}))
            self._runner(["terraform", "init", "-input=false", "-backend=false"], workdir)
            output = json.loads(self._runner(["terraform", "providers", "schema", "-json"], workdir))
        schema = GoogleProviderSchema.from_terraform(output, version)
        schema.write(target)
        return schema


def main(argv: list[str], refresher: SchemaRefresher | None = None, target: Path = BUNDLED_PATH) -> None:
    version = argv[0] if argv else DEFAULT_VERSION
    (refresher or SchemaRefresher()).refresh(version, target)
    print(f"Wrote google provider {version} schema to {target}")


if __name__ == "__main__":
    main(sys.argv[1:])
