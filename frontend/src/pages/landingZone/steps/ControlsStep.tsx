import type { LandingZoneAnswers } from "../../../api/types";
import { Choices, type Choice } from "../controls";
import type { StepProps } from "./StepProps";

const PROFILES: Array<Choice<LandingZoneAnswers["controls_profile"]>> = [
  { value: "baseline", title: "Baseline", description: "Mandatory controls plus root-user restrictions." },
  { value: "recommended", title: "Strongly recommended", recommended: true,
    description: "Baseline plus no public S3 or RDS, encryption at rest, MFA, restricted ports and tamper detection on "
      + "production tiers." },
  { value: "regulated", title: "Regulated",
    description: "Strongly recommended plus the Security Hub standards for your compliance scopes and stricter data perimeters." },
];

export function ControlsStep({ draft, onChange }: StepProps) {
  return (
    <>
      <p className="sub">The starting set of Control Tower controls. Mandatory Control Tower controls are always on.</p>
      <Choices label="Controls profile" choices={PROFILES} selected={draft.toAnswers().controls_profile}
               onSelect={(profile) => onChange(draft.with({ controls_profile: profile }))} />
    </>
  );
}
