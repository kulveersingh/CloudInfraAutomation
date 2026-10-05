from app.providers.aws.project.toolkit import aws_blocks
from app.synth.catalog import ServiceCatalog


def test_catalog_lists_every_registered_block():
    types = [entry["type"] for entry in ServiceCatalog(aws_blocks()).entries()]
    assert types == ["compute.function", "database.table", "messaging.queue", "storage.bucket"]


def test_catalog_entry_shape():
    entry = next(item for item in ServiceCatalog(aws_blocks()).entries() if item["type"] == "storage.bucket")
    assert entry == {"type": "storage.bucket", "name": "S3 bucket", "category": "Storage", "multi_region": "replicated",
                     "settings": []}
