import hashlib
import hmac
import json
from dataclasses import dataclass

from app.config import Settings

MANIFEST_PATH = ".cloudinfra/manifest.json"
SCHEMA = 1
ALGORITHM = "HMAC-SHA256"


class ManifestError(Exception):
    """The manifest is missing a field, was not signed by the platform, or was changed after signing."""


@dataclass(frozen=True)
class Generator:
    name: str
    version: str


@dataclass(frozen=True)
class Manifest:
    """What the platform generated into a repository: the design it came from and the hash of every file."""

    kind: str
    id: str
    revision: int
    generator: Generator
    input: str
    files: dict[str, str]

    @staticmethod
    def digest(content: str) -> str:
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"

    def body(self) -> dict:
        return {"schema": SCHEMA, "kind": self.kind, "id": self.id, "revision": self.revision,
                "generator": {"name": self.generator.name, "version": self.generator.version},
                "input": self.input, "files": dict(self.files)}

    @classmethod
    def from_body(cls, body: dict) -> "Manifest":
        generator = body["generator"]
        return cls(kind=body["kind"], id=body["id"], revision=body["revision"],
                   generator=Generator(generator["name"], generator["version"]), input=body["input"],
                   files=dict(body["files"]))


class ManifestSigner:
    """Signs manifests with the active key and verifies them with any configured key, so keys can rotate."""

    def __init__(self, keys: dict[str, str], active: str):
        if active not in keys:
            raise ValueError(f"The active manifest key '{active}' is not configured.")
        self._keys = dict(keys)
        self._active = active

    @classmethod
    def from_settings(cls, settings: Settings) -> "ManifestSigner":
        return cls(settings.manifest_signing_keys, settings.manifest_active_key)

    def sign(self, manifest: Manifest) -> dict:
        body = manifest.body()
        return {**body, "signature": {"algorithm": ALGORITHM, "key_id": self._active,
                                      "value": self._mac(self._active, body)}}

    def verify(self, document: dict) -> Manifest:
        try:
            body = {key: value for key, value in document.items() if key != "signature"}
            signature = document["signature"]
            key_id, value = signature["key_id"], signature["value"]
            schema = body["schema"]
        except (AttributeError, KeyError, TypeError) as error:
            raise ManifestError(f"The manifest is incomplete: {error}.") from error
        if schema != SCHEMA:
            raise ManifestError(f"The manifest schema {schema} is not supported.")
        if key_id not in self._keys:
            raise ManifestError(f"The manifest was signed with an unknown key '{key_id}'.")
        if not hmac.compare_digest(self._mac(key_id, body), str(value)):
            raise ManifestError("The manifest signature does not match: it was not written by the platform, "
                                "or was changed after it was.")
        return Manifest.from_body(body)

    def _mac(self, key_id: str, body: dict) -> str:
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hmac.new(self._keys[key_id].encode(), canonical.encode(), hashlib.sha256).hexdigest()


class ManifestSealer:
    """Adds the signed manifest to the files of one commit."""

    def __init__(self, signer: ManifestSigner):
        self._signer = signer

    def seal(self, kind: str, id: str, revision: int, generator: Generator, input: str,
             files: dict[str, str]) -> dict[str, str]:
        manifest = Manifest(kind=kind, id=id, revision=revision, generator=generator, input=input,
                            files={path: Manifest.digest(content) for path, content in sorted(files.items())})
        document = json.dumps(self._signer.sign(manifest), indent=2, sort_keys=True) + "\n"
        return {**files, MANIFEST_PATH: document}
