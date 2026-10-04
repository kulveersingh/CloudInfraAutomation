import { Checkbox } from "../controls";
import type { StepProps } from "./StepProps";

const RETENTION: Array<[number, string]> = [[365, "1 year (STAGE/PROD 7 years)"], [730, "2 years"], [2555, "7 years for all"]];
const COMPLIANCE_SCOPES = ["PCI", "HIPAA", "GxP"];

export function SecurityStep({ draft, onChange }: StepProps) {
  const { security_tooling, log_retention_days, compliance } = draft.toAnswers();
  return (
    <>
      <p className="notice">There is always exactly one Security OU, created by Control Tower. It holds the Log Archive and
        Audit accounts; Audit is the delegated administrator for GuardDuty, Security Hub, Inspector and Macie.</p>
      <Checkbox label="Add a Security Tooling account" checked={security_tooling}
                hint="Separate account for SIEM forwarding, incident response tools and forensics"
                onChange={(checked) => onChange(draft.with({ security_tooling: checked }))} />
      <div className="field">
        <label htmlFor="lz-retention">Central log retention</label>
        <select id="lz-retention" value={log_retention_days}
                onChange={(event) => onChange(draft.with({ log_retention_days: Number(event.target.value) }))}>
          {RETENTION.map(([days, label]) => <option key={days} value={days}>{label}</option>)}
        </select>
      </div>
      <div className="field">
        <span className="label">Regulated workloads</span>
        <div className="row">
          {COMPLIANCE_SCOPES.map((scope) => (
            <label key={scope} className="row">
              <input type="checkbox" checked={compliance.includes(scope)}
                     onChange={(event) => onChange(draft.withListItem("compliance", scope, event.target.checked))} />
              {scope}
            </label>
          ))}
        </div>
        <span className="hint">Each scope gets its own OU with STAGE and PROD child OUs, stricter controls and its Security
          Hub standard.</span>
      </div>
    </>
  );
}
