import { useState } from "react";
import type { LandingZoneExplanation, OuInfo } from "../../api/types";

/** The OU tree and diagram the platform derived from the answers, labelled "Proposed" or "Approved". */
export function StructureView({ explanation, stage }: { explanation: LandingZoneExplanation; stage: "Proposed" | "Approved" }) {
  return (
    <div className="split">
      <div className="panel">
        <div className="panel-h"><h3>OU structure</h3><span className="hint">Environment OUs are fixed and isolated</span></div>
        <div className="panel-b">
          <ul className="tree" role="tree" aria-label={`${stage} OU structure`}>
            {explanation.ous.map((ou) => <OuNode key={ou.key} ou={ou} />)}
          </ul>
        </div>
      </div>
      <div className="panel">
        <div className="panel-h"><h3>Diagram</h3></div>
        <div className="panel-b diagram">
          <img alt={`${stage} OU structure diagram`} src={svgDataUrl(explanation.diagram.svg)} />
        </div>
      </div>
    </div>
  );
}

function OuNode({ ou }: { ou: OuInfo }) {
  return (
    <li role="treeitem" aria-selected={false}>
      <span className="ou">
        <b>{ou.name} OU</b>
        {ou.created_by_control_tower && <span className="chip">Control Tower</span>}
        {ou.accounts.map((account) => <span key={account} className="tag">{account}</span>)}
      </span>
      {ou.children.length > 0 && <ul role="group">{ou.children.map((child) => <OuNode key={child.key} ou={child} />)}</ul>}
    </li>
  );
}

function svgDataUrl(svg: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

/** The repository files the approval would commit; one is shown at a time. */
export function GeneratedFiles({ files }: { files: Record<string, string> }) {
  const paths = Object.keys(files);
  const [selected, setSelected] = useState(paths[0]);
  return (
    <div className="panel">
      <div className="panel-h"><h3>Files committed to the landing zone repository after approval</h3></div>
      <div className="panel-b">
        <div className="row wrap">
          {paths.map((path) => (
            <button key={path} className={`btn ghost mono ${path === selected ? "on" : ""}`} aria-pressed={path === selected}
                    onClick={() => setSelected(path)}>{path}</button>
          ))}
        </div>
        <pre className="file" aria-label="File content">{files[selected]}</pre>
      </div>
    </div>
  );
}
