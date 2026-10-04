import json

import pytest

from app.config import Settings
from app.readback.manifest import (
    MANIFEST_PATH,
    Generator,
    Manifest,
    ManifestError,
    ManifestSealer,
    ManifestSigner,
)

GENERATOR = Generator(name="cloudinfra-synth", version="0.1.0")
FILES = {"infra.json": "{}\n", "template.yaml": "Resources: {}\n"}


def signer(keys: dict | None = None, active: str = "k1") -> ManifestSigner:
    return ManifestSigner(keys or {"k1": "secret-one"}, active)


def manifest(**overrides) -> Manifest:
    fields = {"kind": "project", "id": "invoice-ingest", "revision": 1, "generator": GENERATOR,
              "input": "infra.json", "files": {path: Manifest.digest(text) for path, text in FILES.items()}}
    return Manifest(**{**fields, **overrides})


def test_digest_is_a_prefixed_sha256():
    assert Manifest.digest("abc") == "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_sign_then_verify_returns_the_manifest():
    assert signer().verify(signer().sign(manifest())) == manifest()


def test_signed_document_names_the_algorithm_and_key():
    signature = signer().sign(manifest())["signature"]
    assert (signature["algorithm"], signature["key_id"]) == ("HMAC-SHA256", "k1")


def test_signed_document_has_schema_version_one():
    assert signer().sign(manifest())["schema"] == 1


def test_signature_does_not_depend_on_key_order():
    document = signer().sign(manifest())
    reordered = json.loads(json.dumps(document, sort_keys=False))
    reordered["files"] = dict(reversed(list(reordered["files"].items())))
    assert signer().verify(reordered) == manifest()


@pytest.mark.parametrize("field, value", [("id", "someone-else"), ("revision", 2), ("kind", "landing-zone"),
                                          ("input", "template.yaml")])
def test_tampered_field_fails_verification(field, value):
    document = {**signer().sign(manifest()), field: value}
    with pytest.raises(ManifestError, match="signature"):
        signer().verify(document)


def test_tampered_file_hash_fails_verification():
    document = signer().sign(manifest())
    document["files"]["template.yaml"] = Manifest.digest("Resources: {Evil: {}}\n")
    with pytest.raises(ManifestError, match="signature"):
        signer().verify(document)


def test_manifest_signed_with_another_secret_fails():
    document = signer({"k1": "attacker"}).sign(manifest())
    with pytest.raises(ManifestError, match="signature"):
        signer().verify(document)


def test_unknown_key_id_fails():
    document = signer({"k9": "secret"}, "k9").sign(manifest())
    with pytest.raises(ManifestError, match="k9"):
        signer().verify(document)


def test_rotated_keys_still_verify_older_manifests():
    old = signer({"k1": "secret-one"}, "k1").sign(manifest())
    rotated = signer({"k1": "secret-one", "k2": "secret-two"}, "k2")
    assert (rotated.verify(old), rotated.sign(manifest())["signature"]["key_id"]) == (manifest(), "k2")


@pytest.mark.parametrize("document", [{}, {"schema": 1}, {"schema": 2, "signature": {}}, "not an object"])
def test_malformed_documents_fail(document):
    with pytest.raises(ManifestError):
        signer().verify(document)


def test_active_key_must_exist():
    with pytest.raises(ValueError, match="k2"):
        ManifestSigner({"k1": "secret"}, "k2")


def test_signer_from_settings_uses_the_configured_keys(tmp_path):
    settings = Settings(manifest_signing_keys={"2026-10": "s3cret"}, manifest_active_key="2026-10")
    assert ManifestSigner.from_settings(settings).sign(manifest())["signature"]["key_id"] == "2026-10"


def test_default_settings_use_the_local_development_key():
    assert ManifestSigner.from_settings(Settings()).sign(manifest())["signature"]["key_id"] == "local-dev"


def test_sealer_adds_the_manifest_to_the_files():
    sealed = ManifestSealer(signer()).seal(kind="project", id="invoice-ingest", revision=1, generator=GENERATOR,
                                           input="infra.json", files=FILES)
    assert (set(sealed) - set(FILES), signer().verify(json.loads(sealed[MANIFEST_PATH]))) == (
        {MANIFEST_PATH}, manifest())


def test_sealer_leaves_the_other_files_unchanged():
    sealed = ManifestSealer(signer()).seal(kind="project", id="invoice-ingest", revision=1, generator=GENERATOR,
                                           input="infra.json", files=FILES)
    assert {path: sealed[path] for path in FILES} == FILES


def test_manifest_file_is_stable_json():
    sealed = ManifestSealer(signer()).seal(kind="project", id="invoice-ingest", revision=1, generator=GENERATOR,
                                           input="infra.json", files=FILES)
    assert sealed[MANIFEST_PATH] == json.dumps(json.loads(sealed[MANIFEST_PATH]), indent=2, sort_keys=True) + "\n"
