export type UUID = string;

export type UserRole = "admin" | "user";
export type RunStatus = "pending" | "running" | "complete" | "failed" | "skipped";
export type RunTrigger = "manual" | "webhook" | "scheduled";

/** Display-name map for the RunTrigger enum — keep this the single source of
 * truth so Dashboard and Run History stay in agreement (v2.4 item 6). */
export const RUN_TRIGGER_LABEL: Record<RunTrigger, string> = {
  manual: "Manual",
  webhook: "Webhook",
  scheduled: "Scheduled",
};

export function triggerLabel(t: string): string {
  return (RUN_TRIGGER_LABEL as Record<string, string>)[t] ?? t;
}

// ---------------------------------------------------------------------------
// University language
// ---------------------------------------------------------------------------

export interface UniversityLanguage {
  id: UUID;
  iso_code: string;
  university_name: string;
  created_at: string;
}

export interface LanguagePreviewRow {
  row_num: number;
  iso_code: string;
  university_name: string;
}

export interface LanguageInvalidIsoRow {
  row_num: number;
  raw_iso: string;
  university_name: string;
}

export interface LanguageDuplicateRow {
  row_num: number;
  iso_code: string;
  new_university_name: string;
  existing_id: UUID;
  existing_university_name: string;
}

export interface LanguagePreviewResponse {
  new_rows: LanguagePreviewRow[];
  invalid_iso_rows: LanguageInvalidIsoRow[];
  duplicate_rows: LanguageDuplicateRow[];
  parse_errors: string[];
}

export interface LanguageCommitItem {
  iso_code: string;
  university_name: string;
  replace_existing_id?: UUID | null;
}

export interface LanguageCommitRequest {
  mode: "add" | "replace";
  items: LanguageCommitItem[];
}

export interface LanguageCommitReport {
  added: number;
  replaced: number;
  deleted: number;
}

export interface OutletPreviewRow {
  row_num: number;
  name: string;
  domain: string;
  category: string | null;
  keyword_langs: string[];
}

export interface OutletDuplicateRow {
  row_num: number;
  domain: string;
  new_name: string;
  new_category: string | null;
  new_keyword_langs: string[];
  existing_id: UUID;
  existing_name: string;
  existing_category: string | null;
  existing_keyword_langs: string[];
}

export interface OutletPreviewResponse {
  new_rows: OutletPreviewRow[];
  duplicate_rows: OutletDuplicateRow[];
  parse_errors: string[];
}

export interface OutletCommitItem {
  name: string;
  domain: string;
  category?: string | null;
  keyword_langs: string[];
  replace_existing_id?: UUID | null;
}

export interface OutletCommitRequest {
  mode: "add" | "replace";
  items: OutletCommitItem[];
}

export interface OutletCommitReport {
  added: number;
  replaced: number;
  deleted: number;
}

// ---------------------------------------------------------------------------
// Search config
//
// NOTE: any change to this shape must be mirrored in app/schemas/search.py
// (SearchConfig) and app/models/search.py (DEFAULT_SEARCH_CONFIG).
// ---------------------------------------------------------------------------

export interface SearchTermConfig {
  id: string;
  text: string;
  operator: "AND" | "OR" | "NOT" | null;
}

export interface DoiConfig {
  text: string;
  pages: number;
}

export interface UniversityNameConfig {
  enabled: boolean;
  language_ids: UUID[];
  pages: number;
}

export interface OutletsConfig {
  enabled: boolean;
  outlet_ids: UUID[];
}

export interface ScheduleConfig {
  mode: "manual" | "auto";
  interval_hours: number;
  start_time: string;  // HH:MM, 24-hour
  timezone: string;    // IANA name, e.g. "Asia/Tokyo"
}

