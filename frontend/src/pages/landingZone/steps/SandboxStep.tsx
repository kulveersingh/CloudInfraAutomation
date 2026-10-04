import { Checkbox, NumberInput } from "../controls";
import type { StepProps } from "./StepProps";

const OPTIONAL_OUS: Array<{ id: string; label: string; hint: string }> = [
  { id: "exceptions", label: "Exceptions", hint: "Workloads with an approved, time-limited exception to a control" },
  { id: "suspended", label: "Suspended", hint: "Locked down (deny all except break-glass) for accounts being closed" },
  { id: "individual_business_users", label: "Individual Business Users", hint: "Non-workload accounts for business teams" },
];

export function SandboxStep({ draft, onChange }: StepProps) {
  const { sandbox, optional_ous } = draft.toAnswers();
  return (
    <>
      <div className="grid3">
        <div className="field">
          <label htmlFor="lz-sandbox-model">Sandbox accounts</label>
          <select id="lz-sandbox-model" value={sandbox.model}
                  onChange={(event) => onChange(draft.withSandbox({ model: event.target.value as typeof sandbox.model }))}>
            <option value="team">One per team</option>
            <option value="developer">One per developer</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="lz-sandbox-budget">Monthly budget per account (USD)</label>
          <NumberInput id="lz-sandbox-budget" value={sandbox.monthly_budget_usd}
                       onValue={(budget) => onChange(draft.withSandbox({ monthly_budget_usd: budget }))} />
        </div>
        <div className="field">
          <label htmlFor="lz-sandbox-expiry">Resource expiry (days)</label>
          <NumberInput id="lz-sandbox-expiry" value={sandbox.expiry_days}
                       onValue={(days) => onChange(draft.withSandbox({ expiry_days: days }))} />
          <span className="hint">Nightly cleanup removes expired resources</span>
        </div>
      </div>
      <div className="field">
        <span className="label">Other OUs</span>
        <Checkbox label="Policy Staging" hint="Always on: policy and control changes are tested here before promotion" checked />
        {OPTIONAL_OUS.map((ou) => (
          <Checkbox key={ou.id} label={ou.label} hint={ou.hint} checked={optional_ous.includes(ou.id)}
                    onChange={(checked) => onChange(draft.withListItem("optional_ous", ou.id, checked))} />
        ))}
      </div>
    </>
  );
}
