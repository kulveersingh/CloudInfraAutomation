import type { LandingZoneDesign } from "../../../api/types";
import type { LandingZoneDraft } from "../../../landingZone/LandingZoneDraft";

export interface StepProps {
  draft: LandingZoneDraft;
  onChange: (draft: LandingZoneDraft) => void;
  onSubmitted: (design: LandingZoneDesign) => void;
}
