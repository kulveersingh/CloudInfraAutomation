from app.registry.cost_centers import CostCenter
from app.synth.request import ProjectRequest

MANAGED_BY = "cloudinfra"


class TagSet:
    """The ownership tags every resource and role of a project carries."""

    def __init__(self, request: ProjectRequest, cost_center: CostCenter):
        self._request = request
        self._cost_center = cost_center

    def as_dict(self) -> dict[str, str]:
        ownership = self._request.ownership
        return {"org:portfolio": ownership.portfolio_id, "org:product": ownership.product_id,
                "org:project": self._request.project_name, "org:cost-center": self._cost_center.value,
                "org:data-classification": ownership.data_classification,
                "org:resilience": self._request.resilience.mode, "org:managed-by": MANAGED_BY}
