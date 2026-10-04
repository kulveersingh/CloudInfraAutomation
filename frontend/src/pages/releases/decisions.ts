import type { Identity, PlatformApiPort, Release } from "../../api/types";

const SELF_DECISION = "You requested this release, so you cannot decide on it.";

export interface DecisionRequirement {
  role: string;
  message: string;
  approveLabel: string;
  approve: (api: PlatformApiPort, releaseId: string, comment: string) => Promise<Release>;
}

/** Which decision a pending release needs, mirroring the server's approval policy for clear UI hints. */
export const DECISIONS: Record<string, DecisionRequirement> = {
  awaiting_approval: {
    role: "reviewer",
    message: "Only reviewers can approve or reject releases.",
    approveLabel: "Approve and release",
    approve: (api, releaseId, comment) => api.approveRelease(releaseId, comment),
  },
  override_requested: {
    role: "platform-admin",
    message: "Only a platform admin can approve an override.",
    approveLabel: "Approve override",
    approve: (api, releaseId, comment) => api.approveOverride(releaseId, comment),
  },
};

export function decisionProblem(identity: Identity, release: Release, requirement: DecisionRequirement): string | undefined {
  if (!identity.roles.includes(requirement.role)) return requirement.message;
  if (identity.name === release.requested_by) return SELF_DECISION;
  return undefined;
}

export const STATE_LABELS: Record<string, string> = {
  planned: "Planned",
  gate_failed: "Gate failed",
  override_requested: "Override needed",
  awaiting_approval: "Awaiting approval",
  deploying: "Deploying",
  deployed: "Deployed",
  rolled_back: "Rolled back",
  rejected: "Rejected",
  superseded: "Superseded",
};

export function describeEvidence(release: Release): string {
  const { tests_passed, signed, critical_vulnerabilities, high_vulnerabilities } = release.evidence;
  return [
    tests_passed ? "Tests passed" : "Tests failed",
    signed ? "signed" : "unsigned",
    `${critical_vulnerabilities} critical / ${high_vulnerabilities} high vulnerabilities`,
  ].join(" · ");
}
