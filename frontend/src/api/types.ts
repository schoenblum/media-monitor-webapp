export type UUID = string;

export type Lang =
  | "en"
  | "de"
  | "fr"
  | "es"
  | "it"
  | "pt"
  | "ru"
  | "zh"
  | "ko"
  | "ja";

export const SUPPORTED_LANGS: Lang[] = [
  "en", "de", "fr", "es", "it", "pt", "ru", "zh", "ko", "ja",
];

export const LANG_LABELS: Record<Lang, string> = {
  en: "English",
  de: "German",
  fr: "French",
  es: "Spanish",
  it: "Italian",
  pt: "Portuguese",
  ru: "Russian",
  zh: "Chinese",
  ko: "Korean",
  ja: "Japanese",
};

export type UserRole = "admin" | "user";

export type RunStatus = "pending" | "running" | "complete" | "failed";

export interface User {
  id: UUID;
  email: string;
  backup_email?: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
  force_password_change: boolean;
  has_google_key: boolean;
  has_engine_id: boolean;
  has_webhook_key: boolean;
}

export interface SearchTerm {
  id?: UUID;
  language_code: Lang;
  term: string;
  pages: number;
  is_enabled: boolean;
}

export interface Search {
  id: UUID;
  name: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  terms: SearchTerm[];
  outlet_ids: UUID[];
}

export interface Outlet {
  id: UUID;
  name: string;
  domain: string;
  category: string | null;
  keyword_langs: Lang[];
  is_active: boolean;
  created_at: string;
}

export interface Run {
  id: UUID;
  search_id: UUID;
  triggered_by: "manual" | "webhook";
  status: RunStatus;
  started_at: string;
  completed_at: string | null;
  api_calls_used: number;
  error_message: string | null;
  search_name: string | null;
  result_count: number;
}

export interface Result {
  id: UUID;
  run_id: UUID;
  outlet_name: string;
  title: string;
  url: string;
  display_source: string;
  snippet: string;
  date_extracted: string;
  keyword_used: string;
  search_lang: string;
  detected_lang: string;
  detected_lang_name: string;
  is_selected: boolean;
}

export interface ResultsPage {
  items: Result[];
  total: number;
  page: number;
  page_size: number;
}

export interface ImportReport {
  imported: number;
  skipped: { row: number; reason: string }[];
}
