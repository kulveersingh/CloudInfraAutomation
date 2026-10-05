from app.synth.blocks.base import Block, InvocableFunction, RuntimePrincipal
from app.synth.blocks.settings import ChoiceSetting, IntegerSetting, TextSetting
from app.synth.policies import POLICY_VERSION
from app.synth.template import Template

DEFAULT_RUNTIME = "python3.13"
DEFAULT_HANDLER = "lambda_function.lambda_handler"
DEFAULT_MEMORY_MB = 256
DEFAULT_TIMEOUT_SEC = 30
# Runtimes Lambda supports on arm64; provided.al2023 runs compiled languages such as Go and Rust.
RUNTIMES = ("python3.13", "python3.12", "nodejs22.x", "nodejs20.x", "java21", "provided.al2023")
LOG_RETENTION_DAYS = 30
ARCHITECTURE = "arm64"
VPC_ACCESS_POLICY = {"Fn::Sub": "arn:${AWS::Partition}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"}
ANYWHERE = "0.0.0.0/0"
HTTPS_PORT = 443
PERMISSIONS_BOUNDARY = {"Fn::Sub": "arn:${AWS::Partition}:iam::${AWS::AccountId}:policy/cloudinfra-app-boundary"}


class LambdaFunctionBlock(Block, RuntimePrincipal, InvocableFunction):
    type_name = "lambda.function"
    display_name = "Lambda function"
    category = "Compute"
    multi_region = "replicated"
    logical_id_suffix = "Function"
    cloudformation_types = ("AWS::Lambda::Function",)
    settings = (
        ChoiceSetting("runtime", "Runtime", DEFAULT_RUNTIME, RUNTIMES),
        TextSetting("handler", "Handler", DEFAULT_HANDLER, r"^[A-Za-z0-9_.:/$-]{1,128}$",
                    "1 to 128 characters of letters, digits and _ . : / $ -"),
        IntegerSetting("memory_mb", "Memory", DEFAULT_MEMORY_MB, 128, 10240, "MB"),
        IntegerSetting("timeout_sec", "Timeout", DEFAULT_TIMEOUT_SEC, 1, 900, "seconds"),
    )

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

    @property
    def security_group_id(self) -> str:
        return self.naming.logical_id("SecurityGroup")

    @property
    def uses_network(self) -> bool:
        return self.request.network.attach_compute

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
        if self.uses_network:
            template.add_resource(self.security_group_id, self._security_group())
        template.add_resource(self.role_id, self._role())
        template.add_resource(self.logical_id, self._function())
        template.add_output(f"{self.logical_id}Arn", {"Value": self.arn()})

    def _log_group(self) -> dict:
        return {"Type": "AWS::Logs::LogGroup", "Properties": {
            "LogGroupName": {"Fn::Sub": f"/aws/lambda/{self.naming.physical_name()}"},
            "RetentionInDays": LOG_RETENTION_DAYS}}

    def _role(self) -> dict:
        logs = {"Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": {"Fn::GetAtt": [self.log_group_id, "Arn"]}}
        trust = {"Version": POLICY_VERSION, "Statement": [{
            "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
        properties = {
            "AssumeRolePolicyDocument": trust,
            "Path": {"Fn::Sub": "/app/${ProjectName}/"},
            "PermissionsBoundary": PERMISSIONS_BOUNDARY,
            "Policies": [{"PolicyName": "least-privilege",
                          "PolicyDocument": {"Version": POLICY_VERSION, "Statement": [logs, *self._statements]}}]}
        properties.update({"ManagedPolicyArns": [VPC_ACCESS_POLICY]} if self.uses_network else {})
        return {"Type": "AWS::IAM::Role", "Properties": properties}

    def _security_group(self) -> dict:
        return {"Type": "AWS::EC2::SecurityGroup", "Properties": {
            "GroupDescription": {"Fn::Sub": f"{self.naming.physical_name()} function"},
            "VpcId": {"Ref": "VpcId"},
            "SecurityGroupEgress": [
                {"IpProtocol": "-1", "CidrIp": {"Ref": "OrgPrivateCidr"},
                 "Description": "Organization private network"},
                {"IpProtocol": "tcp", "FromPort": HTTPS_PORT, "ToPort": HTTPS_PORT, "CidrIp": ANYWHERE,
                 "Description": "HTTPS to AWS service endpoints"}]}}

    def _vpc_config(self) -> dict:
        own_and_org_groups = {"Fn::Join": [",", [{"Ref": self.security_group_id},
                                                 {"Fn::Join": [",", {"Ref": "OrgSecurityGroupIds"}]}]]}
        return {"VpcConfig": {"SubnetIds": {"Ref": "PrivateSubnetIds"},
                              "SecurityGroupIds": {"Fn::Split": [",", own_and_org_groups]}}}

    def _function(self) -> dict:
        properties = {
            "FunctionName": {"Fn::Sub": self.naming.physical_name()},
            "Runtime": self.setting("runtime"),
            "Handler": self.setting("handler"),
            "Code": {"S3Bucket": {"Ref": "CodeS3Bucket"}, "S3Key": {"Ref": "CodeS3Key"}},
            "Role": {"Fn::GetAtt": [self.role_id, "Arn"]},
            "MemorySize": self.setting("memory_mb"),
            "Timeout": self.setting("timeout_sec"),
            "Architectures": [ARCHITECTURE],
            "LoggingConfig": {"LogGroup": {"Ref": self.log_group_id}, "LogFormat": "JSON"},
            "ReservedConcurrentExecutions": {"Fn::If": ["IsActive", {"Ref": "AWS::NoValue"}, 0]},
        }
        properties.update({"Environment": {"Variables": dict(self._environment)}} if self._environment else {})
        properties.update(self._vpc_config() if self.uses_network else {})
        return {"Type": "AWS::Lambda::Function", "Properties": properties}
