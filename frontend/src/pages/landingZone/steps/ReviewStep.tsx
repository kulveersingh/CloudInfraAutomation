import { useState } from "react";
import { useApi } from "../../../api/ApiContext";
import type { IndustryTemplate, LandingZoneProposal } from "../../../api/types";
import { ErrorAlert } from "../../../components/Notices";
import { useVocabulary } from "../../../providers/VocabularyContext";
import { EditDescriber } from "../../../landingZone/EditDescriber";
import type { LandingZoneDraft } from "../../../landingZone/LandingZoneDraft";
import { OuTreeIndex } from "../../../landingZone/OuTreeIndex";
import { GeneratedFiles, StructureView } from "../StructureView";
import { ManualChanges } from "../tree/ManualChanges";
import type { StepProps } from "./StepProps";

export function ReviewStep({ draft, onChange, onSubmitted, template }: StepProps) {
  const api = useApi();
  const [proposal, setProposal] = useState<LandingZoneProposal>();
  const [error, setError] = useState<string>();
  const problems = draft.problems();
  const words = useVocabulary(draft.provider);

  const attempt = async (action: () => Promise<void>) => {
    try {
      setError(undefined);
      await action();
    } catch (failure) {
      setError((failure as Error).message);
    }
  };
  const propose = (next: LandingZoneDraft) => attempt(async () => setProposal(await api.proposeLandingZone(next.toRequest())));
  /** Every tree edit is proposed again at once, so the platform stays the one source of the tree and its problems. */
  const change = (next: LandingZoneDraft) => {
    onChange(next);
    return propose(next);
  };
  const requestApproval = () => attempt(async () => {
    const design = await api.createLandingZoneDesign(draft.toRequest());
    onSubmitted(await api.submitLandingZoneDesign(design.id));
  });

  return (
    <>
      <p className="sub">The platform proposes the {words.hierarchy_node} structure from your answers and generates the{" "}
        {words.iac_document}. Nothing is created until a second platform admin approves.</p>
      {template && <TemplateBanner draft={draft} template={template} onReset={() => onChange(draft.withTemplate(template))} />}
      <ProblemList problems={problems} />
      <div className="row">
        <button className="btn" disabled={problems.length > 0} onClick={() => propose(draft)}>Propose structure</button>
        {proposal && (
          <button className="btn pri" disabled={proposal.problems.length > 0} onClick={requestApproval}>Request approval</button>
        )}
      </div>
      <ErrorAlert message={error} />
      {proposal && <ProposalEditor proposal={proposal} draft={draft} onChange={change} />}
    </>
  );
}

interface ProposalEditorProps {
  proposal: LandingZoneProposal;
  draft: LandingZoneDraft;
  onChange: (draft: LandingZoneDraft) => void;
}

function ProposalEditor({ proposal, draft, onChange }: ProposalEditorProps) {
  const index = new OuTreeIndex(proposal.ous);
  return (
    <>
      <ProblemList problems={proposal.problems} />
      {proposal.warnings.length > 0 && (
        <ul className="notice warn">{proposal.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
      )}
      <StructureView explanation={proposal} stage="Proposed" editor={{ index, onEdit: (edit) => onChange(draft.withEdit(edit)) }} />
      <ManualChanges edits={draft.edits()} describer={new EditDescriber(index)}
                     onUndo={(position) => onChange(draft.withoutEdit(position))} />
      <GeneratedFiles files={proposal.files} />
    </>
  );
}

interface TemplateBannerProps {
  draft: LandingZoneDraft;
  template: IndustryTemplate;
  onReset: () => void;
}

/** Which template the design started from and what was changed from it. */
function TemplateBanner({ draft, template, onReset }: TemplateBannerProps) {
  const differences = draft.differencesFrom(template);
  return (
    <div className="notice row">
      <b>Based on {template.name} v{template.version}</b>
      {differences.length > 0 && <span>Changed: {differences.join(", ")}</span>}
      <button className="btn ghost" onClick={onReset}>Reset to template</button>
    </div>
  );
}

function ProblemList({ problems }: { problems: string[] }) {
  return problems.length > 0 ? <ul className="notice crit">{problems.map((problem) => <li key={problem}>{problem}</li>)}</ul> : null;
}
