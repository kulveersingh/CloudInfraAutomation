import { useState } from "react";
import type { ServiceSetting, SettingValue } from "../../../api/types";
import type { DraftResource } from "../../../wizard/ProjectDraft";

type OnSetting = (name: string, value: SettingValue | undefined) => void;

interface FieldProps<Kind extends ServiceSetting["kind"]> {
  resourceId: string;
  setting: Extract<ServiceSetting, { kind: Kind }>;
  current: SettingValue | undefined;
  /** Stores a value, or clears it when it equals the default so the platform default keeps applying. */
  onValue: (value: SettingValue | undefined) => void;
}

/** One field per setting the platform declares for a curated service (§6.4.1). */
export function SettingsEditor({ resource, settings, onSetting }: {
  resource: DraftResource; settings: ServiceSetting[]; onSetting: OnSetting;
}) {
  return (
    <>
      {settings.map((setting) => {
        const props = {
          resourceId: resource.id, current: resource.settings[setting.name],
          onValue: (value: SettingValue | undefined) => onSetting(setting.name, value === setting.default ? undefined : value),
        };
        switch (setting.kind) {
          case "choice": return <ChoiceField key={setting.name} setting={setting} {...props} />;
          case "integer": return <IntegerField key={setting.name} setting={setting} {...props} />;
          case "text": return <TextField key={setting.name} setting={setting} {...props} />;
        }
      })}
    </>
  );
}

function ChoiceField({ resourceId, setting, current, onValue }: FieldProps<"choice">) {
  return (
    <label className="field">
      <span>{setting.label}</span>
      <select aria-label={`${setting.label} for ${resourceId}`} value={current ?? setting.default}
              onChange={(event) => onValue(event.target.value)}>
        {setting.choices.map((choice) => <option key={choice} value={choice}>{choice}</option>)}
      </select>
    </label>
  );
}

function IntegerField({ resourceId, setting, current, onValue }: FieldProps<"integer">) {
  const [text, setText] = useState(String(current ?? setting.default));
  const fits = (candidate: string) => /^\d+$/.test(candidate)
    && Number(candidate) >= setting.minimum && Number(candidate) <= setting.maximum;
  const valid = fits(text);
  const update = (next: string) => {
    setText(next);
    if (fits(next)) onValue(Number(next));
  };
  return (
    <label className="field">
      <span>{setting.label} ({setting.unit})</span>
      <input type="number" aria-label={`${setting.label} for ${resourceId} (${setting.unit})`} min={setting.minimum}
             max={setting.maximum} value={text} onChange={(event) => update(event.target.value)} />
      {!valid && <span className="err">
        {setting.label} must be a whole number from {setting.minimum} to {setting.maximum} {setting.unit}.</span>}
    </label>
  );
}

function TextField({ resourceId, setting, current, onValue }: FieldProps<"text">) {
  const [text, setText] = useState(String(current ?? setting.default ?? ""));
  const pattern = new RegExp(setting.pattern);
  const cleared = (candidate: string) => setting.optional && candidate === "";
  const valid = cleared(text) || pattern.test(text);
  const update = (next: string) => {
    setText(next);
    if (cleared(next)) onValue(undefined);
    else if (pattern.test(next)) onValue(next);
  };
  const optional = setting.optional ? " (optional)" : "";
  return (
    <label className="field">
      <span>{setting.label}{optional}</span>
      <input aria-label={`${setting.label} for ${resourceId}${optional}`} value={text}
             onChange={(event) => update(event.target.value)} />
      {!valid && <span className="err">{setting.label} must be {setting.rule}.</span>}
    </label>
  );
}
