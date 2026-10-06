import { cloudText } from "../../../landingZone/cloudText";
import { useVocabulary } from "../../../providers/VocabularyContext";
import { Checkbox } from "../controls";
import type { StepProps } from "./StepProps";

const RETENTION: Array<[number, string]> = [[365, "1 year (STAGE/PROD 7 years)"], [730, "2 years"], [2555, "7 years for all"]];
const COMPLIANCE_SCOPES = ["PCI", "HIPAA", "GxP"];

export function SecurityStep({ draft, onChange }: StepProps) {
  const { security_tooling, log_retention_days, compliance } = draft.toAnswers();
  const text = cloudText(draft.provider);
  const words = useVocabulary(draft.provider);
  return (
    <>
      <p className="notice">{text.securityNotice}</p>
      <Checkbox label={`Add a Security Tooling ${words.isolation_unit}`} checked={security_tooling} hint={text.securityTooling}
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
        <span className="hint">{text.complianceHint}</span>
      </div>
    </>
  );
}
