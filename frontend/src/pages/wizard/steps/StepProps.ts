import type { CatalogEntry, EnvironmentInfo, NetworkSettings, Portfolio, RegionInfo } from "../../../api/types";
import type { ProjectDraft } from "../../../wizard/ProjectDraft";

export interface ReferenceData {
  portfolios: Portfolio[];
  environments: EnvironmentInfo[];
  regions: RegionInfo[];
  catalog: CatalogEntry[];
  networkSettings: NetworkSettings;
}

/** The project being changed (§21.8): what it was read back at, and what may not change. */
export interface ChangeBase {
  projectName: string;
  baseCommit: string;
  revision: number;
  /** Environments the project already has; they can be kept but not removed. */
  environments: string[];
}

export interface StepProps {
  draft: ProjectDraft;
  onChange: (draft: ProjectDraft) => void;
  reference: ReferenceData;
  /** Set when changing an existing project: name, ownership, classification and resilience are locked. */
  change?: ChangeBase;
}
