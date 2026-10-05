from app.synth.blocks.registry import BlockRegistry
from app.synth.catalog import ServiceCatalog


def test_catalog_lists_every_registered_block():
    types = [entry["type"] for entry in ServiceCatalog(BlockRegistry.default()).entries()]
    assert types == ["dynamodb.table", "lambda.function", "s3.bucket", "sqs.queue"]


def test_catalog_entry_shape():
    entry = next(item for item in ServiceCatalog(BlockRegistry.default()).entries() if item["type"] == "s3.bucket")
    assert entry == {"type": "s3.bucket", "name": "S3 bucket", "category": "Storage", "multi_region": "replicated",
                     "settings": []}
