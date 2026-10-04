from app.synth.blocks.base import Block, InvocableFunction, RuntimePrincipal
from app.synth.policies import POLICY_VERSION
from app.synth.template import Template

DEFAULT_RUNTIME = "python3.13"
DEFAULT_HANDLER = "lambda_function.lambda_handler"
DEFAULT_MEMORY_MB = 256
DEFAULT_TIMEOUT_SEC = 30
LOG_RETENTION_DAYS = 30
ARCHITECTURE = "arm64"
PERMISSIONS_BOUNDARY = {"Fn::Sub": "arn:${AWS::Partition}:iam::${AWS::AccountId}:policy/cloudinfra-app-boundary"}


class LambdaFunctionBlock(Block, RuntimePrincipal, InvocableFunction):
    type_name = "lambda.function"
    display_name = "Lambda function"
    category = "Compute"
    multi_region = "replicated"
    logical_id_suffix = "Function"
    cloudformation_types = ("AWS::Lambda::Function",)

    def __init__(self, spec, request):
        super().__init__(spec, request)
        self._statements: list[dict] = []
        self._environment: dict = {}

    @property
    def role_id(self) -> str:
        return self.naming.logical_id("Role")

    @property
    def log_group_id(self) -> str:
        return self.naming.logical_id("LogGroup")

    def grant(self, statement: dict) -> None:
        if statement not in self._statements:
            self._statements.append(statement)

    def bind_environment(self, name: str, value: object) -> None:
        self._environment[name] = value

    def arn(self) -> dict:
        return {"Fn::GetAtt": [self.logical_id, "Arn"]}

    def required_parameters(self) -> dict:
        return {"CodeS3Bucket": {"Type": "String", "Description": "Bucket holding the function package"},
                "CodeS3Key": {"Type": "String", "Description": "Key of the function package"}}

    def contract_entry(self) -> dict:
        return {"functionName": self.naming.physical_name()}

    def emit(self, template: Template) -> None:
        template.add_resource(self.log_group_id, self._log_group())
        template.add_resource(self.role_id, self._role())
        template.add_resource(self.logical_id, self._function())
        template.add_output(f"{self.logical_id}Arn", {"Value": self.arn()})

    def _setting(self, key: str, default):
        return self.spec.config.get(key, default)

    def _log_group(self) -> dict:
        return {"Type": "AWS::Logs::LogGroup", "Properties": {
            "LogGroupName": {"Fn::Sub": f"/aws/lambda/{self.naming.physical_name()}"},
            "RetentionInDays": LOG_RETENTION_DAYS}}

    def _role(self) -> dict:
        logs = {"Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": {"Fn::GetAtt": [self.log_group_id, "Arn"]}}
        trust = {"Version": POLICY_VERSION, "Statement": [{
            "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
        return {"Type": "AWS::IAM::Role", "Properties": {
            "AssumeRolePolicyDocument": trust,
            "Path": {"Fn::Sub": "/app/${ProjectName}/"},
            "PermissionsBoundary": PERMISSIONS_BOUNDARY,
            "Policies": [{"PolicyName": "least-privilege",
                          "PolicyDocument": {"Version": POLICY_VERSION, "Statement": [logs, *self._statements]}}]}}

    def _function(self) -> dict:
        properties = {
            "FunctionName": {"Fn::Sub": self.naming.physical_name()},
            "Runtime": self._setting("runtime", DEFAULT_RUNTIME),
            "Handler": self._setting("handler", DEFAULT_HANDLER),
            "Code": {"S3Bucket": {"Ref": "CodeS3Bucket"}, "S3Key": {"Ref": "CodeS3Key"}},
            "Role": {"Fn::GetAtt": [self.role_id, "Arn"]},
            "MemorySize": self._setting("memory_mb", DEFAULT_MEMORY_MB),
            "Timeout": self._setting("timeout_sec", DEFAULT_TIMEOUT_SEC),
            "Architectures": [ARCHITECTURE],
            "LoggingConfig": {"LogGroup": {"Ref": self.log_group_id}, "LogFormat": "JSON"},
            "ReservedConcurrentExecutions": {"Fn::If": ["IsActive", {"Ref": "AWS::NoValue"}, 0]},
        }
        properties.update({"Environment": {"Variables": dict(self._environment)}} if self._environment else {})
        return {"Type": "AWS::Lambda::Function", "Properties": properties}
