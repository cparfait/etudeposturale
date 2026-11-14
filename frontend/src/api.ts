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

async function upload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`/api${path}`, { method: "POST", body: form });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* réponse non JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Any = any;

export const http = {
  get: <T = Any>(p: string) => request<T>("GET", p),
  post: <T = Any>(p: string, body?: unknown) => request<T>("POST", p, body ?? {}),
  put: <T = Any>(p: string, body: unknown) => request<T>("PUT", p, body),
  del: async (p: string) => {
    const res = await fetch(`/api${p}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  },
  upload: <T = Any>(p: string, form: FormData) => upload<T>(p, form),
};

export const api = {
  health: () => request<{ status: string; version: string }>("GET", "/health"),
  getProfile: () => request<Values>("GET", "/profile"),
  putProfile: (v: Values) => request<Values>("PUT", "/profile", v),
  getBike: () => request<Values>("GET", "/bike"),
  putBike: (v: Values) => request<Values>("PUT", "/bike", v),
  listConfigs: () => request<BikeConfig[]>("GET", "/bike/configs"),
  createConfig: (v: Values) => request<BikeConfig>("POST", "/bike/configs", v),
};
