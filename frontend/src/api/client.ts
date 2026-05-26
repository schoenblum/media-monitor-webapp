import type {
  DuplicateRunsReport,
  ImportReport,
  LanguageCommitReport,
  LanguageCommitRequest,
  LanguagePreviewResponse,
  Outlet,
  OutletCommitReport,
  OutletCommitRequest,
  OutletPreviewResponse,
  Result,
  ResultsPage,
  Run,
  Search,
  SearchConfig,
  University,
  UniversityLanguage,
  User,
  UUID,
  RunStatus,
} from "./types";

const API = "/api/v1";

export const tokenStore = {
  get: () => localStorage.getItem("mm_token"),
  set: (t: string) => localStorage.setItem("mm_token", t),
  clear: () => localStorage.removeItem("mm_token"),
};

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { auth?: boolean } = { auth: true },
): Promise<T> {
  const { auth = true, headers, ...rest } = options;
  const hdrs = new Headers(headers);
  if (auth) {
    const token = tokenStore.get();
    if (token) hdrs.set("Authorization", `Bearer ${token}`);
  }
  if (rest.body && !(rest.body instanceof FormData) && !hdrs.has("Content-Type")) {
    hdrs.set("Content-Type", "application/json");
  }
  const resp = await fetch(API + path, { ...rest, headers: hdrs });
  if (resp.status === 401 && auth) {
    tokenStore.clear();
    if (!location.pathname.startsWith("/login")) {
      location.href = "/login";
    }
  }
  const ct = resp.headers.get("content-type") || "";
  if (resp.status === 204) return undefined as T;
  if (!resp.ok) {
    let body: unknown = null;
    let message = resp.statusText;
    if (ct.includes("application/json")) {
      body = await resp.json().catch(() => null);
      const detail = (body as { detail?: unknown } | null)?.detail;
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail)) message = detail.map((d) => (d as { msg?: string })?.msg ?? JSON.stringify(d)).join("; ");
    } else {
      body = await resp.text().catch(() => null);
    }
    throw new ApiError(resp.status, body, message);
  }
  if (ct.includes("application/json")) return (await resp.json()) as T;
  return (await resp.text()) as unknown as T;
}

