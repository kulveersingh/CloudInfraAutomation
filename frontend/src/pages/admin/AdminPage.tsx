import { useState, type ReactNode } from "react";
import { CostCentersPanel } from "./CostCentersPanel";
import { RegionsPanel } from "./RegionsPanel";

const TABS: Array<{ id: string; label: string; panel: () => ReactNode }> = [
  { id: "cost-centers", label: "Cost centers", panel: () => <CostCentersPanel /> },
  { id: "regions", label: "Regions", panel: () => <RegionsPanel /> },
];

export function AdminPage() {
  const [selected, setSelected] = useState(TABS[0]);
  return (
    <section className="page">
      <header className="head">
        <div>
          <h1>Admin</h1>
          <p className="sub">Organization settings. Changes are versioned and audited.</p>
        </div>
      </header>
      <div className="panel">
        <div className="tabs" role="tablist">
          {TABS.map((tab) => (
            <button key={tab.id} role="tab" aria-selected={tab.id === selected.id} onClick={() => setSelected(tab)}>
              {tab.label}
            </button>
          ))}
        </div>
        <div className="panel-b">{selected.panel()}</div>
      </div>
    </section>
  );
}
