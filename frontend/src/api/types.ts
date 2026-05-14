export type UUID = string;

export type UserRole = "admin" | "user";
export type RunStatus = "pending" | "running" | "complete" | "failed";

// ---------------------------------------------------------------------------
// University language
// ---------------------------------------------------------------------------

export interface UniversityLanguage {
  id: UUID;
  iso_code: string;
  language_label: string;
  university_name: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Search config
// ---------------------------------------------------------------------------

export interface SearchTermConfig {
  id: string;
  text: string;
  operator: "AND" | "OR" | "NOT" | null;
  pages: number;
}

export interface DoiConfig {
  text: string;
  pages: number;
}

export interface UniversityNameConfig {
  enabled: boolean;
  language_ids: UUID[];
}

export interface OutletsConfig {
  enabled: boolean;
  outlet_ids: UUID[];
}

export interface SearchConfig {
  search_window: "last" | "hours";
  fallback_hours: number;
  terms: SearchTermConfig[];
  doi: DoiConfig;
  university_name: UniversityNameConfig;
  outlets: OutletsConfig;
}

export function defaultSearchConfig(): SearchConfig {
  return {
    search_window: "last",
    fallback_hours: 72,
    terms: [],
    doi: { text: "", pages: 1 },
    university_name: { enabled: false, language_ids: [] },
    outlets: { enabled: false, outlet_ids: [] },
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
