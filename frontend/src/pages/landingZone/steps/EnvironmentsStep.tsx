import { useState } from "react";
import type { EnvironmentCount, LandingZoneAnswers } from "../../../api/types";
import type { EnvironmentTier, LandingZoneDraft, LandingZoneEnvironment } from "../../../landingZone/LandingZoneDraft";
import { Choices, type Choice } from "../controls";
import type { StepProps } from "./StepProps";

const COUNTS: Array<Choice<EnvironmentCount>> = [
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
  const { environment_count, grouping } = draft.toAnswers();
  return (
    <>
      <Choices label="How many environments?" choices={COUNTS} selected={environment_count}
               onSelect={(count) => onChange(draft.withEnvironmentCount(count))} />
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
