import type { LandingZoneAnswers } from "../api/types";

/** A shared unit the Infrastructure step offers, by its answer id; clouds that have no such unit leave it out. */
export interface SharedUnit {
  id: string;
  label: string;
  hint: string;
}

/** What the landing-zone questionnaire says and offers on one cloud (§22.10). New clouds add an entry. */
export interface LandingZoneCloudText {
  repository: string;
  regions: string[];
  organizationIntro: string;
  /** What the organization name prefixes. */
  namePrefixHint: string;
  /** How the landing zone creates each environment's isolation units. */
  accountsIntro: string;
  homeRegionHint: string;
  governedRegionsHint: string;
  sharedUnits: SharedUnit[];
  sharedUnitsIntro: string;
  hubTitle: string;
  hubDescription: string;
  isolatedDescription: string;
  egressOptions: Array<{ value: LandingZoneAnswers["network"]["egress"]; label: string }>;
  dedicatedLink: string;
  inspection: string;
  flowsHint: string;
  securityNotice: string;
  securityTooling: string;
  complianceHint: string;
  controlsIntro: string;
  /** What the cloud's controls cannot do for this design. */
  controlNotes: (providerAnswers: Record<string, unknown>) => string[];
  /** Checks of the cloud's own answers the browser can make. */
  answerProblems: (providerAnswers: Record<string, unknown>) => string[];
  /** The cloud's own answers, empty, for a new design. */
  emptyAnswers: Record<string, unknown>;
}

const EMAIL_PATTERN = /^[^@\s+]+@[^@\s]+\.[^@\s]+$/;
const ORGANIZATION_ID_PATTERN = /^[0-9]{1,20}$/;
const BILLING_ACCOUNT_PATTERN = /^[0-9A-Z]{6}-[0-9A-Z]{6}-[0-9A-Z]{6}$/;
const DOMAIN_PATTERN = /^[a-z0-9-]+(\.[a-z0-9-]+)+$/;

const text = (value: unknown) => String(value ?? "");

const AWS: LandingZoneCloudText = {
  repository: "landing-zone-infra",
  regions: [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2", "ca-central-1", "sa-east-1", "eu-west-1", "eu-west-2", "eu-west-3",
    "eu-central-1", "eu-central-2", "eu-north-1", "eu-south-1", "eu-south-2", "ap-south-1", "ap-south-2", "ap-southeast-1",
    "ap-southeast-2", "ap-southeast-3", "ap-southeast-4", "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
    "ap-east-1", "me-south-1", "me-central-1", "af-south-1", "il-central-1",
  ],
  namePrefixHint: "Prefix for account names and OU paths",
  accountsIntro: "Accounts are created through Control Tower Account Factory, already enrolled in their environment OU.",
  organizationIntro: "Creates a new AWS Organization with all features and an AWS Control Tower landing zone in the "
    + "management (payer) account.",
  homeRegionHint: "Where Control Tower runs",
  governedRegionsHint: "All other regions are denied by SCP. Any two governed regions can be a DR/HA pair.",
  sharedUnitsIntro: "These accounts go in the Infrastructure OU. Environment accounts reach them only through the routes "
    + "on the Network step.",
  sharedUnits: [
    { id: "network", label: "Network", hint: "Transit Gateway, IPAM, central egress and inspection" },
    { id: "shared_services", label: "Shared Services", hint: "DNS resolver, artifact buckets, directory, the CloudInfra platform" },
    { id: "identity", label: "Identity", hint: "Directory integration for IAM Identity Center" },
    { id: "backup", label: "Backup", hint: "Central backup vaults with cross-region copy" },
    { id: "monitoring", label: "Monitoring", hint: "Cross-account CloudWatch dashboards and alarms" },
    { id: "cicd", label: "CI/CD Automations", hint: "Only if you run build agents in AWS; GitHub Actions with OIDC doesn't need it" },
  ],
  hubTitle: "Hub and spoke (Transit Gateway)",
  hubDescription: "A central Network account; each environment VPC attaches to the hub.",
  isolatedDescription: "No hub. Environments can't reach Shared Services privately.",
  egressOptions: [{ value: "central", label: "Central egress VPC (recommended)" }, { value: "local", label: "NAT in each VPC" }],
  dedicatedLink: "Direct Connect",
  inspection: "Inspect traffic with AWS Network Firewall",
  flowsHint: "None by default: environments are fully isolated. Each exception is a single port, routed only through the "
    + "inspection VPC, and is approved with the design.",
  securityNotice: "There is always exactly one Security OU, created by Control Tower. It holds the Log Archive and Audit "
    + "accounts; Audit is the delegated administrator for GuardDuty, Security Hub, Inspector and Macie.",
  securityTooling: "Separate account for SIEM forwarding, incident response tools and forensics",
  complianceHint: "Each scope gets its own OU with STAGE and PROD child OUs, stricter controls and its Security Hub standard.",
  controlsIntro: "Control Tower controls come in packs; each pack targets the OUs it fits. A profile picks a set of packs, "
    + "and you can add or remove single packs. Mandatory Control Tower controls are always on.",
  controlNotes: () => [],
  answerProblems: (answers) => (EMAIL_PATTERN.test(text(answers.management_email))
    ? [] : ["Enter the management account email."]),
  emptyAnswers: { management_email: "" },
};

