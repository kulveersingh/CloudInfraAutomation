import { useState } from "react";
import { useApi } from "../../../api/ApiContext";
import type { LandingZoneReadBack, TemplateSummary } from "../../../api/types";
import { ErrorAlert } from "../../../components/Notices";
import { RefusedRepository } from "../../../components/RefusedRepository";
import { useLoad } from "../../../hooks/useLoad";
import { plural } from "../../../landingZone/plural";
import type { StepProps } from "./StepProps";

/** Industry templates fill in the questionnaire, OU structure and control packs; everything stays editable. */
export function StartStep({ draft, onTemplate, onRepository }: StepProps) {
  const api = useApi();
  const templates = useLoad(() => api.landingZoneTemplates());
  const [error, setError] = useState<string>();
  const [refused, setRefused] = useState<LandingZoneReadBack>();
  const chosen = draft.toAnswers().template?.id;

  const editCurrent = async () => {
    try {
      setError(undefined);
      setRefused(undefined);
      const readBack = await api.landingZoneReadBack();
      if (readBack.verified) onRepository(readBack);
      else setRefused(readBack);
    } catch (failure) {
      setError((failure as Error).message);
    }
  };

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
      {refused && <RefusedRepository title="The landing zone repository can't be loaded" readBack={refused} />}
      <div className="choice templates">
        <button type="button" className="opt" onClick={editCurrent}>
          <b>Edit the current landing zone</b>
          <span className="hint">Load the design committed to {LANDING_ZONE_REPOSITORY}. The platform checks it generated the
            repository and that nobody edited it by hand.</span>
        </button>
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

export const LANDING_ZONE_REPOSITORY = "landing-zone-infra";

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
