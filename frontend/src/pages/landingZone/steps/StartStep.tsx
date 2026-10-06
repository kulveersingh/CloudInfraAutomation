import { useState } from "react";
import { useApi } from "../../../api/ApiContext";
import type { LandingZoneReadBack, TemplateSummary } from "../../../api/types";
import { ErrorAlert } from "../../../components/Notices";
import { CloudPicker } from "../../../components/CloudPicker";
import { RefusedRepository } from "../../../components/RefusedRepository";
import { useLoad } from "../../../hooks/useLoad";
import { cloudText } from "../../../landingZone/cloudText";
import { plural } from "../../../landingZone/plural";
import { useProviders, useVocabulary } from "../../../providers/VocabularyContext";
import type { StepProps } from "./StepProps";

/** Industry templates fill in the questionnaire, OU structure and control packs; everything stays editable. */
export function StartStep(props: StepProps) {
  const { draft, onChange } = props;
  return (
    <>
      <div className="grid3">
        <CloudPicker providers={useProviders().filter((provider) => provider.landing_zone)} value={draft.provider} onChange={(provider) => onChange(draft.withProvider(provider))} />
      </div>
      <CloudStart key={draft.provider} {...props} />
    </>
  );
}

/** The chosen cloud's templates, and its committed landing zone to continue from. */
function CloudStart({ draft, onTemplate, onRepository }: StepProps) {
  const api = useApi();
  const provider = draft.provider;
  const words = useVocabulary(provider);
  const repository = cloudText(provider).repository;
  const templates = useLoad(() => api.landingZoneTemplates(provider));
  const [error, setError] = useState<string>();
  const [refused, setRefused] = useState<LandingZoneReadBack>();
  const chosen = draft.toAnswers().template?.id;

  const editCurrent = async () => {
    try {
      setError(undefined);
      setRefused(undefined);
      const readBack = await api.landingZoneReadBack(provider);
      if (readBack.verified) onRepository(readBack);
      else setRefused(readBack);
    } catch (failure) {
      setError((failure as Error).message);
    }
  };

  const choose = async (templateId: string) => {
    try {
      setError(undefined);
      onTemplate(await api.landingZoneTemplate(templateId, provider));
    } catch (failure) {
      setError((failure as Error).message);
    }
  };

  return (
    <>
      <p className="sub">Start from an industry template, or from the platform's recommendations. You can change every
        answer, environment, {words.hierarchy_node} and control pack afterwards.</p>
      <ErrorAlert message={templates.error ?? error} />
      {refused && <RefusedRepository title="The landing zone repository can't be loaded" readBack={refused} />}
      <div className="choice templates">
        <button type="button" className="opt" onClick={editCurrent}>
          <b>Edit the current landing zone</b>
          <span className="hint">Load the design committed to {repository}. The platform checks it generated the
            repository and that nobody edited it by hand.</span>
        </button>
        <button type="button" className={`opt ${chosen ? "" : "on"}`} aria-pressed={!chosen} onClick={() => onTemplate()}>
          <b>Start from scratch</b>
          <span className="hint">The recommended five environments and the Strongly recommended controls.</span>
        </button>
        {templates.data?.map((template) => (
          <TemplateCard key={template.id} template={template} chosen={template.id === chosen} node={words.hierarchy_node}
                        onChoose={() => choose(template.id)} />
        ))}
      </div>
    </>
  );
}

function TemplateCard({ template, chosen, node, onChoose }: {
  template: TemplateSummary; chosen: boolean; node: string; onChoose: () => void;
}) {
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
      <span className="hint">{plural(template.ou_count, node)} · {plural(controls, "control")} ({plural(template.enabled_controls,
        "enablement")})</span>
    </button>
  );
}
