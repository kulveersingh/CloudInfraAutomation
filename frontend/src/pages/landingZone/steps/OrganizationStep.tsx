import type { StepProps } from "./StepProps";

/** Every commercial region Control Tower can govern; the organization is new, so the platform registry doesn't apply. */
const AWS_REGIONS = [
  "us-east-1", "us-east-2", "us-west-1", "us-west-2", "ca-central-1", "sa-east-1", "eu-west-1", "eu-west-2", "eu-west-3",
  "eu-central-1", "eu-central-2", "eu-north-1", "eu-south-1", "eu-south-2", "ap-south-1", "ap-south-2", "ap-southeast-1",
  "ap-southeast-2", "ap-southeast-3", "ap-southeast-4", "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
  "ap-east-1", "me-south-1", "me-central-1", "af-south-1", "il-central-1",
];

export function OrganizationStep({ draft, onChange }: StepProps) {
  const answers = draft.toAnswers();
  return (
    <>
      <p className="sub">Creates a new AWS Organization with all features and an AWS Control Tower landing zone in the
        management (payer) account.</p>
      <div className="grid3">
        <div className="field">
          <label htmlFor="lz-name">Organization name</label>
          <input type="text" id="lz-name" value={answers.organization_name}
                 onChange={(event) => onChange(draft.withOrganization(event.target.value, draft.managementEmail()))} />
          <span className="hint">Prefix for account names and OU paths</span>
        </div>
        <div className="field">
          <label htmlFor="lz-email">Management account email</label>
          <input type="text" id="lz-email" value={draft.managementEmail()}
                 onChange={(event) => onChange(draft.withOrganization(answers.organization_name, event.target.value))} />
          <span className="hint">A distribution list, not a person</span>
        </div>
        <div className="field">
          <label htmlFor="lz-home">Home region</label>
          <select id="lz-home" value={answers.home_region} onChange={(event) => onChange(draft.with({ home_region: event.target.value }))}>
            {AWS_REGIONS.map((region) => <option key={region}>{region}</option>)}
          </select>
          <span className="hint">Where Control Tower runs</span>
        </div>
      </div>
      <div className="field">
        <span className="label">Governed regions</span>
        <div className="row wrap">
          {AWS_REGIONS.map((region) => (
            <label key={region} className="row">
              <input type="checkbox" aria-label={`Govern ${region}`} checked={answers.governed_regions.includes(region)}
                     onChange={(event) => onChange(draft.withRegion(region, event.target.checked))} />
              <span className="mono">{region}</span>
            </label>
          ))}
        </div>
        <span className="hint">All other regions are denied by SCP. Any two governed regions can be a DR/HA pair.</span>
      </div>
    </>
  );
}
