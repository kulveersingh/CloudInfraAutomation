import { useState } from "react";
import { useApi } from "../../api/ApiContext";
import type { LandingZoneDesign, LandingZoneStatus } from "../../api/types";
import { ErrorAlert, StatusMessage, type SaveStatus } from "../../components/Notices";
import { useLoad } from "../../hooks/useLoad";
import { EditDescriber } from "../../landingZone/EditDescriber";
import { OuTreeIndex } from "../../landingZone/OuTreeIndex";
import { StructureView } from "./StructureView";
import { ManualChanges } from "./tree/ManualChanges";

const STATUS_LABELS: Record<LandingZoneStatus, string> = {
  draft: "Draft", pending_approval: "Awaiting second admin", applied: "Applied", rejected: "Rejected",
};

export function ApprovalsPanel() {
  const api = useApi();
  const designs = useLoad(() => api.landingZoneDesigns());
  const [status, setStatus] = useState<SaveStatus>();
  const [viewing, setViewing] = useState<LandingZoneDesign>();

  const decided = (design: LandingZoneDesign, message: string) => {
    setStatus({ kind: "saved", message });
    setViewing(design);
    designs.reload();
  };

  return (
    <>
      <StatusMessage status={status} />
      <ErrorAlert message={designs.error} />
      {designs.data?.length === 0 && <p className="empty">No landing zone designs yet.</p>}
      <ul className="inbox">
        {designs.data?.map((design) => (
          <DesignRow key={design.id} design={design} onView={() => setViewing(design)} onDecided={decided}
                     onFailed={(message) => setStatus({ kind: "error", message })} />
        ))}
      </ul>
      {viewing && <DesignDetail key={`${viewing.id}:${viewing.status}`} design={viewing} />}
    </>
  );
}

interface DesignRowProps {
  design: LandingZoneDesign;
  onView: () => void;
  onDecided: (design: LandingZoneDesign, message: string) => void;
  onFailed: (message: string) => void;
}

function DesignRow({ design, onView, onDecided, onFailed }: DesignRowProps) {
  const api = useApi();
  const [comment, setComment] = useState("");
  const version = `v${design.version}`;

  const approve = async () => {
    const applied = await api.approveLandingZoneDesign(design.id, comment);
    onDecided(applied, `Design ${version} applied. Committed to ${applied.repository}.`);
  };
  const reject = async () => {
    onDecided(await api.rejectLandingZoneDesign(design.id, comment), `Design ${version} rejected.`);
  };
  const decide = (decision: () => Promise<void>) => decision().catch((failure: Error) => onFailed(failure.message));

  return (
    <li className="row">
      <span className={`chip ${design.status}`}>{STATUS_LABELS[design.status]}</span>
      <b>{design.organization_name}</b>
      <span className="muted">{version} · by {design.created_by}</span>
      <button className="btn ghost" aria-label={`View ${version}`} onClick={onView}>View</button>
      {design.status === "pending_approval" && (
        <>
          <input type="text" aria-label={`Comment for ${version}`} placeholder="Comment" value={comment}
                 onChange={(event) => setComment(event.target.value)} />
          <button className="btn pri" aria-label={`Approve ${version}`} onClick={() => decide(approve)}>Approve</button>
          <button className="btn" aria-label={`Reject ${version}`} onClick={() => decide(reject)}>Reject</button>
        </>
      )}
    </li>
  );
}

/** Loads the design's OU structure; the status, repository and accounts come from the latest decision. */
function DesignDetail({ design }: { design: LandingZoneDesign }) {
  const api = useApi();
  const detail = useLoad(() => api.landingZoneDesign(design.id));
  const applied = design.status === "applied";
  return (
    <div className="panel">
      <div className="panel-h">
        <h3>{design.organization_name} · v{design.version}</h3>
        {applied && (
          <span className="row">
            <span className="mono">{design.repository}</span>
            <span className="hint">{Object.keys(design.accounts).length} accounts</span>
          </span>
        )}
      </div>
      <div className="panel-b">
        <ErrorAlert message={detail.error} />
        {detail.data && (
          <>
            <StructureView explanation={detail.data} stage={applied ? "Approved" : "Proposed"} />
            <ManualChanges edits={detail.data.edits} describer={new EditDescriber(new OuTreeIndex(detail.data.ous))} />
          </>
        )}
      </div>
    </div>
  );
}
