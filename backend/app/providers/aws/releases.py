from app.releases.risk import ResourceClassifier

STATEFUL_TYPES = frozenset({
    "AWS::S3::Bucket", "AWS::DynamoDB::Table", "AWS::DynamoDB::GlobalTable", "AWS::RDS::DBCluster",
    "AWS::RDS::DBInstance", "AWS::EFS::FileSystem", "AWS::Kinesis::Stream", "AWS::SQS::Queue",
    "AWS::OpenSearchService::Domain", "AWS::ElastiCache::ReplicationGroup", "AWS::Neptune::DBCluster",
    "AWS::DocDB::DBCluster", "AWS::KMS::Key", "AWS::SecretsManager::Secret",
})


class CloudFormationResourceClassifier(ResourceClassifier):
    """Which CloudFormation change-set rows hold data, and which change permissions."""

    def is_stateful(self, resource_type: str) -> bool:
        return resource_type in STATEFUL_TYPES

    def is_permission(self, resource_type: str) -> bool:
        return (resource_type.startswith("AWS::IAM::") or resource_type.endswith("Policy")
                or resource_type == "AWS::Lambda::Permission")
