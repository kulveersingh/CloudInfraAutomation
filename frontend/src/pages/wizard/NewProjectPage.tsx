import { useState, type ReactNode } from "react";
import { useApi } from "../../api/ApiContext";
import type { PlatformApiPort } from "../../api/types";
import { ErrorAlert } from "../../components/Notices";
import { useLoad } from "../../hooks/useLoad";
import { ProjectDraft } from "../../wizard/ProjectDraft";
import { JobProgress } from "./JobProgress";
import { ConnectionsStep } from "./steps/ConnectionsStep";
import { EnvironmentsStep } from "./steps/EnvironmentsStep";
import { NetworkStep } from "./steps/NetworkStep";
import { OwnershipStep } from "./steps/OwnershipStep";
import { PreviewStep } from "./steps/PreviewStep";
import { ResilienceStep } from "./steps/ResilienceStep";
import { ServicesStep } from "./steps/ServicesStep";
import type { ReferenceData, StepProps } from "./steps/StepProps";

interface WizardContext extends StepProps {
  newKey: () => string;
  onCreated: (jobId: string) => void;
}

const STEPS: Array<{ label: string; render: (context: WizardContext) => ReactNode }> = [
  { label: "Ownership", render: (context) => <OwnershipStep {...context} /> },
  { label: "Resilience", render: (context) => <ResilienceStep {...context} /> },
  { label: "Services", render: (context) => <ServicesStep {...context} /> },
  { label: "Connections", render: (context) => <ConnectionsStep {...context} /> },
  { label: "Environments", render: (context) => <EnvironmentsStep {...context} /> },
  { label: "Network", render: (context) => <NetworkStep {...context} /> },
  { label: "Preview", render: (context) => <PreviewStep {...context} /> },
];

async function loadReferenceData(api: PlatformApiPort): Promise<ReferenceData> {
  const [portfolios, environments, regions, catalog, networkSettings] = await Promise.all([
    api.orgRegistry(), api.environments(), api.regions(), api.catalog(), api.networkSettings()]);
  return { portfolios, environments, regions, catalog, networkSettings };
}

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
      {!jobId && reference.data && <Wizard reference={reference.data} newKey={newKey} onCreated={setJobId} />}
    </section>
  );
}

interface WizardProps {
  reference: ReferenceData;
  newKey: () => string;
  onCreated: (jobId: string) => void;
}

function Wizard({ reference, newKey, onCreated }: WizardProps) {
  const [draft, setDraft] = useState(
    () => ProjectDraft.initial().withAttachCompute(reference.networkSettings.attach_compute_by_default));
  const [step, onStep] = useState(0);
  const context: WizardContext = { draft, onChange: setDraft, reference, newKey, onCreated };
  const last = STEPS.length - 1;
  return (
    <>
      <nav className="steps" aria-label="Wizard steps">
        {STEPS.map((item, index) => (
          <button key={item.label} className={`step ${index === step ? "on" : ""}`} aria-current={index === step ? "step" : undefined}
                  onClick={() => onStep(index)}>
            {item.label}
          </button>
        ))}
      </nav>
      <div className="panel">
        <div className="panel-b">{STEPS[step].render(context)}</div>
        <div className="panel-h">
          <button className="btn" disabled={step === 0} onClick={() => onStep(step - 1)}>Back</button>
          {step < last && <button className="btn pri" onClick={() => onStep(step + 1)}>Continue</button>}
        </div>
      </div>
    </>
  );
}
