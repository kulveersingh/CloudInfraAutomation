import type { ResilienceMode } from "../../../api/types";
import type { StepProps } from "./StepProps";

const MODES: Array<{ mode: ResilienceMode; label: string; description: string }> = [
  { mode: "single", label: "Single region", description: "One region; recovery redeploys from code and backups." },
  { mode: "dr", label: "DR · active / standby", description: "Both regions deployed; only the primary is active." },
  { mode: "ha", label: "HA pair · active / active", description: "Both regions active behind health checks." },
];

export function ResilienceStep({ draft, onChange, reference }: StepProps) {
  const { mode, primaryRegion, secondaryRegion } = draft.values;
  const regions = reference.regions.filter((region) => region.enabled);
  return (
    <>
      <h2>Resilience</h2>
      <div className="choice" role="radiogroup" aria-label="Resilience mode">
        {MODES.map((option) => (
          <label key={option.mode} className={`opt ${option.mode === mode ? "on" : ""}`}>
            <input type="radio" name="mode" checked={option.mode === mode} onChange={() => onChange(draft.withMode(option.mode))} />
            <b>{option.label}</b>
            <span className="hint">{option.description}</span>
          </label>
        ))}
      </div>
      <div className="grid3">
        <div className="field">
          <label htmlFor="primary-region">Primary region</label>
          <select id="primary-region" value={primaryRegion} onChange={(event) => onChange(draft.withPrimary(event.target.value))}>
            {regions.map((region) => <option key={region.id} value={region.id}>{region.id} · {region.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="secondary-region">Secondary region</label>
          <select id="secondary-region" value={secondaryRegion} disabled={mode === "single"}
                  onChange={(event) => onChange(draft.withSecondary(event.target.value))}>
            {regions.map((region) => <option key={region.id} value={region.id}>{region.id} · {region.name}</option>)}
          </select>
          <span className="hint">Any pair of enabled regions; default us-east-1 / us-east-2</span>
        </div>
      </div>
    </>
  );
}
