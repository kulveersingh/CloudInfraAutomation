import type { CloudProviderInfo } from "../api/types";

interface CloudPickerProps {
  providers: CloudProviderInfo[];
  value: string;
  onChange: (provider: CloudProviderInfo) => void;
  disabled?: boolean;
}

/** Chooses one of the clouds the platform supports (§22.9.6). Shown once the clouds have loaded. */
export function CloudPicker({ providers, value, onChange, disabled = false }: CloudPickerProps) {
  if (providers.length === 0) return null;
  return (
    <div className="field">
      <label htmlFor="cloud">Cloud</label>
      <select id="cloud" value={value} disabled={disabled}
              onChange={(event) => onChange(providers.find((provider) => provider.id === event.target.value)!)}>
        {providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}
      </select>
    </div>
  );
}
