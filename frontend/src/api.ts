// Client de l'API locale. Types alignés sur backend/src/posturale/storage/models.py.

export type Values = Record<string, string | number | null>;

export interface BikeConfig extends Values {
  id: number;
  bike_id: number;
  created_at: string;
}

interface ValidationError {
  loc: string[];
  msg: string;
  type: string;
  ctx?: Record<string, number | string>;
}

// Messages de validation de l'API (Pydantic) traduits en français.
function translate(e: ValidationError): string {
  const field = String(e.loc.at(-1)).replace(/_/g, " ");
  const ctx = e.ctx ?? {};
  const messages: Record<string, string> = {
    greater_than_equal: `doit être supérieur ou égal à ${ctx.ge}`,
    less_than_equal: `doit être inférieur ou égal à ${ctx.le}`,
    float_parsing: "doit être un nombre",
    int_parsing: "doit être un nombre entier",
    int_from_float: "doit être un nombre entier",
  };
  return `${field} : ${messages[e.type] ?? e.msg}`;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (Array.isArray(data.detail)) {
        detail = data.detail.map(translate).join(" ; ");
      } else if (data.detail) detail = data.detail;
    } catch {
      /* réponse non JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; version: string }>("GET", "/health"),
  getProfile: () => request<Values>("GET", "/profile"),
  putProfile: (v: Values) => request<Values>("PUT", "/profile", v),
  getBike: () => request<Values>("GET", "/bike"),
  putBike: (v: Values) => request<Values>("PUT", "/bike", v),
  listConfigs: () => request<BikeConfig[]>("GET", "/bike/configs"),
  createConfig: (v: Values) => request<BikeConfig>("POST", "/bike/configs", v),
};
