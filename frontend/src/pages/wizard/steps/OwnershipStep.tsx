import type { Classification, Portfolio } from "../../../api/types";
import { CloudPicker } from "../../../components/CloudPicker";
import type { StepProps } from "./StepProps";

const CLASSIFICATIONS: Classification[] = ["public", "internal", "confidential", "restricted"];

export function OwnershipStep({ draft, onChange, reference, change }: StepProps) {
  const locked = change !== undefined;
  const { portfolioId, productId, name, classification } = draft.values;
  const products = findPortfolio(reference.portfolios, portfolioId)?.products ?? [];
  const product = products.find((item) => item.id === productId);
  return (
    <>
      <h2>Ownership</h2>
      <div className="grid3">
        <CloudPicker providers={reference.providers} value={draft.values.provider} disabled={locked}
                     onChange={(provider) => onChange(draft.withProvider(provider))} />
      </div>
      {!locked && <p className="hint">Changing the cloud clears the services, connections and networks chosen so far.</p>}
      <div className="grid3">
        <div className="field">
          <label htmlFor="portfolio">Portfolio</label>
          <select id="portfolio" value={portfolioId} disabled={locked} onChange={(event) => onChange(draft.withOwnership(event.target.value, ""))}>
            <option value="">Choose…</option>
            {reference.portfolios.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="product">Product / Platform</label>
          <select id="product" value={productId} disabled={locked} onChange={(event) => onChange(draft.withOwnership(portfolioId, event.target.value))}>
            <option value="">Choose…</option>
            {products.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.kind})</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="project-name">Project name</label>
          <input id="project-name" value={name} autoComplete="off" disabled={locked} onChange={(event) => onChange(draft.withName(event.target.value))} />
          <span className="hint">Becomes the repository name and the org:project tag</span>
        </div>
      </div>
      <div className="grid3">
        <div className="field">
          <label htmlFor="classification">Data classification</label>
          <select id="classification" value={classification} disabled={locked}
                  onChange={(event) => onChange(draft.withClassification(event.target.value as Classification))}>
            {CLASSIFICATIONS.map((item) => <option key={item}>{item}</option>)}
          </select>
        </div>
        <div className="field">
          <span className="label">Cost center</span>
          <span className="mono">{product ? `${product.cost_center.value} · ${product.cost_center.source}` : "—"}</span>
        </div>
      </div>
    </>
  );
}

function findPortfolio(portfolios: Portfolio[], portfolioId: string): Portfolio | undefined {
  return portfolios.find((portfolio) => portfolio.id === portfolioId);
}
