import { useState } from "react";
import { useApi } from "../../api/ApiContext";
import type { CostCenterChange, CostCenterSettings, CostCenterValue } from "../../api/types";
import { ErrorAlert, StatusMessage, type SaveStatus } from "../../components/Notices";
import { useLoad } from "../../hooks/useLoad";

const SOURCE_LABELS: Record<string, string> = {
  project: "project override",
  product: "set on product",
  portfolio: "inherited from portfolio",
  organization: "organization default",
};

type Level = "portfolio" | "product";
type Entry = [id: string, original: string | null];

function sourceLabel(effective: CostCenterValue, level: Level): string {
  const label = effective.source === level ? `set on ${level}` : SOURCE_LABELS[effective.source];
  return `${effective.value} · ${label}`;
}

function fieldKey(level: Level, id: string): string {
  return `${level}:${id}`;
}

function changedValues(entries: Entry[], values: Record<string, string>, level: Level): Record<string, string | null> {
  return Object.fromEntries(entries
    .filter(([id, original]) => values[fieldKey(level, id)] !== (original ?? ""))
    .map(([id]) => [id, values[fieldKey(level, id)] || null]));
}

/** Builds the minimal change set between the loaded settings and the edited form values. */
export function costCenterChange(initial: CostCenterSettings, values: Record<string, string>): CostCenterChange {
  const change: CostCenterChange = {};
  if (values.default !== initial.default) change.default = values.default;
  const portfolios = changedValues(initial.portfolios.map((p) => [p.id, p.cost_center]), values, "portfolio");
  const products = changedValues(
    initial.portfolios.flatMap((p) => p.products.map((product): Entry => [product.id, product.cost_center])),
    values, "product");
  if (Object.keys(portfolios).length > 0) change.portfolios = portfolios;
  if (Object.keys(products).length > 0) change.products = products;
  return change;
}

function initialValues(settings: CostCenterSettings): Record<string, string> {
  const values: Record<string, string> = { default: settings.default };
  for (const portfolio of settings.portfolios) {
    values[fieldKey("portfolio", portfolio.id)] = portfolio.cost_center ?? "";
    for (const product of portfolio.products) {
      values[fieldKey("product", product.id)] = product.cost_center ?? "";
    }
  }
  return values;
}

export function CostCentersPanel() {
  const api = useApi();
  const settings = useLoad(() => api.costCenters());
  return (
    <>
      <ErrorAlert message={settings.error} />
      {settings.data && <CostCentersForm initial={settings.data} />}
    </>
  );
}

function CostCentersForm({ initial }: { initial: CostCenterSettings }) {
  const api = useApi();
  const [values, setValues] = useState(() => initialValues(initial));
  const [status, setStatus] = useState<SaveStatus>();
  const update = (key: string, value: string) => setValues((current) => ({ ...current, [key]: value }));

  const save = async () => {
    try {
      await api.updateCostCenters(costCenterChange(initial, values));
      setStatus({ kind: "saved", message: "Saved. Tags update on each project's next deploy." });
    } catch (error) {
      setStatus({ kind: "error", message: (error as Error).message });
    }
  };

  return (
    <div className="stack">
      <div className="grid3">
        <div className="field">
          <label htmlFor="cc-default">Organization default</label>
          <input id="cc-default" value={values.default} onChange={(event) => update("default", event.target.value)} />
          <span className="hint">Used when no portfolio or product value is set</span>
        </div>
        <div className="field">
          <span className="label">Format rule</span>
          <span className="mono">{initial.pattern}</span>
        </div>
        <div className="field">
          <span className="label">Resolution order</span>
          <span className="muted">Project override → product → portfolio → organization default</span>
        </div>
      </div>
      <div className="tbl-wrap">
        <table>
          <thead><tr><th>Portfolio / product</th><th>Cost center</th><th>Effective</th></tr></thead>
          <tbody>
            {initial.portfolios.map((portfolio) => (
              <PortfolioRows key={portfolio.id} portfolio={portfolio} values={values} update={update} />
            ))}
          </tbody>
        </table>
      </div>
      <StatusMessage status={status} />
      <div className="row"><button className="btn pri" onClick={save}>Save cost centers</button></div>
    </div>
  );
}

interface RowsProps {
  portfolio: CostCenterSettings["portfolios"][number];
  values: Record<string, string>;
  update: (key: string, value: string) => void;
}

function PortfolioRows({ portfolio, values, update }: RowsProps) {
  return (
    <>
      <CostCenterRow name={portfolio.name} fieldId={fieldKey("portfolio", portfolio.id)} level="portfolio"
                     effective={portfolio.effective} values={values} update={update} />
      {portfolio.products.map((product) => (
        <CostCenterRow key={product.id} name={product.name} fieldId={fieldKey("product", product.id)} level="product"
                       effective={product.effective} values={values} update={update} />
      ))}
    </>
  );
}

interface RowProps {
  name: string;
  fieldId: string;
  level: Level;
  effective: CostCenterValue;
  values: Record<string, string>;
  update: (key: string, value: string) => void;
}

function CostCenterRow({ name, fieldId, level, effective, values, update }: RowProps) {
  return (
    <tr className={level === "product" ? "indented" : undefined}>
      <td>{name}</td>
      <td>
        <input aria-label={`Cost center for ${name}`} value={values[fieldId]} placeholder={`inherit (${effective.value})`}
               onChange={(event) => update(fieldId, event.target.value)} />
      </td>
      <td className="mono">{sourceLabel(effective, level)}</td>
    </tr>
  );
}
