// Composants de formulaire : un écran = une liste de champs décrits par FieldSpec.
import type { Values } from "./api";

export interface FieldSpec {
  name: string;
  label: string;
  type?: "number" | "text" | "select" | "textarea" | "segmented";
  unit?: string;
  step?: number;
  options?: { value: string; label: string }[];
  help?: string;
  wide?: boolean;
}

interface FieldsProps {
  specs: FieldSpec[];
  values: Values;
  onChange: (name: string, value: string | number | null) => void;
  onFocusField?: (name: string | null) => void;
  changed?: Set<string>;
}

export function Fields({ specs, values, onChange, onFocusField, changed }: FieldsProps) {
  return (
    <div className="grid">
      {specs.map((f) => (
        <Field key={f.name} spec={f} value={values[f.name] ?? null} onChange={onChange}
          onFocusField={onFocusField} changed={changed?.has(f.name)} />
      ))}
    </div>
  );
}

function Field({ spec: f, value: v, onChange, onFocusField, changed }: {
  spec: FieldSpec;
  value: string | number | null;
  onChange: FieldsProps["onChange"];
  onFocusField?: FieldsProps["onFocusField"];
  changed?: boolean;
}) {
  const id = `f-${f.name}`;
  const type = f.type ?? "number";
  const wide = f.wide || type === "textarea" || type === "segmented";
  const focus = {
    onFocus: () => onFocusField?.(f.name),
    onBlur: () => onFocusField?.(null),
  };
  const helpId = f.help ? `${id}-help` : undefined;

  let control: React.ReactNode;
  if (type === "segmented") {
    control = (
      <div className="segmented" role="group" aria-labelledby={`${id}-label`}>
        {f.options!.map((o) => (
          <button key={o.value} type="button" aria-pressed={v === o.value} {...focus}
            onClick={() => onChange(f.name, v === o.value ? null : o.value)}>
            {o.label}
          </button>
        ))}
      </div>
    );
  } else if (type === "select") {
    control = (
      <select id={id} className="select" value={(v as string) ?? ""} aria-describedby={helpId} {...focus}
        onChange={(e) => onChange(f.name, e.target.value || null)}>
        <option value="">Non renseigné</option>
        {f.options!.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    );
  } else if (type === "textarea") {
    control = (
      <textarea id={id} className="textarea" value={(v as string) ?? ""} aria-describedby={helpId} {...focus}
        onChange={(e) => onChange(f.name, e.target.value || null)} />
    );
  } else {
    control = (
      <div className="input-wrap">
        <input id={id} className={f.unit ? "input has-unit" : "input"} type={type}
          inputMode={type === "number" ? "decimal" : undefined} step={f.step ?? "any"}
          value={v ?? ""} aria-describedby={helpId} {...focus}
          onChange={(e) => {
            const raw = e.target.value;
            onChange(f.name, raw === "" ? null : type === "number" ? Number(raw) : raw);
          }} />
        {f.unit && <span className="unit" aria-hidden="true">{f.unit}</span>}
      </div>
    );
  }

  return (
    <div className={`field${wide ? " wide" : ""}${changed ? " changed" : ""}`}>
      <label className="field-label" htmlFor={type === "segmented" ? undefined : id} id={`${id}-label`}>
        {f.label}
        {changed && <span className="changed-dot" title="Modifié par rapport à la configuration en cours" />}
      </label>
      {control}
      {f.help && <span className="field-help" id={helpId}>{f.help}</span>}
    </div>
  );
}
