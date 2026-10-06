import type { ResilienceMode } from "../api/types";

/** A cloud's fixed region pairs: where geo-redundant storage replicates (Azure, MC4-4). Empty on other clouds. */
export class RegionPairs {
  /** No pairs until the cloud's description has loaded. */
  constructor(private readonly pairs: Record<string, string> = {}, private readonly enabled: string[] = []) {}

  /** The secondary region after the primary changes: the new primary's pair, if it has an enabled one. */
  secondaryFor(primary: string, current: string): string {
    const pair = this.pairs[primary];
    return pair !== undefined && this.enabled.includes(pair) ? pair : current;
  }

  hint(mode: ResilienceMode, primary: string): string | undefined {
    const pair = this.pairs[primary];
    return mode !== "single" && pair !== undefined ? `Storage replicates to ${primary}'s pair, ${pair}.` : undefined;
  }

  /** Why the regions don't suit a project with storage, which can only replicate to the primary's pair. */
  problem(mode: ResilienceMode, primary: string, secondary: string, hasStorage: boolean): string | undefined {
    if (mode === "single" || !hasStorage || Object.keys(this.pairs).length === 0) return undefined;
    const pair = this.pairs[primary];
    if (pair === undefined) {
      return `Storage cannot replicate from ${primary}: it has no pair. Choose another primary region, or remove the storage.`;
    }
    return secondary === pair ? undefined
      : `Storage can only replicate to ${primary}'s pair: choose ${pair} as the secondary region, or remove the storage.`;
  }
}
