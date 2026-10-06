import { useState } from "react";
import type { FlowException, LandingZoneAnswers } from "../../../api/types";
import type { LandingZoneDraft, LandingZoneEnvironment } from "../../../landingZone/LandingZoneDraft";
import { Checkbox, Choices, type Choice } from "../controls";
import type { StepProps } from "./StepProps";

type Network = LandingZoneAnswers["network"];

const TOPOLOGIES: Array<Choice<boolean>> = [
  { value: true, title: "Hub and spoke (Transit Gateway)", recommended: true,
    description: "A central Network account; each environment VPC attaches to the hub." },
  { value: false, title: "Isolated VPCs only", description: "No hub. Environments can't reach Shared Services privately." },
];

export function NetworkStep({ draft, onChange }: StepProps) {
  const { network } = draft.toAnswers();
  const change = (update: Partial<Network>) => onChange(draft.withNetwork(update));
  return (
    <>
      <Choices label="Topology" choices={TOPOLOGIES} selected={network.hub} onSelect={(hub) => change({ hub })} />
      <div className="grid3">
        <div className="field">
          <label htmlFor="lz-cidr">Organization CIDR</label>
          <input type="text" id="lz-cidr" value={network.cidr} onChange={(event) => change({ cidr: event.target.value })} />
          <span className="hint">IPAM splits it into non-overlapping pools per environment and region</span>
        </div>
        <div className="field">
          <label htmlFor="lz-egress">Internet egress</label>
          <select id="lz-egress" value={network.egress} onChange={(event) => change({ egress: event.target.value as Network["egress"] })}>
            <option value="central">Central egress VPC (recommended)</option>
            <option value="local">NAT in each VPC</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="lz-on-premises">On-premises connection</label>
          <select id="lz-on-premises" value={network.on_premises}
                  onChange={(event) => change({ on_premises: event.target.value as Network["on_premises"] })}>
            <option value="none">None</option>
            <option value="vpn">Site-to-site VPN</option>
            <option value="dedicated">Direct Connect</option>
          </select>
        </div>
      </div>
      <Checkbox label="Inspect traffic with AWS Network Firewall" hint="Required for any cross-environment flow"
                checked={network.inspection} onChange={(inspection) => change({ inspection })} />
      <FlowExceptions draft={draft} onChange={onChange} />
    </>
  );
}

interface FlowExceptionsProps {
  draft: LandingZoneDraft;
  onChange: (draft: LandingZoneDraft) => void;
}

function FlowExceptions({ draft, onChange }: FlowExceptionsProps) {
  const environments = draft.environments().filter((environment) => environment.tier !== "sandbox");
  const names = Object.fromEntries(environments.map((environment) => [environment.id, environment.name]));
  return (
    <div className="field">
      <span className="label">Cross-environment exceptions</span>
      <table>
        <thead><tr><th>Flow</th><th>Port</th><th>Reason</th><th /></tr></thead>
        <tbody>
          {draft.toAnswers().network.flows.map((flow, index) => (
            <tr key={index}>
              <td><b>{names[flow.source]}</b> → <b>{names[flow.destination]}</b></td>
              <td className="mono">{flow.protocol}/{flow.port}</td>
              <td>{flow.reason}</td>
              <td><button className="btn ghost" aria-label={`Remove flow ${index + 1}`}
                          onClick={() => onChange(draft.withoutFlow(index))}>Remove</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <FlowForm environments={environments} onAdd={(flow) => onChange(draft.withFlow(flow))} />
      <span className="hint">None by default: environments are fully isolated. Each exception is a single port, routed
        only through the inspection VPC, and is approved with the design.</span>
    </div>
  );
}

function FlowForm({ environments, onAdd }: { environments: LandingZoneEnvironment[]; onAdd: (flow: FlowException) => void }) {
  const [source, setSource] = useState(environments[0].id);
  const [destination, setDestination] = useState(environments[1].id);
  const [protocol, setProtocol] = useState<FlowException["protocol"]>("tcp");
  const [port, setPort] = useState("5432");
  const [reason, setReason] = useState("");
  const options = environments.map((environment) => (
    <option key={environment.id} value={environment.id}>{environment.name}</option>));
  return (
    <div className="row">
      <select aria-label="Flow source" value={source} onChange={(event) => setSource(event.target.value)}>{options}</select>
      <span>→</span>
      <select aria-label="Flow destination" value={destination} onChange={(event) => setDestination(event.target.value)}>{options}</select>
      <select aria-label="Flow protocol" value={protocol}
              onChange={(event) => setProtocol(event.target.value as FlowException["protocol"])}>
        <option>tcp</option>
        <option>udp</option>
      </select>
      <input type="text" inputMode="numeric" aria-label="Flow port" value={port} onChange={(event) => setPort(event.target.value)} />
      <input type="text" aria-label="Flow reason" value={reason} onChange={(event) => setReason(event.target.value)} />
      <button className="btn" disabled={reason.trim() === ""}
              onClick={() => onAdd({ source, destination, protocol, port: Number(port), reason })}>Add exception</button>
    </div>
  );
}