export interface SearchConfig {
  search_window: "last" | "hours" | "range";
  fallback_hours: number;
  date_from: string; // YYYY-MM-DD; only meaningful when search_window === "range"
  date_to: string;   // YYYY-MM-DD; empty = up to today (range mode)
  terms_pages: number;
  terms: SearchTermConfig[];
  doi: DoiConfig;
  university_name: UniversityNameConfig;
  outlets: OutletsConfig;
  schedule: ScheduleConfig;
}

export function defaultSearchConfig(): SearchConfig {
  return {
    search_window: "last",
    fallback_hours: 72,
    date_from: "",
    date_to: "",
    terms_pages: 1,
    terms: [],
    doi: { text: "", pages: 1 },
    university_name: { enabled: false, language_ids: [], pages: 1 },
    outlets: { enabled: false, outlet_ids: [] },
    schedule: {
      mode: "manual",
      interval_hours: 24,
      start_time: "08:00",
      timezone: "Asia/Tokyo",
    },
  };
}

// ---------------------------------------------------------------------------
// User
// ---------------------------------------------------------------------------

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
  // Affiliation (Item 8). Null when unaffiliated.
  university_id: UUID | null;
  university_name: string | null;
}

// ---------------------------------------------------------------------------
// University (Item 8)
// ---------------------------------------------------------------------------

export interface University {
  id: UUID;
  name: string;
  created_at: string;
  updated_at: string;
  member_count: number;
}

