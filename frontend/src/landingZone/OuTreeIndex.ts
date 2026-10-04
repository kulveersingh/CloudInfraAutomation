import type { OuInfo } from "../api/types";

/** Lookups over the proposed OU tree: names by key, and where an OU or account may move inside its isolation domain. */
export class OuTreeIndex {
  private readonly ous: OuInfo[] = [];
  private readonly parents = new Map<string, string>();

  constructor(roots: OuInfo[]) {
    this.add(roots);
  }

  name(key: string): string {
    return this.ous.find((ou) => ou.key === key)?.name ?? key;
  }

  ouTargets(ou: OuInfo): OuInfo[] {
    const excluded = new Set([ou.key, this.parents.get(ou.key), ...descendantKeys(ou)]);
    return this.inDomain(ou).filter((target) => target.allowed_edits.includes("add_child") && !excluded.has(target.key));
  }

  accountTargets(ou: OuInfo): OuInfo[] {
    return this.inDomain(ou).filter((target) => target.allowed_edits.includes("add_account") && target.key !== ou.key);
  }

  private inDomain(ou: OuInfo): OuInfo[] {
    return this.ous.filter((candidate) => candidate.domain === ou.domain);
  }

  private add(ous: OuInfo[]) {
    for (const ou of ous) {
      this.ous.push(ou);
      ou.children.forEach((child) => this.parents.set(child.key, ou.key));
      this.add(ou.children);
    }
  }
}

function descendantKeys(ou: OuInfo): string[] {
  return ou.children.flatMap((child) => [child.key, ...descendantKeys(child)]);
}
