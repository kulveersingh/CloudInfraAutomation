POLICY_VERSION = "2012-10-17"
SERVICE_LINKED_ROLES = {"Fn::Sub": "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/aws-service-role/*"}


class SameTagPolicy:
    """Resource-policy statements that deny every caller whose project or environment tag differs."""

    def __init__(self, action: str, resources: list):
        self._action = action
        self._resources = resources

    def document(self, extra_statements: tuple = ()) -> dict:
        return {"Version": POLICY_VERSION, "Statement": [*self.statements(), *extra_statements]}

    def statements(self) -> list[dict]:
        return [self._deny("DenyOtherProjects", "org:project", "ProjectName"),
                self._deny("DenyOtherEnvironments", "org:environment", "EnvironmentName")]

    def _deny(self, sid: str, tag_key: str, parameter: str) -> dict:
        return {
            "Sid": sid,
            "Effect": "Deny",
            "Principal": "*",
            "Action": self._action,
            "Resource": self._resources,
            "Condition": {
                "StringNotEquals": {f"aws:PrincipalTag/{tag_key}": {"Ref": parameter}},
                "BoolIfExists": {"aws:PrincipalIsAWSService": "false"},
                "ArnNotLike": {"aws:PrincipalArn": [SERVICE_LINKED_ROLES]},
            },
        }


class InsecureTransportDenial:
    """Statement that rejects requests not using TLS."""

    def __init__(self, action: str, resources: list):
        self._action = action
        self._resources = resources

    def statement(self) -> dict:
        return {"Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": self._action,
                "Resource": self._resources, "Condition": {"Bool": {"aws:SecureTransport": "false"}}}
