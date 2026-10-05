from app.providers.aws.project.naming import ResourceNaming


def test_logical_id_is_pascal_case_with_suffix():
    assert ResourceNaming("my-func-2").logical_id("Function") == "MyFunc2Function"


def test_physical_name_uses_project_parameter():
    assert ResourceNaming("processor").physical_name() == "${ProjectName}--processor"


def test_bucket_name_includes_account_and_region():
    assert ResourceNaming("uploads").bucket_name() == "${ProjectName}--uploads-${AWS::AccountId}-${AWS::Region}"


def test_bucket_arn_is_built_without_references():
    assert ResourceNaming("uploads").bucket_arn() == {
        "Fn::Sub": "arn:${AWS::Partition}:s3:::${ProjectName}--uploads-${AWS::AccountId}-${AWS::Region}"}


def test_bucket_arn_with_object_suffix():
    assert ResourceNaming("uploads").bucket_arn("/incoming/*")["Fn::Sub"].endswith("${AWS::Region}/incoming/*")


def test_table_arn():
    assert ResourceNaming("invoices").table_arn() == {
        "Fn::Sub": "arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}--invoices"}


def test_queue_arn():
    assert ResourceNaming("jobs").queue_arn() == {
        "Fn::Sub": "arn:${AWS::Partition}:sqs:${AWS::Region}:${AWS::AccountId}:${ProjectName}--jobs"}


def test_queue_url():
    assert ResourceNaming("jobs").queue_url() == {
        "Fn::Sub": "https://sqs.${AWS::Region}.amazonaws.com/${AWS::AccountId}/${ProjectName}--jobs"}


def test_environment_variable_name():
    assert ResourceNaming("my-queue").environment_variable("QUEUE_URL") == "MY_QUEUE_QUEUE_URL"
