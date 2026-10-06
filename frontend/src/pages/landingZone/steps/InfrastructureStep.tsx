import { cloudText } from "../../../landingZone/cloudText";
import { Checkbox } from "../controls";
import type { StepProps } from "./StepProps";

export function InfrastructureStep({ draft, onChange }: StepProps) {
  const { infrastructure } = draft.toAnswers();
  const text = cloudText(draft.provider);
  return (
    <>
      <p className="sub">{text.sharedUnitsIntro}</p>
      {text.sharedUnits.map((unit) => (
        <Checkbox key={unit.id} label={unit.label} hint={unit.hint} checked={infrastructure.includes(unit.id)}
                  onChange={(checked) => onChange(draft.withListItem("infrastructure", unit.id, checked))} />
      ))}
    </>
  );
}
