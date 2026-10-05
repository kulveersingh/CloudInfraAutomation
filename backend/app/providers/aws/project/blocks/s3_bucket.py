from app.providers.aws.project.access import AccessActions
from app.providers.aws.project.capabilities import (
    AccessTarget,
    AwsBlock,
    FunctionNotification,
    NotificationSource,
)
from app.providers.aws.project.policies import InsecureTransportDenial, SameTagPolicy
from app.providers.aws.project.template import Template
from app.synth.access import READ_LEVELS

S3_NAME_BUDGET = 31
NONCURRENT_VERSION_DAYS = 30
ABORT_UPLOAD_DAYS = 7


class S3BucketBlock(AwsBlock, AccessTarget, NotificationSource):
    type_name = "storage.bucket"
    aliases = ("s3.bucket",)
    display_name = "S3 bucket"
    category = "Storage"
    multi_region = "replicated"
    logical_id_suffix = "Bucket"
    provider_types = ("AWS::S3::Bucket",)
    notification_principal = "s3.amazonaws.com"
    retained_on_removal = True

    OBJECT_ACTIONS = AccessActions(read=["s3:GetObject"], write=["s3:PutObject", "s3:AbortMultipartUpload"])
    LIST_ACTIONS = ("s3:ListBucket",)

    def __init__(self, spec, request):
        super().__init__(spec, request)
        self._notifications: list[FunctionNotification] = []

    @classmethod
    def naming_problems(cls, project_name: str, resource_id: str) -> list[str]:
        too_long = len(project_name) + len(resource_id) > S3_NAME_BUDGET
        return [f"Bucket '{resource_id}' makes the S3 bucket name too long."] if too_long else []

    def add_notification(self, notification: FunctionNotification) -> None:
        self._notifications.append(notification)

    def source_arn(self) -> dict:
        return self.naming.bucket_arn()

    def notification_read_statement(self, prefix: str) -> dict:
        return {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": self.naming.bucket_arn(f"/{prefix}*")}

    def access_statements(self, access: str, prefix: str) -> list[dict]:
        objects = {"Effect": "Allow", "Action": self.OBJECT_ACTIONS.for_level(access),
                   "Resource": self.naming.bucket_arn(f"/{prefix}*")}
        listing = {"Effect": "Allow", "Action": list(self.LIST_ACTIONS), "Resource": self.naming.bucket_arn()}
        return [objects, listing] if access in READ_LEVELS else [objects]

    def environment_binding(self) -> tuple[str, object]:
        return self.naming.environment_variable("BUCKET_NAME"), {"Fn::Sub": self.naming.bucket_name()}

    def contract_entry(self) -> dict:
        return {"bucketName": self.naming.bucket_name()}

    def emit(self, template: Template) -> None:
        template.add_resource(self.logical_id, self._bucket())
        template.add_resource(f"{self.logical_id}Policy", self._bucket_policy())
        template.add_output(f"{self.logical_id}Name", {"Value": {"Ref": self.logical_id}})

    def _bucket(self) -> dict:
        properties = {
            "BucketName": {"Fn::Sub": self.naming.bucket_name()},
            "PublicAccessBlockConfiguration": {"BlockPublicAcls": True, "BlockPublicPolicy": True,
                                               "IgnorePublicAcls": True, "RestrictPublicBuckets": True},
            "OwnershipControls": {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]},
            "BucketEncryption": {"ServerSideEncryptionConfiguration": [
                {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]},
            "VersioningConfiguration": {"Status": "Enabled"},
            "LifecycleConfiguration": {"Rules": [{
                "Id": "expire-old-versions", "Status": "Enabled",
                "NoncurrentVersionExpiration": {"NoncurrentDays": NONCURRENT_VERSION_DAYS},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": ABORT_UPLOAD_DAYS}}]},
        }
        bucket = {"Type": "AWS::S3::Bucket", "Properties": properties,
                  "DeletionPolicy": "RetainExceptOnCreate", "UpdateReplacePolicy": "Retain"}
        if self._notifications:
            self._attach_notifications(bucket)
        return bucket

    def _attach_notifications(self, bucket: dict) -> None:
        configurations = [self._lambda_configuration(notification, event)
                          for notification in self._notifications for event in notification.events]
        bucket["Properties"]["NotificationConfiguration"] = {
            "Fn::If": ["IsActive", {"LambdaConfigurations": configurations}, {"Ref": "AWS::NoValue"}]}
        bucket["DependsOn"] = sorted({notification.permission_id for notification in self._notifications})

    def _lambda_configuration(self, notification: FunctionNotification, event: str) -> dict:
        rules = [{"Name": name, "Value": value}
                 for name, value in (("prefix", notification.prefix), ("suffix", notification.suffix)) if value]
        configuration = {"Event": event, "Function": notification.function_arn}
        configuration.update({"Filter": {"S3Key": {"Rules": rules}}} if rules else {})
        return configuration

    def _bucket_policy(self) -> dict:
        resources = [self.naming.bucket_arn(), self.naming.bucket_arn("/*")]
        transport = InsecureTransportDenial("s3:*", resources).statement()
        return {"Type": "AWS::S3::BucketPolicy", "Properties": {
            "Bucket": {"Ref": self.logical_id},
            "PolicyDocument": SameTagPolicy("s3:*", resources).document((transport,))}}
