from app.providers.gcp.project.capabilities import GcpBlock, GrantTarget
from app.synth.access import READ_LEVELS, WRITE_LEVELS

RETENTION = "604800s"  # 7 days
MAX_DELIVERY_ATTEMPTS = 5
ACK_DEADLINE_SECONDS = 60
PUBSUB_AGENT = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"


class PubSubQueueBlock(GcpBlock, GrantTarget):
    """A topic with one pull subscription and a dead-letter topic: the closest match to a queue."""

    type_name = "messaging.queue"
    display_name = "Pub/Sub queue"
    category = "Integration"
    multi_region = "global"
    provider_types = ("google_pubsub_topic", "google_pubsub_subscription")

    @property
    def _dead(self) -> str:
        return f"{self.spec.id}-dead"

    def emit(self, document):
        name = self.naming.physical_name()
        document.add_resource("google_pubsub_topic", self.spec.id, self.primary_only({"name": name}))
        document.add_resource("google_pubsub_topic", self._dead, self.primary_only({"name": f"{name}-dead"}))
        document.add_resource("google_pubsub_subscription", self.spec.id, self.primary_only({
            "name": name, "topic": self.reference("google_pubsub_topic", self.spec.id, "id"),
            "ack_deadline_seconds": ACK_DEADLINE_SECONDS, "message_retention_duration": RETENTION,
            "enable_exactly_once_delivery": True,
            "dead_letter_policy": {"dead_letter_topic": self.reference("google_pubsub_topic", self._dead, "id"),
                                   "max_delivery_attempts": MAX_DELIVERY_ATTEMPTS}}))
        self._let_pubsub_dead_letter(document)
        document.add_output(f"{self.spec.id}_topic", {"value": name})

    def _let_pubsub_dead_letter(self, document) -> None:
        """Pub/Sub's service agent moves undeliverable messages, so it needs both ends of the dead-letter path."""
        document.add_data("google_project", "this", {"project_id": "${var.project_id}"})
        document.add_resource("google_pubsub_topic_iam_member", f"{self._dead}-agent", self.primary_only({
            "topic": self.reference("google_pubsub_topic", self._dead, "name"), "role": "roles/pubsub.publisher",
            "member": PUBSUB_AGENT}))
        document.add_resource("google_pubsub_subscription_iam_member", f"{self.spec.id}-agent", self.primary_only({
            "subscription": self.reference("google_pubsub_subscription", self.spec.id, "name"),
            "role": "roles/pubsub.subscriber", "member": PUBSUB_AGENT}))

    def grants(self, access, prefix, member, source_id):
        found = []
        if access in WRITE_LEVELS:
            found.append(("google_pubsub_topic_iam_member", f"{source_id}-{self.spec.id}-publish", self.primary_only(
                {"topic": self.naming.physical_name(), "role": "roles/pubsub.publisher", "member": member})))
        if access in READ_LEVELS:
            found.append(("google_pubsub_subscription_iam_member", f"{source_id}-{self.spec.id}-subscribe",
                          self.primary_only({"subscription": self.naming.physical_name(),
                                             "role": "roles/pubsub.subscriber", "member": member})))
        return found

    def environment(self):
        name = self.naming.physical_name()
        return {self.naming.environment_variable("TOPIC"): name, self.naming.environment_variable("SUBSCRIPTION"): name}

    def contract_entry(self):
        return {"topic": self.naming.physical_name()}