export interface DuplicateRunsReport {
  runs_copied: number;
  results_copied: number;
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export interface Search {
  id: UUID;
  name: string;
  is_default: boolean;
  config: SearchConfig;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Outlet
// ---------------------------------------------------------------------------

export interface Outlet {
  id: UUID;
  name: string;
  domain: string;
  category: string | null;
  keyword_langs: string[];
  is_active: boolean;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Run / Result
// ---------------------------------------------------------------------------

export interface Run {
  id: UUID;
  search_id: UUID;
  triggered_by: RunTrigger;
  status: RunStatus;
  started_at: string;
  completed_at: string | null;
  api_calls_used: number;
  error_message: string | null;
  search_name: string | null;
  result_count: number;
  // Affiliation context (Item 8) — meaningful when the run was performed under
  // a university. ``performed_by_email`` powers the "performed by" column.
  user_id: UUID | null;
  university_id: UUID | null;
  performed_by_email: string | null;
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

// ---------------------------------------------------------------------------
// Legacy (kept for reference; no longer used in search config)
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// BCP-47 / ISO 639 language dropdown list
//
// ⚠️ PAIRED-EDIT WARNING ⚠️
// This list is duplicated in app/services/languages.py (SUPPORTED_LANGUAGES).
// Any add/remove/rename here MUST be mirrored there, or CSV imports and the
// dropdown will drift out of sync. A future revision may collapse this to a
// single source of truth.
// ---------------------------------------------------------------------------

export interface LangOption {
  code: string;
  label: string;
}

export const ALL_LANGUAGES: LangOption[] = [
  { code: "af", label: "Afrikaans" },
  { code: "sq", label: "Albanian" },
  { code: "am", label: "Amharic" },
  { code: "ar", label: "Arabic" },
  { code: "hy", label: "Armenian" },
  { code: "az", label: "Azerbaijani" },
  { code: "eu", label: "Basque" },
  { code: "be", label: "Belarusian" },
  { code: "bn", label: "Bengali" },
  { code: "bs", label: "Bosnian" },
  { code: "bg", label: "Bulgarian" },
  { code: "ca", label: "Catalan" },
  { code: "ceb", label: "Cebuano" },
  { code: "ny", label: "Chichewa" },
  { code: "zh", label: "Chinese (Simplified)" },
  { code: "zh-TW", label: "Chinese (Traditional)" },
  { code: "co", label: "Corsican" },
  { code: "hr", label: "Croatian" },
  { code: "cs", label: "Czech" },
  { code: "da", label: "Danish" },
  { code: "nl", label: "Dutch" },
  { code: "en", label: "English" },
  { code: "eo", label: "Esperanto" },
  { code: "et", label: "Estonian" },
  { code: "tl", label: "Filipino" },
  { code: "fi", label: "Finnish" },
  { code: "fr", label: "French" },
  { code: "fy", label: "Frisian" },
  { code: "gl", label: "Galician" },
  { code: "ka", label: "Georgian" },
  { code: "de", label: "German" },
  { code: "el", label: "Greek" },
  { code: "gu", label: "Gujarati" },
  { code: "ht", label: "Haitian Creole" },
  { code: "ha", label: "Hausa" },
  { code: "haw", label: "Hawaiian" },
  { code: "iw", label: "Hebrew" },
  { code: "hi", label: "Hindi" },
  { code: "hmn", label: "Hmong" },
  { code: "hu", label: "Hungarian" },
  { code: "is", label: "Icelandic" },
  { code: "ig", label: "Igbo" },
  { code: "id", label: "Indonesian" },
  { code: "ga", label: "Irish" },
  { code: "it", label: "Italian" },
  { code: "ja", label: "Japanese" },
  { code: "jw", label: "Javanese" },
  { code: "kn", label: "Kannada" },
  { code: "kk", label: "Kazakh" },
  { code: "km", label: "Khmer" },
  { code: "rw", label: "Kinyarwanda" },
  { code: "ko", label: "Korean" },
  { code: "ku", label: "Kurdish" },
  { code: "ky", label: "Kyrgyz" },
  { code: "lo", label: "Lao" },
  { code: "la", label: "Latin" },
  { code: "lv", label: "Latvian" },
  { code: "lt", label: "Lithuanian" },
  { code: "lb", label: "Luxembourgish" },
  { code: "mk", label: "Macedonian" },
  { code: "mg", label: "Malagasy" },
  { code: "ms", label: "Malay" },
  { code: "ml", label: "Malayalam" },
  { code: "mt", label: "Maltese" },
  { code: "mi", label: "Maori" },
  { code: "mr", label: "Marathi" },
  { code: "mn", label: "Mongolian" },
  { code: "my", label: "Myanmar (Burmese)" },
  { code: "ne", label: "Nepali" },
  { code: "no", label: "Norwegian" },
  { code: "or", label: "Odia (Oriya)" },
  { code: "ps", label: "Pashto" },
  { code: "fa", label: "Persian" },
  { code: "pl", label: "Polish" },
  { code: "pt", label: "Portuguese" },
  { code: "pa", label: "Punjabi" },
  { code: "ro", label: "Romanian" },
  { code: "ru", label: "Russian" },
  { code: "sm", label: "Samoan" },
  { code: "gd", label: "Scots Gaelic" },
  { code: "sr", label: "Serbian" },
  { code: "st", label: "Sesotho" },
  { code: "sn", label: "Shona" },
  { code: "sd", label: "Sindhi" },
  { code: "si", label: "Sinhala" },
  { code: "sk", label: "Slovak" },
  { code: "sl", label: "Slovenian" },
  { code: "so", label: "Somali" },
  { code: "es", label: "Spanish" },
  { code: "su", label: "Sundanese" },
  { code: "sw", label: "Swahili" },
  { code: "sv", label: "Swedish" },
  { code: "tg", label: "Tajik" },
  { code: "ta", label: "Tamil" },
  { code: "tt", label: "Tatar" },
  { code: "te", label: "Telugu" },
  { code: "th", label: "Thai" },
  { code: "tr", label: "Turkish" },
  { code: "tk", label: "Turkmen" },
  { code: "uk", label: "Ukrainian" },
  { code: "ur", label: "Urdu" },
  { code: "ug", label: "Uyghur" },
  { code: "uz", label: "Uzbek" },
  { code: "vi", label: "Vietnamese" },
  { code: "cy", label: "Welsh" },
  { code: "xh", label: "Xhosa" },
  { code: "yi", label: "Yiddish" },
  { code: "yo", label: "Yoruba" },
  { code: "zu", label: "Zulu" },
];