export async function fetchBlob(path: string): Promise<Blob> {
  const token = tokenStore.get();
  const hdrs: Record<string, string> = {};
  if (token) hdrs["Authorization"] = `Bearer ${token}`;
  const resp = await fetch(API + path, { headers: hdrs });
  if (!resp.ok) {
    throw new ApiError(resp.status, await resp.text().catch(() => ""), `Download failed (HTTP ${resp.status})`);
  }
  return resp.blob();
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string; force_password_change: boolean }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }), auth: false },
    ),
  me: () => request<User>("/auth/me"),
  changePassword: (current_password: string, new_password: string) =>
    request<void>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),
  forgotPassword: (email: string) =>
    request<{ detail: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
      auth: false,
    }),
  resetPassword: (token: string, new_password: string) =>
    request<void>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password }),
      auth: false,
    }),

  // Users (self)
  updateMe: (payload: { email?: string; backup_email?: string }) =>
    request<User>("/users/me", { method: "PATCH", body: JSON.stringify(payload) }),
  updateCredentials: (google_api_key: string, search_engine_id: string) =>
    request<{ has_google_key: boolean; has_engine_id: boolean }>("/users/me/credentials", {
      method: "PUT",
      body: JSON.stringify({ google_api_key, search_engine_id }),
    }),
  deleteCredentials: () =>
    request<{ has_google_key: boolean; has_engine_id: boolean }>("/users/me/credentials", {
      method: "DELETE",
    }),
  credentialsStatus: () =>
    request<{ has_google_key: boolean; has_engine_id: boolean }>("/users/me/credentials/status"),
  generateWebhookKey: () => request<{ api_key: string }>("/users/me/webhook-key", { method: "POST" }),
  revokeWebhookKey: () => request<void>("/users/me/webhook-key", { method: "DELETE" }),

  // Users (admin)
  listUsers: () => request<User[]>("/users"),
  createUser: (email: string, role: "admin" | "user") =>
    request<{ user: User; initial_password: string; email_sent: boolean }>("/users", {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),
  updateUser: (
    id: UUID,
    payload: {
      is_active?: boolean;
      role?: "admin" | "user";
      set_university?: boolean;
      university_id?: UUID | null;
    },
  ) =>
    request<User>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteUser: (id: UUID) => request<void>(`/users/${id}`, { method: "DELETE" }),
  duplicateUser: (id: UUID, email: string) =>
    request<{ user: User; initial_password: string; email_sent: boolean }>(`/users/${id}/duplicate`, {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  // University Languages
  listLanguages: () => request<UniversityLanguage[]>("/languages"),
  createLanguage: (payload: { iso_code: string; university_name: string }) =>
    request<UniversityLanguage>("/languages", { method: "POST", body: JSON.stringify(payload) }),
  updateLanguage: (id: UUID, payload: { iso_code?: string; university_name?: string }) =>
    request<UniversityLanguage>(`/languages/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteLanguage: (id: UUID) => request<void>(`/languages/${id}`, { method: "DELETE" }),
  bulkDeleteLanguages: (language_ids: UUID[]) =>
    request<void>("/languages/bulk-delete", {
      method: "POST",
      body: JSON.stringify({ language_ids }),
    }),
  previewLanguageImport: async (file: File): Promise<LanguagePreviewResponse> => {
    const fd = new FormData();
    fd.append("file", file);
    return request<LanguagePreviewResponse>("/languages/import/preview", { method: "POST", body: fd });
  },
  commitLanguageImport: (payload: LanguageCommitRequest) =>
    request<LanguageCommitReport>("/languages/import/commit", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  downloadLanguageTemplate: () => fetchBlob("/languages/import/template"),
  exportLanguages: () => fetchBlob("/languages/export"),

  // Searches
  listSearches: () => request<Search[]>("/searches"),
  getSearch: (id: UUID) => request<Search>(`/searches/${id}`),
  createSearch: (name: string, is_default = false) =>
    request<Search>("/searches", { method: "POST", body: JSON.stringify({ name, is_default }) }),
  updateSearch: (id: UUID, payload: { name?: string; is_default?: boolean; config?: SearchConfig }) =>
    request<Search>(`/searches/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteSearch: (id: UUID) => request<void>(`/searches/${id}`, { method: "DELETE" }),

  // Outlets
  listOutlets: () => request<Outlet[]>("/outlets"),
  createOutlet: (payload: { name: string; domain: string; category?: string | null; keyword_langs: string[]; is_active?: boolean }) =>
    request<Outlet>("/outlets", { method: "POST", body: JSON.stringify(payload) }),
  updateOutlet: (id: UUID, payload: Partial<Omit<Outlet, "id" | "created_at">>) =>
    request<Outlet>(`/outlets/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteOutlet: (id: UUID) => request<void>(`/outlets/${id}`, { method: "DELETE" }),
  importOutlets: async (file: File, mode: "replace" | "add"): Promise<ImportReport> => {
    const fd = new FormData();
    fd.append("file", file);
    return request<ImportReport>(`/outlets/import?mode=${mode}`, { method: "POST", body: fd });
  },
  previewOutletImport: async (file: File): Promise<OutletPreviewResponse> => {
    const fd = new FormData();
    fd.append("file", file);
    return request<OutletPreviewResponse>("/outlets/import/preview", { method: "POST", body: fd });
  },
  commitOutletImport: (payload: OutletCommitRequest) =>
    request<OutletCommitReport>("/outlets/import/commit", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  bulkDeleteOutlets: (outlet_ids: UUID[]) =>
    request<void>("/outlets/bulk-delete", {
      method: "POST",
      body: JSON.stringify({ outlet_ids }),
    }),
  downloadImportTemplate: () => fetchBlob("/outlets/import/template"),
  exportOutlets: () => fetchBlob("/outlets/export"),

  // Runs
  listRuns: (params?: { search_id?: UUID; status?: RunStatus }) => {
    const q = new URLSearchParams();
    if (params?.search_id) q.set("search_id", params.search_id);
    if (params?.status) q.set("status", params.status);
    const qs = q.toString();
    return request<Run[]>(`/runs${qs ? `?${qs}` : ""}`);
  },
  triggerRun: (search_id: UUID, opts?: { deduplicate?: boolean }) =>
    request<Run>("/runs", {
      method: "POST",
      body: JSON.stringify({
        search_id,
        deduplicate: opts?.deduplicate ?? true,
      }),
    }),
  getRun: (id: UUID) => request<Run>(`/runs/${id}`),
  getResults: (
    id: UUID,
    params?: { lang?: string; selected?: boolean; page?: number; page_size?: number },
  ) => {
    const q = new URLSearchParams();
    if (params?.lang) q.set("lang", params.lang);
    if (params?.selected !== undefined) q.set("selected", String(params.selected));
    if (params?.page) q.set("page", String(params.page));
    if (params?.page_size) q.set("page_size", String(params.page_size));
    const qs = q.toString();
    return request<ResultsPage>(`/runs/${id}/results${qs ? `?${qs}` : ""}`);
  },
  getMergedResults: (
    run_ids: UUID[],
    params?: { page?: number; page_size?: number },
  ) => {
    const q = new URLSearchParams();
    run_ids.forEach((id) => q.append("run_ids[]", id));
    if (params?.page) q.set("page", String(params.page));
    if (params?.page_size) q.set("page_size", String(params.page_size));
    return request<ResultsPage>(`/runs/merged?${q.toString()}`);
  },
  setResultsSelection: (id: UUID, result_ids: UUID[], selected: boolean) =>
    request<void>(`/runs/${id}/results`, {
      method: "PATCH",
      body: JSON.stringify({ result_ids, selected }),
    }),
  deleteRun: (id: UUID) => request<void>(`/runs/${id}`, { method: "DELETE" }),
  bulkDeleteRuns: (run_ids: UUID[]) =>
    request<void>("/runs/bulk-delete", { method: "POST", body: JSON.stringify({ run_ids }) }),
  exportRuns: (run_ids: UUID[]) => {
    const params = run_ids.map((r) => `run_ids[]=${encodeURIComponent(r)}`).join("&");
    return fetchBlob(`/runs/export?${params}`);
  },

  // Universities (admin only)
  listUniversities: () => request<University[]>("/universities"),
  createUniversity: (name: string) =>
    request<University>("/universities", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  renameUniversity: (id: UUID, name: string) =>
    request<University>(`/universities/${id}`, {
      method: "PUT",
      body: JSON.stringify({ name }),
    }),
  deleteUniversity: (id: UUID) =>
    request<void>(`/universities/${id}`, { method: "DELETE" }),
  duplicateRunsIntoUniversity: (user_id: UUID, target_university_id: UUID) =>
    request<DuplicateRunsReport>("/universities/duplicate-runs", {
      method: "POST",
      body: JSON.stringify({ user_id, target_university_id }),
    }),
};

export type { Outlet, Result, Run, Search, UniversityLanguage, User, ResultsPage };
