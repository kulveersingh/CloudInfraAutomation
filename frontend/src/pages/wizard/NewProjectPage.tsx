import { useState } from "react";
import { useApi } from "../../api/ApiContext";
import { ErrorAlert } from "../../components/Notices";
import { useLoad } from "../../hooks/useLoad";
import { ProjectDraft } from "../../wizard/ProjectDraft";
import { JobProgress } from "./JobProgress";
import { loadReferenceData, ProjectWizard } from "./ProjectWizard";

interface NewProjectPageProps {
  newKey?: () => string;
  pollMs?: number;
}

export function NewProjectPage({ newKey = () => crypto.randomUUID(), pollMs = 2000 }: NewProjectPageProps) {
  const api = useApi();
  const reference = useLoad(() => loadReferenceData(api));
  const [jobId, setJobId] = useState<string>();

  return (
    <section className="page">
      <header className="head">
        <div>
          <h1>New project</h1>
          <p className="sub">Pick who owns it, how resilient it must be and which AWS services it needs.</p>
        </div>
      </header>
      <ErrorAlert message={reference.error} />
      {jobId && <JobProgress jobId={jobId} pollMs={pollMs} />}
      {!jobId && reference.data && (
        <ProjectWizard reference={reference.data}
                       initial={ProjectDraft.initial().withAttachCompute(reference.data.networkSettings.attach_compute_by_default)}
                       mode={{ kind: "new", newKey, onCreated: setJobId }} />
      )}
    </section>
  );
}
