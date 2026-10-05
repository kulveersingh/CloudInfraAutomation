import { useApi } from "../../../api/ApiContext";
import type { NetworkOption } from "../../../api/types";
import { ErrorAlert } from "../../../components/Notices";
import { useLoad } from "../../../hooks/useLoad";
import { useVocabulary } from "../../../providers/VocabularyContext";
import type { ProjectDraft } from "../../../wizard/ProjectDraft";

interface NetworkStepProps {
  draft: ProjectDraft;
  onChange: (draft: ProjectDraft) => void;
}

export function NetworkStep({ draft, onChange }: NetworkStepProps) {
  const { portfolioId, attachCompute } = draft.values;
  const words = useVocabulary();
  return (
    <>
      <h2>Network</h2>
      <p className="sub">Compute (for example Lambda) runs in private subnets of the organization {words.private_network} and can reach other
        services in the organization's private range without opening ports one by one.</p>
      <label className="row">
        <input type="checkbox" checked={attachCompute} onChange={(event) => onChange(draft.withAttachCompute(event.target.checked))} />
        Attach compute to the organization {words.private_network}
      </label>
      {!attachCompute && <p className="hint">Compute will run outside the {words.private_network} with {words.cloud}-managed
        networking.</p>}
      {attachCompute && (portfolioId
        ? <NetworkChoices draft={draft} onChange={onChange} />
        : <p className="notice warn">Choose a portfolio first.</p>)}
    </>
  );
}

function NetworkChoices({ draft, onChange }: NetworkStepProps) {
  const api = useApi();
  const options = useLoad(() => api.networkOptions(draft.values.portfolioId));
  const targets = draft.values.environments.flatMap(
    (environment) => draft.regionsFor(environment).map((region) => ({ environment, region })));

  if (targets.length === 0) return <p className="notice warn">Select environments first.</p>;
  const data = options.data;
  return (
    <>
      <ErrorAlert message={options.error} />
      {data && (
        <div className="tbl-wrap">
          <table>
            <thead><tr><th>Environment</th><th>Region</th><th>Network</th></tr></thead>
            <tbody>
              {targets.map(({ environment, region }) => (
                <tr key={`${environment}:${region}`}>
                  <td>{environment}</td>
                  <td className="mono">{region}</td>
                  <td>
                    <NetworkSelect option={data.find((item) => item.environment === environment && item.region === region)}
                                   environment={environment} region={region} draft={draft} onChange={onChange} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

interface NetworkSelectProps extends NetworkStepProps {
  option: NetworkOption | undefined;
  environment: string;
  region: string;
}

function NetworkSelect({ option, environment, region, draft, onChange }: NetworkSelectProps) {
  if (!option || option.networks.length === 0) {
    return <span className="err">No network is configured for {environment} in {region}. Ask a platform admin to add one.</span>;
  }
  const selected = draft.values.networkSelections[`${environment}:${region}`] ?? option.default_network_id ?? option.networks[0].id;
  return (
    <select aria-label={`Network for ${environment} in ${region}`} value={selected}
            onChange={(event) => onChange(draft.withNetworkSelection(environment, region, event.target.value))}>
      {option.networks.map((network) => (
        <option key={network.id} value={network.id}>{`${network.name} · ${network.network_ref} · ${network.cidr}`}</option>
      ))}
    </select>
  );
}
