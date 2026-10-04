import json

from app.synth.naming import ResourceNaming
from app.synth.synthesizer import ENGINE_VERSION
from tests.factories import dr_request_dict, request_dict, with_resources
from tests.synth_helpers import (
    dependency_graph,
    has_cycle,
    properties,
    resource,
    role_statements,
    statements_by_sid,
    synthesize,
)

UPLOADS = ResourceNaming("uploads")
SAME_TAG_PROJECT = {"aws:PrincipalTag/org:project": {"Ref": "ProjectName"}}
SAME_TAG_ENVIRONMENT = {"aws:PrincipalTag/org:environment": {"Ref": "EnvironmentName"}}


# ---- parameters, conditions, metadata ----

def test_core_parameters_present():
    expected = {"ProjectName", "EnvironmentName", "ResilienceMode", "RegionRole", "ActivationState"}
    assert expected <= set(synthesize(request_dict())["Parameters"])


def test_code_parameters_present_with_lambda():
    assert {"CodeS3Bucket", "CodeS3Key"} <= set(synthesize(request_dict())["Parameters"])


def test_no_code_parameters_without_lambda():
    payload = request_dict(resources=[{"id": "uploads", "type": "s3.bucket"}], connections=[])
    assert "CodeS3Bucket" not in synthesize(payload)["Parameters"]


def test_activation_state_values():
    assert synthesize(request_dict())["Parameters"]["ActivationState"]["AllowedValues"] == ["active", "standby"]


def test_is_active_condition():
    assert synthesize(request_dict())["Conditions"]["IsActive"] == {
        "Fn::Equals": [{"Ref": "ActivationState"}, "active"]}


def test_is_primary_condition():
    assert synthesize(request_dict())["Conditions"]["IsPrimary"] == {
        "Fn::Equals": [{"Ref": "RegionRole"}, "primary"]}


def test_generator_metadata():
    assert synthesize(request_dict())["Metadata"]["Generator"] == {"name": "cloudinfra-synth",
                                                                   "version": ENGINE_VERSION}


def test_synthesis_is_deterministic():
    assert json.dumps(synthesize(request_dict())) == json.dumps(synthesize(request_dict()))


# ---- S3 bucket ----

def test_bucket_name():
    assert properties(synthesize(request_dict()), "UploadsBucket")["BucketName"] == {
        "Fn::Sub": UPLOADS.bucket_name()}


def test_bucket_blocks_public_access():
    block = properties(synthesize(request_dict()), "UploadsBucket")["PublicAccessBlockConfiguration"]
    assert all(block.values()) and len(block) == 4


def test_bucket_versioning_enabled():
    assert properties(synthesize(request_dict()), "UploadsBucket")["VersioningConfiguration"] == {
        "Status": "Enabled"}


def test_bucket_encryption():
    encryption = properties(synthesize(request_dict()), "UploadsBucket")["BucketEncryption"]
    assert encryption["ServerSideEncryptionConfiguration"][0]["ServerSideEncryptionByDefault"] == {
        "SSEAlgorithm": "AES256"}


def test_bucket_retention_policies():
    bucket = resource(synthesize(request_dict()), "UploadsBucket")
    assert (bucket["DeletionPolicy"], bucket["UpdateReplacePolicy"]) == ("RetainExceptOnCreate", "Retain")


def test_bucket_policy_denies_other_projects():
    statement = statements_by_sid(properties(synthesize(request_dict()), "UploadsBucketPolicy")[
        "PolicyDocument"])["DenyOtherProjects"]
    assert (statement["Effect"], statement["Condition"]["StringNotEquals"]) == ("Deny", SAME_TAG_PROJECT)


def test_bucket_policy_denies_other_environments():
    statement = statements_by_sid(properties(synthesize(request_dict()), "UploadsBucketPolicy")[
        "PolicyDocument"])["DenyOtherEnvironments"]
    assert statement["Condition"]["StringNotEquals"] == SAME_TAG_ENVIRONMENT


