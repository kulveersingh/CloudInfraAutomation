import pytest

from app.providers.aws.teardown import CloudFormationInventory
from app.synth.request import ProjectRequest
from tests.factories import dr_request_dict, request_dict

ACCOUNT = "555555555555"


def inventory(payload: dict, environment: str = "prod", regions=("us-east-1",)):
    return CloudFormationInventory.default().for_environment(ProjectRequest.model_validate(payload), environment, ACCOUNT,
                                                        list(regions))


def test_buckets_are_data_stores_with_resolved_names():
    stores, problems = inventory(request_dict())
    [bucket] = stores
    assert (problems, bucket.service_id, bucket.resource_type, bucket.physical_name, bucket.source_ref,
            bucket.region, bucket.retained) == (
        [], "uploads", "AWS::S3::Bucket", "invoice-ingest--uploads-555555555555-us-east-1",
        "arn:aws:s3:::invoice-ingest--uploads-555555555555-us-east-1", "us-east-1", True)


def test_functions_are_not_data_stores():
    stores, _ = inventory(request_dict())
    assert "processor" not in [store.service_id for store in stores]


def test_every_region_has_its_own_bucket():
    stores, _ = inventory(dr_request_dict(), regions=("us-east-1", "us-east-2"))
    assert [store.region for store in stores] == ["us-east-1", "us-east-2"]


def test_a_global_table_is_backed_up_in_the_primary_region_only():
    payload = dr_request_dict(resources=[{"id": "orders", "type": "dynamodb.table"}], connections=[])
    stores, _ = inventory(payload, regions=("us-east-1", "us-east-2"))
    assert [(store.resource_type, store.region, store.source_ref) for store in stores] == [
        ("AWS::DynamoDB::GlobalTable", "us-east-1", "arn:aws:dynamodb:us-east-1:555555555555:table/invoice-ingest--orders")]


def test_regional_table():
    payload = request_dict(resources=[{"id": "orders", "type": "dynamodb.table"}], connections=[])
    [table], _ = inventory(payload)
    assert (table.resource_type, table.physical_name, table.retained) == (
        "AWS::DynamoDB::Table", "invoice-ingest--orders", True)


def test_schema_driven_database_with_an_identifier():
    payload = request_dict(resources=[{"id": "ledger", "type": "AWS::RDS::DBCluster", "config": {"properties": {
        "Engine": "aurora-postgresql", "DBClusterIdentifier": "ledger-db"}}}], connections=[])
    [cluster], problems = inventory(payload)
    assert (problems, cluster.source_ref, cluster.retained) == (
        [], "arn:aws:rds:us-east-1:555555555555:cluster:ledger-db", False)


@pytest.mark.parametrize("resource, kind", [
    ({"id": "ledger", "type": "AWS::RDS::DBCluster", "config": {"properties": {"Engine": "aurora-postgresql"}}},
     "AWS::RDS::DBCluster"),
    ({"id": "share", "type": "AWS::EFS::FileSystem", "config": {}}, "AWS::EFS::FileSystem"),
])
def test_data_stores_without_a_name_in_the_template_cannot_be_backed_up(resource, kind):
    payload = request_dict(resources=[resource], connections=[])
    stores, problems = inventory(payload)
    assert (stores, problems) == ([], [
        f"Cannot back up {resource['id']} ({kind}): its physical name is not in the template."])


def test_services_that_are_not_backed_up_are_listed():
    assert CloudFormationInventory.default().not_backed_up(ProjectRequest.model_validate(request_dict())) == [
        "processor (lambda.function): rebuilt from the template and the application repository"]
