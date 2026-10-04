import { useState } from "react";
import { useApi } from "../../api/ApiContext";
import type { RegionInfo } from "../../api/types";
import { ErrorAlert } from "../../components/Notices";
import { useLoad } from "../../hooks/useLoad";

export function RegionsPanel() {
  const api = useApi();
  const regions = useLoad(() => api.regions());
  const [saved, setSaved] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string>();

  const toggle = async (region: RegionInfo, enabled: boolean) => {
    try {
      const updated = await api.setRegionEnabled(region.id, enabled);
      setSaved((current) => ({ ...current, [updated.id]: updated.enabled }));
      setError(undefined);
    } catch (failure) {
      setError((failure as Error).message);
    }
  };

  return (
    <div className="stack">
      <ErrorAlert message={regions.error ?? error} />
      {regions.data && (
        <div className="tbl-wrap">
          <table>
            <thead><tr><th>Region</th><th>Name</th><th>Enabled</th></tr></thead>
            <tbody>
              {regions.data.map((region) => (
                <tr key={region.id}>
                  <td className="mono">{region.id}</td>
                  <td>{region.name}</td>
                  <td>
                    <input type="checkbox" aria-label={`Enable ${region.id}`} checked={saved[region.id] ?? region.enabled}
                           onChange={(event) => toggle(region, event.target.checked)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="hint">Enabled regions appear in the project wizard. Any pair of enabled regions can be a DR/HA pair.</p>
    </div>
  );
}
