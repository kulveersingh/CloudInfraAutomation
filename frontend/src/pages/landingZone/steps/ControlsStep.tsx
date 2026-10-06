import { useApi } from "../../../api/ApiContext";
import type { ControlPackCatalog, ControlPackInfo, ControlsProfile, IndustryTemplate } from "../../../api/types";
import { ErrorAlert } from "../../../components/Notices";
import { useLoad } from "../../../hooks/useLoad";
import { cloudText } from "../../../landingZone/cloudText";
import { Choices, type Choice } from "../controls";
import type { StepProps } from "./StepProps";

const PROFILES: Array<Choice<ControlsProfile>> = [
  { value: "baseline", title: "Baseline", description: "The Foundation pack: root user, MFA and public-exposure basics." },
  { value: "recommended", title: "Strongly recommended", recommended: true,
    description: "Baseline plus data protection, network hardening and production resilience." },
  { value: "regulated", title: "Regulated",
    description: "Strongly recommended plus logging integrity and key management." },
];

const BEHAVIORS = ["PREVENTIVE", "DETECTIVE", "PROACTIVE"] as const;

export function ControlsStep({ draft, onChange, template }: StepProps) {
  const api = useApi();
  const provider = draft.provider;
  const catalog = useLoad(() => api.controlPacks(provider));
  const { controls_profile, control_packs, provider_answers } = draft.toAnswers();
  const text = cloudText(provider);
  return (
    <>
      <p className="sub">{text.controlsIntro}</p>
      {text.controlNotes(provider_answers).map((note) => <p key={note} className="notice warn">{note}</p>)}
      <Choices label="Controls profile" choices={PROFILES} selected={control_packs ? undefined : controls_profile}
               onSelect={(profile) => onChange(draft.withProfile(profile))} />
      <ErrorAlert message={catalog.error} />
      {catalog.data && (
        <PackList catalog={catalog.data} chosen={control_packs ?? catalog.data.profiles[controls_profile]} template={template}
                  onChoose={(packs) => onChange(draft.withControlPacks(packs))} />
      )}
    </>
  );
}

interface PackListProps {
  catalog: ControlPackCatalog;
  chosen: string[];
  template?: IndustryTemplate;
  onChoose: (packs: string[]) => void;
}

function PackList({ catalog, chosen, template, onChoose }: PackListProps) {
  const toggle = (pack: string, included: boolean) => onChoose(catalog.packs.map((item) => item.id)
    .filter((id) => (id === pack ? included : chosen.includes(id))));
  return (
    <div className="packs">
      {catalog.packs.map((pack) => (
        <PackCard key={pack.id} pack={pack} chosen={chosen.includes(pack.id)} refreshed={catalog.mappings_refreshed !== null}
                  template={template} onToggle={(included) => toggle(pack.id, included)} />
      ))}
    </div>
  );
}

interface PackCardProps {
  pack: ControlPackInfo;
  chosen: boolean;
  refreshed: boolean;
  template?: IndustryTemplate;
  onToggle: (included: boolean) => void;
}

function PackCard({ pack, chosen, refreshed, template, onToggle }: PackCardProps) {
  const counts = BEHAVIORS.map((behavior) => `${pack.controls.filter((control) => control.behavior === behavior).length} `
    + behavior.toLowerCase()).join(" · ");
  const frameworks = [...new Set(pack.controls.flatMap((control) => control.frameworks))];
  const dropped = !chosen && template?.packs.includes(pack.id);
  return (
    <fieldset className="panel pack" aria-label={pack.name}>
      <label className="row check">
        <input type="checkbox" aria-label={`Use ${pack.name}`} checked={chosen} onChange={(event) => onToggle(event.target.checked)} />
        <span><b>{pack.name}</b>{pack.optional && <span className="chip">Optional</span>}<br />
          <span className="hint">{pack.description}</span></span>
      </label>
      <span className="hint">Targets: {pack.selectors.join(", ")}</span>
      <span className="hint">{counts}</span>
      <span className="hint">Frameworks: {frameworks.length ? frameworks.join(", ") : refreshed ? "none mapped" : "not refreshed yet"}</span>
      <details>
        <summary>Controls ({pack.controls.length})</summary>
        <ul>{pack.controls.map((control) => <li key={control.id}>{control.name}</li>)}</ul>
      </details>
      {dropped && (
        <p className="notice warn">{pack.name} is part of the {template!.name} template, aligned with {template!.frameworks.join(", ")}.
          Turning it off removes that coverage.</p>
      )}
    </fieldset>
  );
}
