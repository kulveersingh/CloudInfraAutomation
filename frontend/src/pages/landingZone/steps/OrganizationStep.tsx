import { cloudText } from "../../../landingZone/cloudText";
import type { LandingZoneDraft } from "../../../landingZone/LandingZoneDraft";
import type { StepProps } from "./StepProps";

const SCC_TIERS: Array<[string, string]> = [["premium", "Premium (recommended)"], ["enterprise", "Enterprise"],
  ["standard", "Standard (no detective controls)"]];

export function OrganizationStep({ draft, onChange }: StepProps) {
  const answers = draft.toAnswers();
  const text = cloudText(draft.provider);
  return (
    <>
      <p className="sub">{text.organizationIntro}</p>
      <div className="grid3">
        <div className="field">
          <label htmlFor="lz-name">Organization name</label>
          <input type="text" id="lz-name" value={answers.organization_name}
                 onChange={(event) => onChange(draft.with({ organization_name: event.target.value }))} />
          <span className="hint">Prefix for {draft.provider === "gcp" ? "project ids and folder paths" : "account names and OU paths"}</span>
        </div>
        {draft.provider === "gcp" ? <GoogleCloudAnswers draft={draft} onChange={onChange} /> : (
          <div className="field">
            <label htmlFor="lz-email">Management account email</label>
            <input type="text" id="lz-email" value={draft.managementEmail()}
                   onChange={(event) => onChange(draft.withOrganization(answers.organization_name, event.target.value))} />
            <span className="hint">A distribution list, not a person</span>
          </div>
        )}
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

/** What only Google Cloud asks: the existing organization, its billing account and domain, and the SCC tier. */
function GoogleCloudAnswers({ draft, onChange }: { draft: LandingZoneDraft; onChange: (draft: LandingZoneDraft) => void }) {
  const field = (name: string, label: string, hint: string) => (
    <div className="field" key={name}>
      <label htmlFor={`lz-${name}`}>{label}</label>
      <input type="text" id={`lz-${name}`} value={draft.providerAnswer(name)}
             onChange={(event) => onChange(draft.withProviderAnswer(name, event.target.value))} />
      <span className="hint">{hint}</span>
    </div>
  );
  return (
    <>
      {field("organization_id", "Organization id", "Digits, from the organization's settings")}
      {field("billing_account", "Billing account", "XXXXXX-XXXXXX-XXXXXX; projects are billed to it")}
      {field("domain", "Domain", "Only identities in it can be granted access; admin groups default to gcp-<role>@domain")}
      <div className="field">
        <label htmlFor="lz-scc-tier">Security Command Center tier</label>
        <select id="lz-scc-tier" value={draft.providerAnswer("scc_tier")}
                onChange={(event) => onChange(draft.withProviderAnswer("scc_tier", event.target.value))}>
          {SCC_TIERS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <span className="hint">Detective controls are deployed as postures, which need Premium or Enterprise</span>
      </div>
    </>
  );
}
