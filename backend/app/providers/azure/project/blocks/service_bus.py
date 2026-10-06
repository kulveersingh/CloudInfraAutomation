from app.providers.azure.project.blocks.storage_account import add_private_endpoint
from app.providers.azure.project.capabilities import (
    LOCATION,
    AzureBlock,
    GrantTarget,
    identity_id,
    principal_of,
    resource_id,
    role_assignment,
)
from app.providers.azure.project.naming import bare, variable
from app.synth.access import READ_LEVELS, WRITE_LEVELS

API = "2024-01-01"
NAMESPACE = "Microsoft.ServiceBus/namespaces"
SENDER = "69a216fc-b8fb-44d8-bc22-1f3c2cd27a39"  # Azure Service Bus Data Sender
RECEIVER = "4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0"  # Azure Service Bus Data Receiver
MAX_DELIVERY_COUNT = 5


class ServiceBusQueueBlock(AzureBlock, GrantTarget):
    """A Service Bus namespace and queue with its built-in dead-letter queue: Standard, Premium in DR/HA (A3). In the
    shared stack, so removing it deletes it, as queues are on other clouds."""

    type_name = "messaging.queue"
    display_name = "Service Bus queue"
    category = "Integration"
    multi_region = "global"
    provider_types = (NAMESPACE,)

    @property
    def _name(self) -> str:
        return variable(self.naming.variable)

    @property
    def _id(self) -> str:
        return resource_id(NAMESPACE, f"variables('{self.naming.variable}')")

    def emit(self, documents):
        self.declare(documents, self.naming.variable, self.naming.service_bus())
        shared, item = documents.shared, self.spec.id
        tier = "Premium" if self.spans_regions else "Standard"
        shared.add_resource({"type": NAMESPACE, "apiVersion": API, "comments": item, "name": self._name,
                           "location": LOCATION, "sku": {"name": tier, "tier": tier},
                           "properties": {"disableLocalAuth": True, "minimumTlsVersion": "1.2",
                                          "publicNetworkAccess": "Disabled" if self.attached and self.spans_regions
                                          else "Enabled"}})
        shared.add_resource({"type": f"{NAMESPACE}/queues", "apiVersion": API, "comments": item,
                           "name": f"[format('{{0}}/{item}', {bare(self._name)})]", "dependsOn": [f"[{self._id}]"],
                           "properties": {"maxDeliveryCount": MAX_DELIVERY_COUNT, "deadLetteringOnMessageExpiration": True,
                                          "lockDuration": "PT1M"}})
        if self.attached and self.spans_regions:  # private endpoints need Premium
            add_private_endpoint(shared, item, f"[{self._id}]", "namespace", same_stack=True)

    def grants(self, access, prefix, identity, comment):
        scope = f"[format('Microsoft.ServiceBus/namespaces/{{0}}/queues/{self.spec.id}', {bare(self._name)})]"
        depends = [f"[{identity_id(identity)}]",
                   f"[resourceId('{NAMESPACE}/queues', {bare(self._name)}, '{self.spec.id}')]"]
        roles = [*([SENDER] if access in WRITE_LEVELS else []), *([RECEIVER] if access in READ_LEVELS else [])]
        return [role_assignment(scope, role, principal_of(identity), comment, depends) for role in roles]

    def environment(self):
        return {self.naming.environment_variable("NAMESPACE"): self._name,
                self.naming.environment_variable("QUEUE"): self.spec.id}

    def contract_entry(self):
        return {"namespace": self._name, "queue": self.spec.id}