const GCP: LandingZoneCloudText = {
  repository: "landing-zone-gcp-infra",
  regions: [
    "us-east1", "us-east4", "us-east5", "us-central1", "us-south1", "us-west1", "us-west2", "us-west3", "us-west4",
    "northamerica-northeast1", "northamerica-northeast2", "southamerica-east1", "europe-west1", "europe-west2",
    "europe-west3", "europe-west4", "europe-west6", "europe-west8", "europe-west9", "europe-north1", "europe-central2",
    "europe-southwest1", "asia-east1", "asia-east2", "asia-northeast1", "asia-northeast2", "asia-northeast3",
    "asia-south1", "asia-southeast1", "asia-southeast2", "australia-southeast1", "australia-southeast2", "me-west1",
    "me-central1", "africa-south1",
  ],
  namePrefixHint: "Prefix for project ids and folder paths",
  accountsIntro: "Projects are created by the platform's Terraform, already in their environment folder.",
  organizationIntro: "Creates new folders, projects and policies under an existing Google Cloud organization. An "
    + "organization admin runs the generated seed script once; after that every change goes through the platform.",
  homeRegionHint: "Where the Infrastructure Manager deployments run",
  governedRegionsHint: "Data residency packs allow only these regions. Any two governed regions can be a DR/HA pair.",
  sharedUnitsIntro: "These projects go in the Infrastructure folder. Environment projects reach them only through the hub "
    + "on the Network step.",
  sharedUnits: [
    { id: "network", label: "Network hub", hint: "Network Connectivity Center hub, hybrid links and inspection" },
    { id: "shared_services", label: "Shared Services", hint: "DNS, artifact repositories, the CloudInfra platform" },
    { id: "backup", label: "Vault", hint: "Teardown backups: locked buckets and Backup and DR vaults, 60 days" },
    { id: "monitoring", label: "Monitoring", hint: "Cloud Monitoring metrics scope across the projects" },
    { id: "cicd", label: "CI/CD Automations", hint: "Only if you run build agents in Google Cloud; GitHub Actions with "
      + "Workload Identity Federation doesn't need it" },
  ],
  hubTitle: "Hub and spoke (Network Connectivity Center)",
  hubDescription: "A star: the hub is the center, each environment's Shared VPC an edge that reaches only the hub.",
  isolatedDescription: "No hub. Environments can't reach Shared Services privately.",
  egressOptions: [{ value: "local", label: "Cloud NAT in each environment's VPC" }],
  dedicatedLink: "Cloud Interconnect",
  inspection: "Inspect traffic with Cloud NGFW",
  flowsHint: "None by default: environments are fully isolated. Each exception is a Private Service Connect endpoint "
    + "for one service on one port, and is approved with the design.",
  securityNotice: "There is always exactly one Security folder. It holds the logging project, where the organization's "
    + "audit logs are kept in a locked bucket, and the security project; Security Command Center covers the organization.",
  securityTooling: "Separate project for SIEM forwarding, incident response tools and forensics",
  complianceHint: "Each scope gets its own folder with STAGE and PROD child folders, each with its own Shared VPC and "
    + "stricter controls.",
  controlsIntro: "Org Policy constraints, IAM deny policies and Security Command Center detectors come in packs; each "
    + "pack targets the folders it fits and governs everything below them.",
  controlNotes: (answers) => [
    "Google Cloud has no proactive controls: packs list their preventive and detective controls only.",
    ...(answers.scc_tier === "standard" ? ["Detective controls are not deployed: Security Command Center Standard has no "
      + "postures. Choose Premium or Enterprise on the Organization step to deploy them."] : []),
  ],
  answerProblems: (answers) => [
    ...(ORGANIZATION_ID_PATTERN.test(text(answers.organization_id)) ? [] : ["Enter the organization id: digits only."]),
    ...(BILLING_ACCOUNT_PATTERN.test(text(answers.billing_account))
      ? [] : ["Enter the billing account: XXXXXX-XXXXXX-XXXXXX."]),
    ...(DOMAIN_PATTERN.test(text(answers.domain)) ? [] : ["Enter the organization's domain."]),
  ],
  emptyAnswers: { organization_id: "", billing_account: "", domain: "", scc_tier: "premium" },
};

const GUID_PATTERN = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
const BILLING_SCOPE_PATTERN = new RegExp("^/providers/Microsoft\\.Billing/billingAccounts/[^/]+/"
  + "(enrollmentAccounts/[^/]+|billingProfiles/[^/]+/invoiceSections/[^/]+)$");

/** Azure's admin groups (existing Entra groups, by object id) and how the questionnaire names them. */
export const AZURE_GROUPS: Array<[string, string]> = [["platform_admins", "Platform admins"],
  ["network_admins", "Network admins"], ["security_admins", "Security admins"], ["backup_super_users", "Backup super users"]];

