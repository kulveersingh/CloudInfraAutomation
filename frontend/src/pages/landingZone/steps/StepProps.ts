import type { IndustryTemplate, LandingZoneDesign, LandingZoneReadBack } from "../../../api/types";
import type { LandingZoneDraft } from "../../../landingZone/LandingZoneDraft";

export interface StepProps {
  draft: LandingZoneDraft;
  onChange: (draft: LandingZoneDraft) => void;
  onSubmitted: (design: LandingZoneDesign) => void;
  /** The industry template the design started from, if any. */
  template?: IndustryTemplate;
  /** Starts the design from a template, or from scratch when none is given. */
  onTemplate: (template?: IndustryTemplate) => void;
  /** Continues from the design committed to the repository, once read back and verified. */
  onRepository: (readBack: LandingZoneReadBack) => void;
}
