import { useState } from "react";
import { useApi } from "../../../api/ApiContext";
import type { TemplateSummary } from "../../../api/types";
import { ErrorAlert } from "../../../components/Notices";
import { useLoad } from "../../../hooks/useLoad";
import { plural } from "../../../landingZone/plural";
import type { StepProps } from "./StepProps";

/** Industry templates fill in the questionnaire, OU structure and control packs; everything stays editable. */
export function StartStep({ draft, onTemplate }: StepProps) {
  const api = useApi();
  const templates = useLoad(() => api.landingZoneTemplates());
  const [error, setError] = useState<string>();
  const chosen = draft.toAnswers().template?.id;

  const choose = async (templateId: string) => {
    try {
      setError(undefined);
      onTemplate(await api.landingZoneTemplate(templateId));
    } catch (failure) {
      setError((failure as Error).message);
    }
  };

  return (
    <>
      <p className="sub">Start from an industry template, or from the platform's recommendations. You can change every
        answer, environment, OU and control pack afterwards.</p>
      <ErrorAlert message={templates.error ?? error} />
      <div className="choice templates">
        <button type="button" className={`opt ${chosen ? "" : "on"}`} aria-pressed={!chosen} onClick={() => onTemplate()}>
          <b>Start from scratch</b>
          <span className="hint">The recommended five environments and the Strongly recommended controls.</span>
        </button>
        {templates.data?.map((template) => (
          <TemplateCard key={template.id} template={template} chosen={template.id === chosen} onChoose={() => choose(template.id)} />
        ))}
      </div>
    </>
  );
}

function TemplateCard({ template, chosen, onChoose }: { template: TemplateSummary; chosen: boolean; onChoose: () => void }) {
  const controls = Object.values(template.control_counts).reduce((total, count) => total + count, 0);
  return (
    <button type="button" className={`opt ${chosen ? "on" : ""}`} aria-pressed={chosen} onClick={onChoose}>
      <b>{template.name}</b>
      <span className="hint">{template.industry}</span>
      <span>{template.description}</span>
      <span className="tags">
        {template.frameworks.map((framework) => <span key={framework} className="tag">{framework}</span>)}
        {!template.frameworks_verified && <span className="hint">intended alignment (unverified)</span>}
      </span>
      <span className="mono">{template.environments.join(" · ")}</span>
      <span className="hint">{plural(template.ou_count, "OU")} · {plural(controls, "control")} ({plural(template.enabled_controls,
        "enablement")})</span>
    </button>
  );
}