def test_bucket_policy_exempts_aws_services():
    statement = statements_by_sid(properties(synthesize(request_dict()), "UploadsBucketPolicy")[
        "PolicyDocument"])["DenyOtherProjects"]
    assert statement["Condition"]["BoolIfExists"] == {"aws:PrincipalIsAWSService": "false"}


def test_bucket_policy_denies_insecure_transport():
    statement = statements_by_sid(properties(synthesize(request_dict()), "UploadsBucketPolicy")[
        "PolicyDocument"])["DenyInsecureTransport"]
    assert statement["Condition"] == {"Bool": {"aws:SecureTransport": "false"}}


def test_bucket_output():
    assert synthesize(request_dict())["Outputs"]["UploadsBucketName"] == {"Value": {"Ref": "UploadsBucket"}}


# ---- Lambda function ----

def test_function_defaults():
    function = properties(synthesize(request_dict()), "ProcessorFunction")
    assert (function["Runtime"], function["Architectures"], function["MemorySize"], function["Timeout"]) == (
        "python3.13", ["arm64"], 256, 30)


def test_function_configuration_overrides():
    payload = request_dict(resources=[{"id": "processor", "type": "lambda.function",
                                       "config": {"runtime": "python3.12", "memory_mb": 512, "timeout_sec": 60}}],
                           connections=[])
    function = properties(synthesize(payload), "ProcessorFunction")
    assert (function["Runtime"], function["MemorySize"], function["Timeout"]) == ("python3.12", 512, 60)


def test_function_name_and_role():
    function = properties(synthesize(request_dict()), "ProcessorFunction")
    assert (function["FunctionName"], function["Role"]) == (
        {"Fn::Sub": "${ProjectName}--processor"}, {"Fn::GetAtt": ["ProcessorRole", "Arn"]})


def test_function_code_location():
    assert properties(synthesize(request_dict()), "ProcessorFunction")["Code"] == {
        "S3Bucket": {"Ref": "CodeS3Bucket"}, "S3Key": {"Ref": "CodeS3Key"}}


def test_function_disabled_in_standby():
    assert properties(synthesize(request_dict()), "ProcessorFunction")["ReservedConcurrentExecutions"] == {
        "Fn::If": ["IsActive", {"Ref": "AWS::NoValue"}, 0]}


def test_function_uses_its_log_group():
    assert properties(synthesize(request_dict()), "ProcessorFunction")["LoggingConfig"] == {
        "LogGroup": {"Ref": "ProcessorLogGroup"}, "LogFormat": "JSON"}


def test_log_group():
    log_group = properties(synthesize(request_dict()), "ProcessorLogGroup")
    assert (log_group["LogGroupName"], log_group["RetentionInDays"]) == (
        {"Fn::Sub": "/aws/lambda/${ProjectName}--processor"}, 30)


def test_role_boundary_and_path():
    role = properties(synthesize(request_dict()), "ProcessorRole")
    assert (role["Path"], role["PermissionsBoundary"]) == (
        {"Fn::Sub": "/app/${ProjectName}/"},
        {"Fn::Sub": "arn:${AWS::Partition}:iam::${AWS::AccountId}:policy/cloudinfra-app-boundary"})


def test_role_trusts_lambda():
    trust = properties(synthesize(request_dict()), "ProcessorRole")["AssumeRolePolicyDocument"]
    assert trust["Statement"][0]["Principal"] == {"Service": "lambda.amazonaws.com"}


def test_role_can_write_own_logs():
    assert {"Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
            "Resource": {"Fn::GetAtt": ["ProcessorLogGroup", "Arn"]}} in role_statements(
        synthesize(request_dict()), "ProcessorRole")


def test_function_output():
    assert synthesize(request_dict())["Outputs"]["ProcessorFunctionArn"] == {
        "Value": {"Fn::GetAtt": ["ProcessorFunction", "Arn"]}}


# ---- event.notify (S3 -> Lambda) ----

