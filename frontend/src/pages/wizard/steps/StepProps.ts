import type {
  CatalogEntry, CloudProviderInfo, EnvironmentInfo, NetworkSettings, Portfolio, RegionInfo,
} from "../../../api/types";
import type { ProjectDraft } from "../../../wizard/ProjectDraft";

export interface ReferenceData {
  providers: CloudProviderInfo[];
  portfolios: Portfolio[];
  environments: EnvironmentInfo[];
  /** Every cloud's regions; each step shows the chosen cloud's. */
  regions: RegionInfo[];
  /** Each cloud's curated services, by cloud id. */
  catalogs: Record<string, CatalogEntry[]>;
  networkSettings: NetworkSettings;
}

/** The chosen cloud's provider entry (AWS until the clouds have loaded). */
export function chosenCloud(reference: ReferenceData, provider: string): CloudProviderInfo | undefined {
  return reference.providers.find((item) => item.id === provider);
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
