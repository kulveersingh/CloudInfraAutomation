import { useState } from "react";

export interface Choice<T> {
  value: T;
  title: string;
  description: string;
  recommended?: boolean;
}

interface ChoicesProps<T> {
  label: string;
  choices: Array<Choice<T>>;
  /** Nothing is pressed when the current answer matches no choice (e.g. a custom environment combination). */
  selected: T | undefined;
  onSelect: (value: T) => void;
}

/** A row of option cards; the platform's recommendation is badged. */
export function Choices<T>({ label, choices, selected, onSelect }: ChoicesProps<T>) {
  return (
    <div className="field">
      <span className="label">{label}</span>
      <div className="choice">
        {choices.map((choice) => (
          <button key={choice.title} type="button" className={`opt ${choice.value === selected ? "on" : ""}`}
                  aria-pressed={choice.value === selected} onClick={() => onSelect(choice.value)}>
            <b>{choice.title}{choice.recommended && <span className="chip ok">Recommended</span>}</b>
            <span className="hint">{choice.description}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

interface CheckboxProps {
  label: string;
  hint: string;
  checked: boolean;
  onChange?: (checked: boolean) => void;
}

/** A checkbox with an explanation; without onChange it is shown as always on. */
export function Checkbox({ label, hint, checked, onChange }: CheckboxProps) {
  return (
    <label className="row check">
      <input type="checkbox" aria-label={label} checked={checked} disabled={!onChange}
             onChange={(event) => onChange?.(event.target.checked)} />
      <span><b>{label}</b><br /><span className="hint">{hint}</span></span>
    </label>
  );
}

interface NumberInputProps {
  id: string;
  value: number;
  onValue: (value: number) => void;
}

/** Keeps the typed text so a field can be cleared and retyped; the answer receives the number. */
export function NumberInput({ id, value, onValue }: NumberInputProps) {
  const [text, setText] = useState(String(value));
  const change = (next: string) => {
    setText(next);
    onValue(Number(next));
  };
  return <input type="text" inputMode="numeric" id={id} value={text} onChange={(event) => change(event.target.value)} />;
}
