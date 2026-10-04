import { useState } from "react";
import type { AccountInfo, LandingZoneExplanation, OuInfo } from "../../api/types";
import { plural } from "../../landingZone/plural";
import { AccountActions } from "./tree/AccountActions";
import { OuActions, RootActions } from "./tree/OuActions";
import type { TreeEditor } from "./tree/TreeEditor";

interface StructureViewProps {
  explanation: LandingZoneExplanation;
  stage: "Proposed" | "Approved";
  editor?: TreeEditor;
}

/** The OU tree and diagram the platform derived from the answers and edits; editable when given an editor. */
export function StructureView({ explanation, stage, editor }: StructureViewProps) {
  return (
    <div className="split">
      <div className="panel">
        <div className="panel-h"><h3>OU structure</h3><span className="hint">Environment OUs are fixed and isolated</span></div>
        <div className="panel-b">
          {editor && <RootActions editor={editor} />}
          <ul className="tree" role="tree" aria-label={`${stage} OU structure`}>
            {explanation.ous.map((ou) => <OuNode key={ou.key} ou={ou} editor={editor} />)}
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

function OuNode({ ou, editor }: { ou: OuInfo; editor?: TreeEditor }) {
  return (
    <li role="treeitem" aria-selected={false}>
      <span className="ou">
        <b>{ou.name} OU</b>
        {ou.created_by_control_tower && <span className="chip">Control Tower</span>}
        {ou.controls.length > 0 && <span className="chip" title={controlNames(ou)}>{plural(ou.controls.length, "control")}</span>}
        {editor && <OuActions ou={ou} editor={editor} />}
      </span>
      {ou.accounts.length > 0 && (
        <ul className="accounts">
          {ou.accounts.map((account) => <AccountItem key={account.name} account={account} ou={ou} editor={editor} />)}
        </ul>
      )}
      {ou.children.length > 0 && <ul role="group">{ou.children.map((child) => <OuNode key={child.key} ou={child} editor={editor} />)}</ul>}
    </li>
  );
}

function AccountItem({ account, ou, editor }: { account: AccountInfo; ou: OuInfo; editor?: TreeEditor }) {
  return (
    <li className={account.enabled ? "account" : "account off"}>
      <span className="tag">{account.name}</span>
      {!account.enabled && <span className="chip">Disabled</span>}
      {editor && <AccountActions account={account} ou={ou} editor={editor} />}
    </li>
  );
}

function controlNames(ou: OuInfo): string {
  return ou.controls.map((control) => `${control.name} (${control.behavior.toLowerCase()})`).join("\n");
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
