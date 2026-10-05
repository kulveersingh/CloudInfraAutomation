import type { StepProps } from "./StepProps";

export function EnvironmentsStep({ draft, onChange, reference, change }: StepProps) {
  return (
    <>
      <h2>Environments</h2>
      <p className="sub">Accounts come from the account bindings of your portfolio; you cannot choose an account directly.</p>
      <ul className="environments">
        {reference.environments.map((environment) => (
          <li key={environment.id} className="row">
            <input id={`env-${environment.id}`} type="checkbox" checked={draft.values.environments.includes(environment.id)}
                   disabled={change?.environments.includes(environment.id)}
                   onChange={(event) => onChange(draft.withEnvironment(environment.id, event.target.checked))} />
            <label htmlFor={`env-${environment.id}`}>{environment.name}</label>
            <span className={`chip ${environment.requires_approval ? "warn" : "idle"}`}>
              {environment.requires_approval ? "Reviewer approval" : "No approval"}
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}
