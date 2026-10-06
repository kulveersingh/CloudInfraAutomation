import type { ResilienceMode } from "../../../api/types";
import { RegionPairs } from "../../../wizard/RegionPairs";
import { chosenCloud, type StepProps } from "./StepProps";

const MODES: Array<{ mode: ResilienceMode; label: string; description: string }> = [
  { mode: "single", label: "Single region", description: "One region; recovery redeploys from code and backups." },
  { mode: "dr", label: "DR · active / standby", description: "Both regions deployed; only the primary is active." },
  { mode: "ha", label: "HA pair · active / active", description: "Both regions active behind health checks." },
];

export function ResilienceStep({ draft, onChange, reference, change }: StepProps) {
  const locked = change !== undefined;
  const { mode, primaryRegion, secondaryRegion, provider } = draft.values;
  const regions = reference.regions.filter((region) => region.provider === provider && region.enabled);
  const cloud = chosenCloud(reference, provider);
  const defaults = cloud?.default_regions;
  const pairs = new RegionPairs(cloud?.region_pairs, regions.map((region) => region.id));
  const hasStorage = draft.values.resources.some((resource) => resource.type === "storage.bucket");
  const pairHint = pairs.hint(mode, primaryRegion);
  const problem = pairs.problem(mode, primaryRegion, secondaryRegion, hasStorage);
  const choosePrimary = (primary: string) =>
    onChange(draft.withPrimary(primary).withSecondary(pairs.secondaryFor(primary, secondaryRegion)));
  return (
    <>
      <h2>Resilience</h2>
      <div className="choice" role="radiogroup" aria-label="Resilience mode">
        {MODES.map((option) => (
          <label key={option.mode} className={`opt ${option.mode === mode ? "on" : ""}`}>
            <input type="radio" name="mode" checked={option.mode === mode} disabled={locked} onChange={() => onChange(draft.withMode(option.mode))} />
            <b>{option.label}</b>
            <span className="hint">{option.description}</span>
          </label>
        ))}
      </div>
      <div className="grid3">
        <div className="field">
          <label htmlFor="primary-region">Primary region</label>
          <select id="primary-region" value={primaryRegion} disabled={locked} onChange={(event) => choosePrimary(event.target.value)}>
            {regions.map((region) => <option key={region.id} value={region.id}>{region.id} · {region.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="secondary-region">Secondary region</label>
          <select id="secondary-region" value={secondaryRegion} disabled={locked || mode === "single"}
                  onChange={(event) => onChange(draft.withSecondary(event.target.value))}>
            {regions.map((region) => <option key={region.id} value={region.id}>{region.id} · {region.name}</option>)}
          </select>
          <span className="hint">Any pair of enabled regions{defaults && `; default ${defaults.primary} / ${defaults.secondary}`}</span>
          {pairHint && <span className="hint">{pairHint}</span>}
        </div>
      </div>
      {problem && <div role="alert" className="notice warn">{problem}</div>}
    </>
  );
}
