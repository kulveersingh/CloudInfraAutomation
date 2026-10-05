from app.providers.gcp.project.capabilities import GcpBlock, Workload
from app.synth.blocks.settings import ChoiceSetting, IntegerSetting, TextSetting

RUNTIMES = ("python313", "python312", "nodejs22", "nodejs20", "java21", "go125")
EVENT_RECEIVER = "roles/eventarc.eventReceiver"
STRING = {"type": "string"}


class CloudRunFunctionBlock(GcpBlock, Workload):
    type_name = "compute.function"
    display_name = "Cloud Run function"
    category = "Compute"
    multi_region = "replicated"
    provider_types = ("google_cloudfunctions2_function",)
    settings = (
        ChoiceSetting("runtime", "Runtime", "python313", RUNTIMES),
        TextSetting("entry_point", "Entry point", "main", r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$",
                    "1 to 128 letters, digits, _ and ., starting with a letter or _"),
        IntegerSetting("memory_mb", "Memory", 256, 128, 32768, "MiB"),
        IntegerSetting("timeout_sec", "Timeout", 60, 1, 540, "seconds"),  # 540 s is the limit for event triggers
    )

    def __init__(self, spec, request):
        super().__init__(spec, request)
        self._environment: dict[str, str] = {}
        self._trigger: dict | None = None

    @property
    def uses_network(self):
        return self.request.network.attach_compute

    def required_variables(self):
        return {"code_bucket": STRING, "code_object": STRING}

    def member(self):
        return self.naming.member()

    def add_environment(self, variables):
        self._environment.update(variables)

    def add_trigger(self, trigger):
        self._trigger = {**trigger, "service_account_email": self.naming.service_account_email(),
                         "retry_policy": "RETRY_POLICY_RETRY"}

    def contract_entry(self):
        return {"functionName": self.naming.physical_name()}

    def emit(self, document):
        document.add_resource("google_service_account", self.spec.id, self.primary_only(
            {"account_id": self.naming.service_account_id(), "display_name": f"{self.naming.physical_name()} function"}))
        document.add_resource("google_cloudfunctions2_function", self.spec.id, self._function())
        if self._trigger is not None:
            self._allow_events(document)
        document.add_output(f"{self.spec.id}_name", {"value": self.naming.physical_name()})

    def _function(self) -> dict:
        service = {"available_memory": f"{self.setting('memory_mb')}M", "timeout_seconds": self.setting("timeout_sec"),
                   "service_account_email": self.naming.service_account_email(),
                   "ingress_settings": "ALLOW_INTERNAL_ONLY", "all_traffic_on_latest_revision": True}
        service.update({"environment_variables": dict(sorted(self._environment.items()))} if self._environment else {})
        if self.uses_network:
            service["direct_vpc_network_interface"] = {"network": "${var.network}", "subnetwork": "${var.subnetwork}",
                                                       "tags": "${var.network_tags}"}
            service["direct_vpc_egress"] = "VPC_EGRESS_PRIVATE_RANGES_ONLY"
        function = {"name": self.naming.physical_name(), "location": "${var.region}",
                    "build_config": {"runtime": self.setting("runtime"), "entry_point": self.setting("entry_point"),
                                     "source": {"storage_source": {"bucket": "${var.code_bucket}",
                                                                   "object": "${var.code_object}"}}},
                    "service_config": service}
        if self._trigger is not None:  # a standby region keeps the function but takes no events
            function["dynamic"] = {"event_trigger": {"for_each": "${local.is_active ? [1] : []}",
                                                     "content": self._trigger}}
        return function

    def _allow_events(self, document) -> None:
        document.add_resource("google_project_iam_member", f"{self.spec.id}-event-receiver", self.primary_only(
            {"project": "${var.project_id}", "role": EVENT_RECEIVER, "member": self.member()}))
        document.add_resource("google_cloud_run_service_iam_member", f"{self.spec.id}-invoker", {
            "location": "${var.region}", "role": "roles/run.invoker", "member": self.member(),
            "service": f"${{google_cloudfunctions2_function.{self.spec.id}.service_config[0].service}}"})
