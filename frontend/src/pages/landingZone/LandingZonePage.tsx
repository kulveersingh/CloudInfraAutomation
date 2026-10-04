import { useState, type ReactNode } from "react";
import type { Identity, IndustryTemplate, LandingZoneDesign, LandingZoneReadBack } from "../../api/types";
import { StatusMessage, type SaveStatus } from "../../components/Notices";
import { LandingZoneDraft } from "../../landingZone/LandingZoneDraft";
import { ApprovalsPanel } from "./ApprovalsPanel";
import { AccountsStep } from "./steps/AccountsStep";
import { ControlsStep } from "./steps/ControlsStep";
import { EnvironmentsStep } from "./steps/EnvironmentsStep";
import { InfrastructureStep } from "./steps/InfrastructureStep";
import { NetworkStep } from "./steps/NetworkStep";
import { OrganizationStep } from "./steps/OrganizationStep";
import { ReviewStep } from "./steps/ReviewStep";
import { SandboxStep } from "./steps/SandboxStep";
import { SecurityStep } from "./steps/SecurityStep";
import { LANDING_ZONE_REPOSITORY, StartStep } from "./steps/StartStep";
import type { StepProps } from "./steps/StepProps";

const PLATFORM_ADMIN = "platform-admin";

const STEPS: Array<{ label: string; title: string; render: (props: StepProps) => ReactNode }> = [
  { label: "Start", title: "Start from a template", render: (props) => <StartStep {...props} /> },
  { label: "Organization", title: "Organization", render: (props) => <OrganizationStep {...props} /> },
  { label: "Environments", title: "Environments", render: (props) => <EnvironmentsStep {...props} /> },
  { label: "Accounts", title: "Accounts per environment", render: (props) => <AccountsStep {...props} /> },
  { label: "Security & compliance", title: "Security (Cyber) and compliance", render: (props) => <SecurityStep {...props} /> },
  { label: "Shared infrastructure", title: "Shared infrastructure", render: (props) => <InfrastructureStep {...props} /> },
  { label: "Network", title: "Network", render: (props) => <NetworkStep {...props} /> },
  { label: "Sandbox & other OUs", title: "Sandbox and other OUs", render: (props) => <SandboxStep {...props} /> },
  { label: "Controls", title: "Control Tower controls", render: (props) => <ControlsStep {...props} /> },
  { label: "Review", title: "Review the proposed structure", render: (props) => <ReviewStep {...props} /> },
];

type Tab = "design" | "approvals";

const TABS: Array<{ id: Tab; label: string }> = [{ id: "design", label: "Design" }, { id: "approvals", label: "Approvals" }];

export function LandingZonePage({ identity }: { identity: Identity }) {
  return (
    <section className="page">
      <header className="head">
        <div>
          <h1>Landing zone</h1>
          <p className="sub">Design a new AWS organization: answer the questions, review the proposed OU structure, then
            request approval. A second platform admin's approval commits and applies the CloudFormation.</p>
        </div>
      </header>
      {identity.roles.includes(PLATFORM_ADMIN)
        ? <LandingZoneWorkspace />
        : <p className="notice warn">Only platform admins can design the landing zone.</p>}
    </section>
  );
}

function LandingZoneWorkspace() {
  const [tab, setTab] = useState<Tab>("design");
  const [status, setStatus] = useState<SaveStatus>();
  const submitted = (design: LandingZoneDesign) => {
    setStatus({ kind: "saved", message: `Design v${design.version} submitted. A different platform admin must approve it.` });
    setTab("approvals");
  };
  return (
    <>
      <StatusMessage status={status} />
      <div className="panel">
        <div className="tabs" role="tablist">
          {TABS.map((item) => (
            <button key={item.id} role="tab" aria-selected={item.id === tab} onClick={() => setTab(item.id)}>{item.label}</button>
          ))}
        </div>
        <div className="panel-b">{tab === "design" ? <Questionnaire onSubmitted={submitted} /> : <ApprovalsPanel />}</div>
      </div>
    </>
  );
}

function Questionnaire({ onSubmitted }: { onSubmitted: (design: LandingZoneDesign) => void }) {
  const [draft, setDraft] = useState(LandingZoneDraft.initial);
  const [template, setTemplate] = useState<IndustryTemplate>();
  const [step, setStep] = useState(0);
  const [loaded, setLoaded] = useState<LandingZoneReadBack>();
  const last = STEPS.length - 1;
  const startFrom = (chosen?: IndustryTemplate) => {
    setTemplate(chosen);
    setLoaded(undefined);
    setDraft(chosen ? draft.withTemplate(chosen) : draft.fromScratch());
  };
  const continueFrom = (readBack: LandingZoneReadBack) => {
    setTemplate(undefined);
    setLoaded(readBack);
    setDraft(LandingZoneDraft.fromRequest(readBack.request!));
    setStep(last);
  };
  return (
    <>
      {loaded && <LoadedFromRepository readBack={loaded} />}
      <nav className="steps" aria-label="Questionnaire steps">
        {STEPS.map((item, index) => (
          <button key={item.label} className={`step ${index === step ? "on" : ""}`} aria-current={index === step ? "step" : undefined}
                  onClick={() => setStep(index)}>
            {item.label}
          </button>
        ))}
      </nav>
      <h2>{step === 0 ? STEPS[0].title : `${step}. ${STEPS[step].title}`}</h2>
      {STEPS[step].render({ draft, onChange: setDraft, onSubmitted, template, onTemplate: startFrom,
        onRepository: continueFrom })}
      <div className="row">
        <button className="btn" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
        {step < last && <button className="btn pri" onClick={() => setStep(step + 1)}>Continue</button>}
      </div>
    </>
  );
}

function LoadedFromRepository({ readBack }: { readBack: LandingZoneReadBack }) {
  return (
    <>
      <div role="status" className="notice ok">
        Loaded design v{readBack.design.revision} from {LANDING_ZONE_REPOSITORY} at {readBack.commit_sha?.slice(0, 7)}.
      </div>
      {readBack.findings.map((finding) => <div key={finding.check} className="notice warn">{finding.message}</div>)}
    </>
  );
}
