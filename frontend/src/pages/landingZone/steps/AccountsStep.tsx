import type { LandingZoneAnswers } from "../../../api/types";
import { Choices, type Choice } from "../controls";
import type { StepProps } from "./StepProps";

const MODELS: Array<Choice<LandingZoneAnswers["account_model"]>> = [
  { value: "environment", title: "One account per environment",
    description: "Simplest. Every product shares the environment's account and its service quotas." },
  { value: "portfolio", title: "One per portfolio per environment", recommended: true,
    description: "An account boundary between portfolios. Tags isolate products and projects inside it." },
  { value: "product", title: "One per product per environment",
    description: "The strongest isolation and the most accounts. Suits regulated or very large products." },
];

export function AccountsStep({ draft, onChange }: StepProps) {
  return (
    <>
      <p className="sub">Accounts are created through Control Tower Account Factory, already enrolled in their
        environment OU.</p>
      <Choices label="How many accounts per environment?" choices={MODELS} selected={draft.toAnswers().account_model}
               onSelect={(model) => onChange(draft.with({ account_model: model }))} />
    </>
  );
}
