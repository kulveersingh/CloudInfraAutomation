PROJECT_REFERENCE = "${ProjectName}"
CURRENT_REGION = "${AWS::Region}"


class ResourceNaming:
    """Predictable names and ARNs for one resource, built without Ref/GetAtt so they never create cycles."""

    def __init__(self, resource_id: str):
        self._resource_id = resource_id

    def logical_id(self, suffix: str) -> str:
        return "".join(part.capitalize() for part in self._resource_id.split("-")) + suffix

    def physical_name(self) -> str:
        return f"{PROJECT_REFERENCE}--{self._resource_id}"

    def bucket_name(self) -> str:
        return f"{self.physical_name()}-${{AWS::AccountId}}-{CURRENT_REGION}"

    def bucket_arn(self, suffix: str = "") -> dict:
        return {"Fn::Sub": f"arn:${{AWS::Partition}}:s3:::{self.bucket_name()}{suffix}"}

    def table_arn(self, region: str = CURRENT_REGION) -> dict:
        return {"Fn::Sub": f"arn:${{AWS::Partition}}:dynamodb:{region}:${{AWS::AccountId}}:table/"
                           f"{self.physical_name()}"}

    def queue_arn(self) -> dict:
        return {"Fn::Sub": f"arn:${{AWS::Partition}}:sqs:{CURRENT_REGION}:${{AWS::AccountId}}:{self.physical_name()}"}

    def queue_url(self) -> dict:
        return {"Fn::Sub": f"https://sqs.{CURRENT_REGION}.amazonaws.com/${{AWS::AccountId}}/{self.physical_name()}"}

    def environment_variable(self, kind: str) -> str:
        return f"{self._resource_id.replace('-', '_').upper()}_{kind}"
