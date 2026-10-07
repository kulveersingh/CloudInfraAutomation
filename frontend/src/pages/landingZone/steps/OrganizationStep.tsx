import type { ComponentType } from "react";
import { AZURE_GROUPS, cloudText } from "../../../landingZone/cloudText";
import type { LandingZoneDraft } from "../../../landingZone/LandingZoneDraft";
import type { StepProps } from "./StepProps";

type AnswersProps = { draft: LandingZoneDraft; onChange: (draft: LandingZoneDraft) => void };

const SCC_TIERS: Array<[string, string]> = [["premium", "Premium (recommended)"], ["enterprise", "Enterprise"],
  ["standard", "Standard (no detective controls)"]];
const DEFENDER: Array<[string, string]> = [["foundational", "Foundational CSPM (free)"],
  ["standard", "Defender plans (paid, per subscription)"]];
const FIREWALL_TIERS: Array<[string, string]> = [["standard", "Standard"], ["premium", "Premium (TLS inspection and IDPS)"]];

/** Each cloud's own questions; a new cloud adds its entry. */
const PROVIDER_ANSWERS: Record<string, ComponentType<AnswersProps>> = {
  gcp: GoogleCloudAnswers,
  azure: AzureAnswers,
};

export function OrganizationStep({ draft, onChange }: StepProps) {
  const answers = draft.toAnswers();
  const text = cloudText(draft.provider);
  const ProviderAnswers = PROVIDER_ANSWERS[draft.provider] ?? AwsAnswers;
  return (
    <>
      <p className="sub">{text.organizationIntro}</p>
      <div className="grid3">
        <div className="field">
          <label htmlFor="lz-name">Organization name</label>
          <input type="text" id="lz-name" value={answers.organization_name}
                 onChange={(event) => onChange(draft.with({ organization_name: event.target.value }))} />
          <span className="hint">{text.namePrefixHint}</span>
        </div>
        <ProviderAnswers draft={draft} onChange={onChange} />
        <div className="field">
          <label htmlFor="lz-home">Home region</label>
          <select id="lz-home" value={answers.home_region} onChange={(event) => onChange(draft.with({ home_region: event.target.value }))}>
            {text.regions.map((region) => <option key={region}>{region}</option>)}
          </select>
          <span className="hint">{text.homeRegionHint}</span>
        </div>
      </div>
      <div className="field">
        <span className="label">Governed regions</span>
        <div className="row wrap">
          {text.regions.map((region) => (
            <label key={region} className="row">
              <input type="checkbox" aria-label={`Govern ${region}`} checked={answers.governed_regions.includes(region)}
                     onChange={(event) => onChange(draft.withRegion(region, event.target.checked))} />
              <span className="mono">{region}</span>
            </label>
          ))}
        </div>
        <span className="hint">{text.governedRegionsHint}</span>
      </div>
    </>
  );
}

function TextField({ id, label, hint, value, onChange }: { id: string; label: string; hint: string; value: string;
  onChange: (value: string) => void }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input type="text" id={id} value={value} onChange={(event) => onChange(event.target.value)} />
      <span className="hint">{hint}</span>
    </div>
  );
}

function Choice({ id, label, hint, value, options, onChange }: { id: string; label: string; hint: string; value: string;
  options: Array<[string, string]>; onChange: (value: string) => void }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(([option, text]) => <option key={option} value={option}>{text}</option>)}
      </select>
      <span className="hint">{hint}</span>
    </div>
  );
}

/** What only AWS asks: the management account's email. */
function AwsAnswers({ draft, onChange }: AnswersProps) {
  return <TextField id="lz-email" label="Management account email" hint="A distribution list, not a person"
                    value={draft.managementEmail()}
                    onChange={(value) => onChange(draft.withOrganization(draft.toAnswers().organization_name, value))} />;
}

/** What only Google Cloud asks: the existing organization, its billing account and domain, and the SCC tier. */
function GoogleCloudAnswers({ draft, onChange }: AnswersProps) {
  const field = (name: string, label: string, hint: string) => (
    <TextField key={name} id={`lz-${name}`} label={label} hint={hint} value={draft.providerAnswer(name)}
               onChange={(value) => onChange(draft.withProviderAnswer(name, value))} />
  );
  return (
    <>
      {field("organization_id", "Organization id", "Digits, from the organization's settings")}
      {field("billing_account", "Billing account", "XXXXXX-XXXXXX-XXXXXX; projects are billed to it")}
      {field("domain", "Domain", "Only identities in it can be granted access; admin groups default to gcp-<role>@domain")}
      <Choice id="lz-scc-tier" label="Security Command Center tier" options={SCC_TIERS}
              hint="Detective controls are deployed as postures, which need Premium or Enterprise"
              value={draft.providerAnswer("scc_tier")} onChange={(value) => onChange(draft.withProviderAnswer("scc_tier", value))} />
    </>
  );
}

/** What only Azure asks: the tenant, the billing scope subscriptions are created against, the admin groups by object
 *  id, Defender plans and the firewall tier. */
function AzureAnswers({ draft, onChange }: AnswersProps) {
  return (
    <>
      <TextField id="lz-tenant" label="Tenant id" hint="The Microsoft Entra tenant's GUID" value={draft.providerAnswer("tenant_id")}
                 onChange={(value) => onChange(draft.withProviderAnswer("tenant_id", value))} />
      <TextField id="lz-billing-scope" label="Billing scope" value={draft.providerAnswer("billing_scope")}
                 hint="An EA enrollment account or an MCA invoice section; subscriptions are created against it"
                 onChange={(value) => onChange(draft.withProviderAnswer("billing_scope", value))} />
      {AZURE_GROUPS.map(([role, label]) => (
        <TextField key={role} id={`lz-group-${role}`} label={`${label} group`} value={draft.group(role)}
                   hint="Object id of an existing Entra group" onChange={(value) => onChange(draft.withGroup(role, value))} />
      ))}
      <Choice id="lz-defender" label="Defender for Cloud" options={DEFENDER} value={draft.providerAnswer("defender")}
              hint="Audit policies are always on; paid plans add threat protection"
              onChange={(value) => onChange(draft.withProviderAnswer("defender", value))} />
      <Choice id="lz-firewall-tier" label="Azure Firewall tier" options={FIREWALL_TIERS}
              value={draft.providerAnswer("firewall_tier")} hint="The hubs' firewalls"
              onChange={(value) => onChange(draft.withProviderAnswer("firewall_tier", value))} />
    </>
  );
}
