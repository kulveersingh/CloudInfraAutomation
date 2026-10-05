from app.providers.aws.project.access import SAME_TAG_RESOURCE_CONDITION, AccessActions
from app.providers.aws.project.capabilities import AccessTarget, AwsBlock
from app.providers.aws.project.policies import SameTagPolicy
from app.providers.aws.project.template import Template


class SqsQueueBlock(AwsBlock, AccessTarget):
    type_name = "messaging.queue"
    aliases = ("sqs.queue",)
    display_name = "SQS queue"
    category = "Integration"
    multi_region = "regional"
    logical_id_suffix = "Queue"
    provider_types = ("AWS::SQS::Queue",)

    ACTIONS = AccessActions(
        read=["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes"],
        write=["sqs:SendMessage", "sqs:GetQueueAttributes"])

    def access_statements(self, access: str, prefix: str) -> list[dict]:
        return [{"Effect": "Allow", "Action": self.ACTIONS.for_level(access), "Resource": self.naming.queue_arn(),
                 "Condition": SAME_TAG_RESOURCE_CONDITION}]

    def environment_binding(self) -> tuple[str, object]:
        return self.naming.environment_variable("QUEUE_URL"), self.naming.queue_url()

    def contract_entry(self) -> dict:
        return {"queueUrl": self.naming.queue_url()["Fn::Sub"]}

    def emit(self, template: Template) -> None:
        template.add_resource(self.logical_id, {"Type": "AWS::SQS::Queue", "Properties": {
            "QueueName": {"Fn::Sub": self.naming.physical_name()}, "SqsManagedSseEnabled": True}})
        template.add_resource(f"{self.logical_id}Policy", {"Type": "AWS::SQS::QueuePolicy", "Properties": {
            "Queues": [{"Ref": self.logical_id}],
            "PolicyDocument": SameTagPolicy("sqs:*", [self.naming.queue_arn()]).document()}})
        template.add_output(f"{self.logical_id}Url", {"Value": {"Ref": self.logical_id}})