def test_invoke_permission_uses_built_source_arn():
    permission = properties(synthesize(request_dict()), "ProcessorFunctionInvokeFromUploadsBucket")
    assert (permission["Principal"], permission["SourceArn"], permission["SourceAccount"]) == (
        "s3.amazonaws.com", UPLOADS.bucket_arn(), {"Ref": "AWS::AccountId"})


def test_bucket_waits_for_permission():
    assert resource(synthesize(request_dict()), "UploadsBucket")["DependsOn"] == [
        "ProcessorFunctionInvokeFromUploadsBucket"]


def test_notification_only_when_active():
    notification = properties(synthesize(request_dict()), "UploadsBucket")["NotificationConfiguration"]
    assert (notification["Fn::If"][0], notification["Fn::If"][2]) == ("IsActive", {"Ref": "AWS::NoValue"})


def test_notification_targets_function_with_prefix_filter():
    configuration = properties(synthesize(request_dict()), "UploadsBucket")["NotificationConfiguration"][
        "Fn::If"][1]["LambdaConfigurations"][0]
    assert configuration == {"Event": "s3:ObjectCreated:*",
                             "Function": {"Fn::GetAtt": ["ProcessorFunction", "Arn"]},
                             "Filter": {"S3Key": {"Rules": [{"Name": "prefix", "Value": "incoming/"}]}}}


def test_notification_without_filter():
    payload = request_dict(connections=[{"kind": "event.notify", "source": "uploads", "target": "processor"}])
    configuration = properties(synthesize(payload), "UploadsBucket")["NotificationConfiguration"][
        "Fn::If"][1]["LambdaConfigurations"][0]
    assert "Filter" not in configuration


def test_notification_suffix_filter():
    payload = request_dict(connections=[{"kind": "event.notify", "source": "uploads", "target": "processor",
                                         "suffix": ".pdf"}])
    rules = properties(synthesize(payload), "UploadsBucket")["NotificationConfiguration"][
        "Fn::If"][1]["LambdaConfigurations"][0]["Filter"]["S3Key"]["Rules"]
    assert rules == [{"Name": "suffix", "Value": ".pdf"}]


