import hashlib


def short_hash(text: str, length: int = 8) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:length]


class GcpNaming:
    """Names of a service's Google Cloud resources. Projects are per environment, so names repeat across them;
    bucket names are global, so they add a hash of the environment's project id."""

    def __init__(self, project_name: str, resource_id: str):
        self._project = project_name
        self.resource_id = resource_id

    def bucket_name(self) -> str:
        return f"${{var.project_name}}-{self.resource_id}-${{substr(sha1(var.project_id), 0, 8)}}"

    def physical_name(self) -> str:
        return f"{self._project}--{self.resource_id}"

    def database_id(self) -> str:
        return f"{self._project}-{self.resource_id}"

    def service_account_id(self) -> str:
        return f"{self.resource_id}-{short_hash(self._project)}"

    def service_account_email(self) -> str:
        return f"{self.service_account_id()}@${{var.project_id}}.iam.gserviceaccount.com"

    def member(self) -> str:
        return f"serviceAccount:{self.service_account_email()}"

    def environment_variable(self, suffix: str) -> str:
        return f"{self.resource_id.upper().replace('-', '_')}_{suffix}"
