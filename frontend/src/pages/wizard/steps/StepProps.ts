import type { CatalogEntry, EnvironmentInfo, Portfolio, RegionInfo } from "../../../api/types";
import type { ProjectDraft } from "../../../wizard/ProjectDraft";

export interface ReferenceData {
  portfolios: Portfolio[];
  environments: EnvironmentInfo[];
  regions: RegionInfo[];
  catalog: CatalogEntry[];
}

export interface StepProps {
  draft: ProjectDraft;
  onChange: (draft: ProjectDraft) => void;
  reference: ReferenceData;
}
