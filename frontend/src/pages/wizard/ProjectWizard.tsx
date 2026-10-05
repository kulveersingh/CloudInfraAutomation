import { useState, type ReactNode } from "react";
import type { PlatformApiPort, ProjectChange } from "../../api/types";
import type { ProjectDraft } from "../../wizard/ProjectDraft";
import { ChangePreviewStep } from "./steps/ChangePreviewStep";
import { ConnectionsStep } from "./steps/ConnectionsStep";
import { EnvironmentsStep } from "./steps/EnvironmentsStep";
import { NetworkStep } from "./steps/NetworkStep";
import { OwnershipStep } from "./steps/OwnershipStep";
import { PreviewStep } from "./steps/PreviewStep";
import { ResilienceStep } from "./steps/ResilienceStep";
import { ServicesStep } from "./steps/ServicesStep";
import type { ChangeBase, ReferenceData, StepProps } from "./steps/StepProps";

/** New projects are created; existing ones are changed through a pull request (§21.8). */
export type WizardMode =
  | { kind: "new"; newKey: () => string; onCreated: (jobId: string) => void }
  | { kind: "change"; base: ChangeBase; onOpened: (change: ProjectChange) => void };

interface WizardContext extends StepProps {
  mode: WizardMode;
}

const STEPS: Array<{ label: string; render: (context: WizardContext) => ReactNode }> = [
  { label: "Ownership", render: (context) => <OwnershipStep {...context} /> },
  { label: "Resilience", render: (context) => <ResilienceStep {...context} /> },
  { label: "Services", render: (context) => <ServicesStep {...context} /> },
  { label: "Connections", render: (context) => <ConnectionsStep {...context} /> },
  { label: "Environments", render: (context) => <EnvironmentsStep {...context} /> },
  { label: "Network", render: (context) => <NetworkStep {...context} /> },
  { label: "Preview", render: ({ draft, mode }) => (mode.kind === "new"
    ? <PreviewStep draft={draft} newKey={mode.newKey} onCreated={mode.onCreated} />
    : <ChangePreviewStep draft={draft} base={mode.base} onOpened={mode.onOpened} />) },
];

export async function loadReferenceData(api: PlatformApiPort): Promise<ReferenceData> {
  const [providers, portfolios, environments, regions, networkSettings] = await Promise.all([
    api.providers(), api.orgRegistry(), api.environments(), api.regions(), api.networkSettings()]);
  const catalogs = await Promise.all(providers.map((provider) => api.catalog(provider.id)));
  return { providers, portfolios, environments, regions, networkSettings,
    catalogs: Object.fromEntries(providers.map((provider, index) => [provider.id, catalogs[index]])) };
}

export function ProjectWizard({ reference, initial, mode }: { reference: ReferenceData; initial: ProjectDraft; mode: WizardMode }) {
  const [draft, setDraft] = useState(initial);
  const [step, onStep] = useState(0);
  const change = mode.kind === "change" ? mode.base : undefined;
  const context: WizardContext = { draft, onChange: setDraft, reference, change, mode };
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
