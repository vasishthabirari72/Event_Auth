export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
  ) {
    super(code);
  }
}
let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
async function request(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<Response> {
  let response: Response;
  try {
    response = await fetch("/api" + path, {
      method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("connection", 0);
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "unexpected" }));
    throw new ApiError(
      typeof error.detail === "string" ? error.detail : "unexpected",
      response.status,
    );
  }
  return response;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  return (await request(path, method, body)).json() as Promise<T>;
}
export async function apiBlob(path: string): Promise<Blob> {
  return (await request(path, "POST")).blob();
}
export type Task = (action: () => Promise<void>) => Promise<void>;
export interface StaffSession {
  id: string;
  username: string;
  role: string;
  csrf: string;
}
export interface Config {
  organization: string;
  primary_color: string;
  member_fields: {
    key: string;
    label: string;
    type: string;
    required: boolean;
    options: string[];
  }[];
  default_options: string[];
  consent_version: string;
  consent_text: string;
  experimental_face: boolean;
}
export interface Member {
  id: string;
  member_code: string;
  name: string;
  mobile: string;
  is_minor: boolean;
  default_option: string | null;
  custom_fields: Record<string, string>;
  has_face: boolean;
  revision: number;
}
export interface EventSummary {
  id: string;
  name: string;
  date: string;
  venue: string;
  status: string;
  revision: number;
}
export interface EventDetail extends EventSummary {
  slots: {
    id: string;
    code: string;
    label: string;
    options: { id: string; code: string; label: string; count: number }[];
  }[];
  counters: { id: string; label: string; serves: string[] }[];
  registrations: {
    member_id: string;
    choices: Record<string, string>;
    needs_choice: boolean;
  }[];
}
