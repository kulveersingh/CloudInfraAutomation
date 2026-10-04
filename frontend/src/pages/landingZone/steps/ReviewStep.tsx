import { useState } from "react";
import { useApi } from "../../../api/ApiContext";
import type { LandingZoneProposal } from "../../../api/types";
import { ErrorAlert } from "../../../components/Notices";
import { GeneratedFiles, StructureView } from "../StructureView";
import type { StepProps } from "./StepProps";

export function ReviewStep({ draft, onSubmitted }: StepProps) {
  const api = useApi();
  const [proposal, setProposal] = useState<LandingZoneProposal>();
  const [error, setError] = useState<string>();
  const problems = draft.problems();

  const attempt = async (action: () => Promise<void>) => {
    try {
      setError(undefined);
      await action();
    } catch (failure) {
      setError((failure as Error).message);
    }
  };
  const propose = () => attempt(async () => setProposal(await api.proposeLandingZone(draft.toAnswers())));
  const requestApproval = () => attempt(async () => {
    const design = await api.createLandingZoneDesign(draft.toAnswers());
    onSubmitted(await api.submitLandingZoneDesign(design.id));
  });

  return (
    <>
      <p className="sub">The platform proposes the OU structure from your answers and generates the CloudFormation. Nothing
        is created until a second platform admin approves.</p>
      <ProblemList problems={problems} />
      <div className="row">
        <button className="btn" disabled={problems.length > 0} onClick={propose}>Propose structure</button>
        {proposal && (
          <button className="btn pri" disabled={proposal.problems.length > 0} onClick={requestApproval}>Request approval</button>
        )}
      </div>
      <ErrorAlert message={error} />
      {proposal && (
        <>
          <ProblemList problems={proposal.problems} />
          <StructureView explanation={proposal} stage="Proposed" />
          <GeneratedFiles files={proposal.files} />
        </>
      )}
    </>
  );
}

function ProblemList({ problems }: { problems: string[] }) {
  return problems.length > 0 ? <ul className="notice crit">{problems.map((problem) => <li key={problem}>{problem}</li>)}</ul> : null;
}