const groupOf = (answers: Record<string, unknown>, role: string) =>
  text((answers.groups as Record<string, unknown> | undefined)?.[role]);

const AZURE: LandingZoneCloudText = {
  repository: "landing-zone-azure-infra",
  regions: [
    "eastus", "eastus2", "centralus", "northcentralus", "southcentralus", "westcentralus", "westus", "westus2", "westus3",
    "canadacentral", "canadaeast", "brazilsouth", "northeurope", "westeurope", "uksouth", "ukwest", "francecentral",
    "germanywestcentral", "swedencentral", "switzerlandnorth", "norwayeast", "australiaeast", "australiasoutheast",
    "japaneast", "japanwest", "koreacentral", "southeastasia", "eastasia", "centralindia",
  ],
  namePrefixHint: "Prefix for subscription names and management group ids",
  accountsIntro: "Subscriptions are created against your billing scope by the platform's deployment stacks, already in "
    + "their environment management group.",
  organizationIntro: "Creates management groups, subscriptions and policies under your organization's own management "
    + "group, in an existing Microsoft Entra tenant. A tenant admin runs the generated seed script once; after that every "
    + "change goes through the platform.",
  homeRegionHint: "Where the deployment stacks run from",
  governedRegionsHint: "Data residency packs allow only these regions. Govern regions in pairs: geo-redundant storage "
    + "replicates only to a region's pair.",
  sharedUnitsIntro: "These subscriptions go in the Infrastructure management group. Environment subscriptions reach them "
    + "only through the hubs on the Network step.",
  sharedUnits: [
    { id: "network", label: "Connectivity", hint: "Hubs with Azure Firewall, gateways and private DNS zones" },
    { id: "shared_services", label: "Shared Services", hint: "DNS, artifact registries, the CloudInfra platform" },
    { id: "identity", label: "Identity", hint: "Only for AD DS domain controllers; Entra ID needs none" },
    { id: "backup", label: "Backup", hint: "Teardown backups: locked Backup vaults and export container, 60 days" },
    { id: "monitoring", label: "Monitoring", hint: "Azure Monitor workbooks and alerts across the subscriptions" },
    { id: "cicd", label: "CI/CD Automations", hint: "Only if you run build agents in Azure; GitHub Actions with a "
      + "federated credential doesn't need it" },
  ],
  hubTitle: "Hub and spoke (Azure Firewall)",
  hubDescription: "A hub per region in the Connectivity subscription; each workload subscription's spoke VNet peers only "
    + "with its region's hub.",
  isolatedDescription: "No hub. Environments can't reach Shared Services privately.",
  egressOptions: [{ value: "central", label: "Through the hub's Azure Firewall (recommended)" },
    { value: "local", label: "NAT gateway in each spoke" }],
  dedicatedLink: "ExpressRoute",
  inspection: "Inspect traffic with Azure Firewall (Premium adds IDPS)",
  flowsHint: "None by default: environments are fully isolated. Each exception is a firewall rule for one port between "
    + "two environments, and is approved with the design.",
  securityNotice: "There is always exactly one Security management group. It holds the management subscription, with the "
    + "central Log Analytics workspace and locked log storage, and the security subscription for Defender for Cloud.",
  securityTooling: "Separate subscription for Microsoft Sentinel, incident response tools and forensics",
  complianceHint: "Each scope gets its own management group with STAGE and PROD children, stricter policies and their "
    + "own spokes.",
  controlsIntro: "Azure Policy definitions come in packs; each pack targets the management groups it fits and governs "
    + "everything below them. Policy Staging evaluates every control without enforcing it.",
  controlNotes: (answers) => [
    "Azure has no proactive controls: packs list their preventive (Deny) and detective (Audit) policies only.",
    ...(answers.defender === "standard" ? ["Defender plans are billed per subscription and protected resource."] : []),
  ],
  answerProblems: (answers) => [
    ...(GUID_PATTERN.test(text(answers.tenant_id)) ? [] : ["Enter the tenant id: a GUID."]),
    ...(BILLING_SCOPE_PATTERN.test(text(answers.billing_scope))
      ? [] : ["Enter the billing scope: an EA enrollment account or an MCA invoice section."]),
    ...AZURE_GROUPS.filter(([role]) => !GUID_PATTERN.test(groupOf(answers, role)))
      .map(([, label]) => `Enter the ${label} group's object id: a GUID.`),
  ],
  emptyAnswers: { tenant_id: "", billing_scope: "", groups: Object.fromEntries(AZURE_GROUPS.map(([role]) => [role, ""])),
    defender: "foundational", firewall_tier: "standard" },
};

const TEXTS: Record<string, LandingZoneCloudText> = { aws: AWS, gcp: GCP, azure: AZURE };

export function cloudText(provider: string): LandingZoneCloudText {
  return TEXTS[provider] ?? AWS;
}
