import { useState } from "react";
import type { EnvironmentPreset, LandingZoneAnswers } from "../../../api/types";
import {
  LandingZoneDraft, REQUIRED_ENVIRONMENTS, type EnvironmentTier, type LandingZoneEnvironment,
} from "../../../landingZone/LandingZoneDraft";
import { Choices, type Choice } from "../controls";
import type { StepProps } from "./StepProps";

const PRESETS: Array<Choice<EnvironmentPreset>> = [
  { value: 4, title: "4 environments", description: "Sandbox · DEV · STAGE · PROD. Testing runs in DEV." },
  { value: 5, title: "5 environments", description: "Sandbox · DEV · TEST · STAGE · PROD. Testing is isolated from development.",
    recommended: true },
  { value: 6, title: "6 environments", description: "Sandbox · DEV · TEST · UAT · STAGE · PROD. Adds business acceptance." },
];

const GROUPINGS: Array<Choice<LandingZoneAnswers["grouping"]>> = [
  { value: "separate", title: "Keep every environment separate", recommended: true,
    description: "Each environment OU sits under the root with its own copy of the baseline policies, so one change can't "
      + "loosen production and non-production at once." },
  { value: "prod_nonprod", title: "Two parents: Prod and NonProd",
    description: "Shared policies attach once to each parent and are inherited. Fewer attachments, larger blast radius." },
];

const TIERS: Record<EnvironmentTier, string> = { sandbox: "Sandbox", nonprod: "Non-production", prod: "Production tier" };

export function EnvironmentsStep({ draft, onChange }: StepProps) {
  const { environment_ids, grouping } = draft.toAnswers();
  return (
    <>
      <Choices label="Start from a preset" choices={PRESETS} selected={draft.preset()}
               onSelect={(preset) => onChange(draft.withEnvironmentPreset(preset))} />
      <div className="field">
        <span className="label">Or choose any combination</span>
        <div className="row wrap">
          {LandingZoneDraft.environmentCatalog().map((environment) => (
            <label key={environment.id} className="row">
              <input type="checkbox" aria-label={`Include ${environment.name}`} checked={environment_ids.includes(environment.id)}
                     disabled={REQUIRED_ENVIRONMENTS.includes(environment.id)}
                     onChange={(event) => onChange(draft.withEnvironment(environment.id, event.target.checked))} />
              {environment.name}
            </label>
          ))}
        </div>
        <span className="hint">STAGE and PROD are always included, so production has a separate pre-production
          environment. Every environment is its own isolated OU.</span>
      </div>
      <table>
        <thead><tr><th>Name</th><th>Tier</th><th>OU</th></tr></thead>
        <tbody>
          {draft.environments().map((environment) => (
            <EnvironmentRow key={environment.id} environment={environment} draft={draft} onChange={onChange} />
          ))}
        </tbody>
      </table>
      <p className="notice">Every environment is always its own OU with its own accounts. Environments have no access to
        each other; only the network flows you declare on the Network step are allowed, and they're inspected.</p>
      <Choices label="Put the environment OUs under parent OUs?" choices={GROUPINGS} selected={grouping}
               onSelect={(value) => onChange(draft.with({ grouping: value }))} />
      {grouping === "prod_nonprod" && (
        <p className="notice warn">Not recommended. With shared parents, a single policy edit on NonProd or Prod changes
          several environments at once.</p>
      )}
    </>
  );
}

interface EnvironmentRowProps {
  environment: LandingZoneEnvironment;
  draft: LandingZoneDraft;
  onChange: (draft: LandingZoneDraft) => void;
}

function EnvironmentRow({ environment, draft, onChange }: EnvironmentRowProps) {
  const [name, setName] = useState(environment.name);
  const rename = (next: string) => {
    setName(next);
    onChange(draft.withEnvironmentName(environment.id, next));
  };
  return (
    <tr>
      <td><input type="text" aria-label={`Name for ${environment.id}`} value={name} onChange={(event) => rename(event.target.value)} /></td>
      <td><span className={`chip ${environment.tier}`}>{TIERS[environment.tier]}</span></td>
      <td className="mono">{environment.name} OU</td>
    </tr>
  );
}