def test_function_may_read_triggering_prefix():
    assert {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": UPLOADS.bucket_arn("/incoming/*")} in \
        role_statements(synthesize(request_dict()), "ProcessorRole")


def test_identical_grants_are_not_duplicated():
    payload = request_dict(connections=[
        {"kind": "event.notify", "source": "uploads", "target": "processor"},
        {"kind": "iam.access", "source": "processor", "target": "uploads", "access": "read"}])
    read_objects = {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": UPLOADS.bucket_arn("/*")}
    assert role_statements(synthesize(payload), "ProcessorRole").count(read_objects) == 1


def test_function_receives_bucket_name():
    assert properties(synthesize(request_dict()), "ProcessorFunction")["Environment"]["Variables"][
        "UPLOADS_BUCKET_NAME"] == {"Fn::Sub": UPLOADS.bucket_name()}


def test_no_circular_dependency():
    assert not has_cycle(dependency_graph(synthesize(request_dict())))


# ---- iam.access ----

def _access_payload(target: dict, access: str, prefix: str = "") -> dict:
    return with_resources(target, connections=[{"kind": "iam.access", "source": "processor",
                                                "target": target["id"], "access": access, "prefix": prefix}])


def _statement_for(template: dict, resource_ref) -> dict:
    statements = role_statements(template, "ProcessorRole")
    return next(statement for statement in statements if statement["Resource"] == resource_ref)


def test_s3_read_access_on_objects():
    template = synthesize(_access_payload({"id": "archive", "type": "s3.bucket"}, "read", "reports/"))
    assert _statement_for(template, ResourceNaming("archive").bucket_arn("/reports/*"))["Action"] == [
        "s3:GetObject"]


def test_s3_read_access_lists_bucket():
    template = synthesize(_access_payload({"id": "archive", "type": "s3.bucket"}, "read"))
    assert _statement_for(template, ResourceNaming("archive").bucket_arn())["Action"] == ["s3:ListBucket"]


def test_s3_write_access():
    template = synthesize(_access_payload({"id": "archive", "type": "s3.bucket"}, "write"))
    assert _statement_for(template, ResourceNaming("archive").bucket_arn("/*"))["Action"] == [
        "s3:PutObject", "s3:AbortMultipartUpload"]


def test_s3_readwrite_access_merges_object_actions():
    template = synthesize(_access_payload({"id": "archive", "type": "s3.bucket"}, "readwrite"))
    assert _statement_for(template, ResourceNaming("archive").bucket_arn("/*"))["Action"] == [
        "s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload"]


def test_dynamodb_readwrite_actions():
    template = synthesize(_access_payload({"id": "invoices", "type": "dynamodb.table"}, "readwrite"))
    table = ResourceNaming("invoices").table_arn()
    statement = _statement_for(template, [table, {"Fn::Sub": table["Fn::Sub"] + "/index/*"}])
    assert sorted(statement["Action"]) == sorted([
        "dynamodb:GetItem", "dynamodb:Query", "dynamodb:BatchGetItem", "dynamodb:PutItem",
        "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:BatchWriteItem"])


def test_dynamodb_access_requires_matching_tags():
    template = synthesize(_access_payload({"id": "invoices", "type": "dynamodb.table"}, "read"))
    table = ResourceNaming("invoices").table_arn()
    statement = _statement_for(template, [table, {"Fn::Sub": table["Fn::Sub"] + "/index/*"}])
    assert statement["Condition"] == {"StringEquals": {
        "aws:ResourceTag/org:project": "${aws:PrincipalTag/org:project}",
        "aws:ResourceTag/org:environment": "${aws:PrincipalTag/org:environment}"}}


def test_dynamodb_table_name_variable():
    template = synthesize(_access_payload({"id": "invoices", "type": "dynamodb.table"}, "read"))
    assert properties(template, "ProcessorFunction")["Environment"]["Variables"]["INVOICES_TABLE_NAME"] == {
        "Fn::Sub": "${ProjectName}--invoices"}


def test_sqs_write_actions():
    template = synthesize(_access_payload({"id": "jobs", "type": "sqs.queue"}, "write"))
    assert _statement_for(template, ResourceNaming("jobs").queue_arn())["Action"] == [
        "sqs:SendMessage", "sqs:GetQueueAttributes"]


def test_sqs_read_actions():
    template = synthesize(_access_payload({"id": "jobs", "type": "sqs.queue"}, "read"))
    assert _statement_for(template, ResourceNaming("jobs").queue_arn())["Action"] == [
        "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes"]


def test_sqs_readwrite_actions_are_unique():
    template = synthesize(_access_payload({"id": "jobs", "type": "sqs.queue"}, "readwrite"))
    actions = _statement_for(template, ResourceNaming("jobs").queue_arn())["Action"]
    assert len(actions) == len(set(actions)) == 5


def test_sqs_queue_url_variable():
    template = synthesize(_access_payload({"id": "jobs", "type": "sqs.queue"}, "write"))
    assert properties(template, "ProcessorFunction")["Environment"]["Variables"]["JOBS_QUEUE_URL"] == \
        ResourceNaming("jobs").queue_url()


# ---- DynamoDB table ----

def _table_payload(config: dict | None = None, **overrides) -> dict:
    table = {"id": "invoices", "type": "dynamodb.table", "config": config or {}}
    return request_dict(resources=[table], connections=[], **overrides)


def test_single_region_table():
    table = resource(synthesize(_table_payload()), "InvoicesTable")
    assert (table["Type"], table["Properties"]["BillingMode"], table["DeletionPolicy"]) == (
        "AWS::DynamoDB::Table", "PAY_PER_REQUEST", "RetainExceptOnCreate")


def test_table_default_key():
    assert properties(synthesize(_table_payload()), "InvoicesTable")["KeySchema"] == [
        {"AttributeName": "pk", "KeyType": "HASH"}]


def test_table_with_sort_key():
    table = properties(synthesize(_table_payload({"partition_key": "tenant", "sort_key": "id"})), "InvoicesTable")
    assert (table["KeySchema"], table["AttributeDefinitions"]) == (
        [{"AttributeName": "tenant", "KeyType": "HASH"}, {"AttributeName": "id", "KeyType": "RANGE"}],
        [{"AttributeName": "tenant", "AttributeType": "S"}, {"AttributeName": "id", "AttributeType": "S"}])


def test_table_point_in_time_recovery_and_encryption():
    table = properties(synthesize(_table_payload()), "InvoicesTable")
    assert (table["PointInTimeRecoverySpecification"], table["SSESpecification"]) == (
        {"PointInTimeRecoveryEnabled": True}, {"SSEEnabled": True})


def test_table_resource_policy_denies_other_projects():
    policy = properties(synthesize(_table_payload()), "InvoicesTable")["ResourcePolicy"]["PolicyDocument"]
    assert statements_by_sid(policy)["DenyOtherProjects"]["Condition"]["StringNotEquals"] == SAME_TAG_PROJECT


def test_dr_project_uses_global_table_in_primary_region():
    table = resource(synthesize(dr_request_dict(resources=[{"id": "invoices", "type": "dynamodb.table"}],
                                                connections=[])), "InvoicesTable")
    regions = [replica["Region"] for replica in table["Properties"]["Replicas"]]
    assert (table["Type"], table["Condition"], regions) == ("AWS::DynamoDB::GlobalTable", "IsPrimary",
                                                            ["us-east-1", "us-east-2"])


def test_global_table_replicas_carry_same_tag_policy():
    table = properties(synthesize(dr_request_dict(resources=[{"id": "invoices", "type": "dynamodb.table"}],
                                                  connections=[])), "InvoicesTable")
    policies = [statements_by_sid(replica["ResourcePolicy"]["PolicyDocument"]) for replica in table["Replicas"]]
    assert all("DenyOtherEnvironments" in policy for policy in policies)


def test_table_output():
    assert synthesize(_table_payload())["Outputs"]["InvoicesTableName"] == {
        "Value": {"Fn::Sub": "${ProjectName}--invoices"}}


# ---- SQS queue ----

def _queue_template() -> dict:
    return synthesize(request_dict(resources=[{"id": "jobs", "type": "sqs.queue"}], connections=[]))


def test_queue_properties():
    queue = properties(_queue_template(), "JobsQueue")
    assert (queue["QueueName"], queue["SqsManagedSseEnabled"]) == ({"Fn::Sub": "${ProjectName}--jobs"}, True)


def test_queue_policy_targets_queue():
    assert properties(_queue_template(), "JobsQueuePolicy")["Queues"] == [{"Ref": "JobsQueue"}]


def test_queue_policy_denies_other_environments():
    policy = properties(_queue_template(), "JobsQueuePolicy")["PolicyDocument"]
    assert statements_by_sid(policy)["DenyOtherEnvironments"]["Condition"]["StringNotEquals"] == \
        SAME_TAG_ENVIRONMENT


def test_queue_output():
    assert _queue_template()["Outputs"]["JobsQueueUrl"] == {"Value": {"Ref": "JobsQueue"}}


# ---- contract ----

def test_contract_parameter_name():
    assert properties(synthesize(request_dict()), "ContractParameter")["Name"] == {
        "Fn::Sub": "/platform/projects/${ProjectName}/contract"}


def test_contract_lists_resources():
    contract = json.loads(properties(synthesize(request_dict()), "ContractParameter")["Value"]["Fn::Sub"])
    assert set(contract["resources"]) == {"uploads", "processor"}


def test_contract_publishes_resilience_mode():
    contract = json.loads(properties(synthesize(request_dict()), "ContractParameter")["Value"]["Fn::Sub"])
    assert contract["resilienceMode"] == "${ResilienceMode}"
