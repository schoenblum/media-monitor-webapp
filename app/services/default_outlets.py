"""Default outlet library (ported from MEDIA_OUTLETS in media_monitor_v38a)."""
from typing import TypedDict


class OutletSeed(TypedDict):
    name: str
    domain: str
    category: str | None
    keyword_langs: list[str]


# Mirrors the MEDIA_OUTLETS dict in v38a; category added from media_monitor_media.xlsx.
DEFAULT_OUTLETS: list[OutletSeed] = [
    {"name": "Al Jazeera", "domain": "aljazeera.com", "category": "Outstanding international importance", "keyword_langs": ["en"]},
    {"name": "Asharq Al-Awsat", "domain": "aawsat.com", "category": "Outstanding international importance", "keyword_langs": ["en"]},
    {"name": "BBC News", "domain": "bbc.com", "category": "Outstanding international importance", "keyword_langs": ["en"]},
    {"name": "CNN", "domain": "cnn.com", "category": "Outstanding international importance", "keyword_langs": ["en"]},
    {"name": "Der Spiegel", "domain": "spiegel.de", "category": "Outstanding international importance", "keyword_langs": ["en", "de"]},
    {"name": "El País", "domain": "elpais.com", "category": "Outstanding international importance", "keyword_langs": ["en", "es"]},
    {"name": "Financial Times", "domain": "ft.com", "category": "Outstanding international importance", "keyword_langs": ["en"]},
    {"name": "Le Monde", "domain": "lemonde.fr", "category": "Outstanding international importance", "keyword_langs": ["en", "fr"]},
    {"name": "The Economist", "domain": "economist.com", "category": "Outstanding international importance", "keyword_langs": ["en"]},
    {"name": "The Guardian", "domain": "theguardian.com", "category": "Outstanding international importance", "keyword_langs": ["en"]},
    {"name": "The New York Times", "domain": "nytimes.com", "category": "Outstanding international importance", "keyword_langs": ["en"]},
    {"name": "The Times of India", "domain": "timesofindia.indiatimes.com", "category": "Outstanding international importance", "keyword_langs": ["en"]},
    {"name": "The Wall Street Journal", "domain": "wsj.com", "category": "Outstanding international importance", "keyword_langs": ["en"]},
    {"name": "The Washington Post", "domain": "washingtonpost.com", "category": "Outstanding international importance", "keyword_langs": ["en"]},
    {"name": "USA Today", "domain": "usatoday.com", "category": "Outstanding international importance", "keyword_langs": ["en"]},
    {"name": "Xinhua News", "domain": "xinhuanet.com", "category": "Outstanding international importance", "keyword_langs": ["en", "zh"]},
    {"name": "Agence France-Presse (AFP)", "domain": "afp.com", "category": "News agency", "keyword_langs": ["en"]},
    {"name": "Associated Press", "domain": "apnews.com", "category": "News agency", "keyword_langs": ["en"]},
    {"name": "Deutsche Presse-Agentur", "domain": "dpa.com", "category": "News agency", "keyword_langs": ["en", "de"]},
    {"name": "Jiji Press", "domain": "jiji.com", "category": "News agency", "keyword_langs": ["en"]},
    {"name": "Kyodo News", "domain": "english.kyodonews.net", "category": "News agency", "keyword_langs": ["en"]},
    {"name": "Press Trust of India", "domain": "ptinews.com", "category": "News agency", "keyword_langs": ["en"]},
    {"name": "Reuters", "domain": "reuters.com", "category": "News agency", "keyword_langs": ["en"]},
    {"name": "China Times", "domain": "chinatimes.com", "category": "Asian non-English", "keyword_langs": ["zh"]},
    {"name": "Chosun Ilbo", "domain": "chosun.com", "category": "Asian non-English", "keyword_langs": ["en", "ko"]},
    {"name": "Dainik Jagran", "domain": "jagran.com", "category": "Asian non-English", "keyword_langs": ["en"]},
    {"name": "Kompas", "domain": "kompas.com", "category": "Asian non-English", "keyword_langs": ["en"]},
    {"name": "Philippine Daily Inquirer", "domain": "inquirer.net", "category": "Asian non-English", "keyword_langs": ["en"]},
    {"name": "The Nation (Thailand)", "domain": "nationthailand.com", "category": "Asian non-English", "keyword_langs": ["en"]},
    {"name": "China Daily", "domain": "chinadaily.com.cn", "category": "International English", "keyword_langs": ["en", "zh"]},
    {"name": "Daily Nation", "domain": "nation.africa", "category": "International English", "keyword_langs": ["en"]},
    {"name": "Mail & Guardian", "domain": "mg.co.za", "category": "International English", "keyword_langs": ["en"]},
    {"name": "Premium Times", "domain": "premiumtimesng.com", "category": "International English", "keyword_langs": ["en"]},
    {"name": "The Asahi Shimbun", "domain": "asahi.com", "category": "International English", "keyword_langs": ["en"]},
    {"name": "The Daily Telegraph", "domain": "telegraph.co.uk", "category": "International English", "keyword_langs": ["en"]},
    {"name": "The Hindu", "domain": "thehindu.com", "category": "International English", "keyword_langs": ["en"]},
    {"name": "The Irish Times", "domain": "irishtimes.com", "category": "International English", "keyword_langs": ["en"]},
    {"name": "The Japan News (by The Yomiuri Shimbun)", "domain": "japannews.yomiuri.co.jp", "category": "International English", "keyword_langs": ["en"]},
    {"name": "The Japan Times", "domain": "japantimes.co.jp", "category": "International English", "keyword_langs": ["en"]},
    {"name": "The National (UAE)", "domain": "thenationalnews.com", "category": "International English", "keyword_langs": ["en"]},
    {"name": "The Straits Times", "domain": "straitstimes.com", "category": "International English", "keyword_langs": ["en"]},
    {"name": "The Sydney Morning Herald", "domain": "smh.com.au", "category": "International English", "keyword_langs": ["en"]},
    {"name": "BBC Science Focus", "domain": "sciencefocus.com", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "Discover Magazine", "domain": "discovermagazine.com", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "IFL Science", "domain": "iflscience.com", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "MIT Technology Review", "domain": "technologyreview.com", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "National Geographic", "domain": "nationalgeographic.com", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "Nature News", "domain": "nature.com", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "New Scientist", "domain": "newscientist.com", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "Popular Science", "domain": "popsci.com", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "Quanta Magazine", "domain": "quantamagazine.org", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "Science Magazine", "domain": "science.org", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "Scientific American", "domain": "scientificamerican.com", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "Science News", "domain": "sciencenews.org", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "Smithsonian Magazine", "domain": "smithsonianmag.com", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "WIRED", "domain": "wired.com", "category": "Major science-focused English", "keyword_langs": ["en"]},
    {"name": "Clarín", "domain": "clarin.com", "category": "Global non-English", "keyword_langs": ["en", "es"]},
    {"name": "Corriere della Sera", "domain": "corriere.it", "category": "Global non-English", "keyword_langs": ["en", "it"]},
    {"name": "Die Welt", "domain": "welt.de", "category": "Global non-English", "keyword_langs": ["en", "de"]},
    {"name": "El Tiempo", "domain": "eltiempo.com", "category": "Global non-English", "keyword_langs": ["en", "es"]},
    {"name": "Folha de S.Paulo", "domain": "folha.uol.com.br", "category": "Global non-English", "keyword_langs": ["en", "pt"]},
    {"name": "Frankfurter Allgemeine Zeitung", "domain": "faz.net", "category": "Global non-English", "keyword_langs": ["en", "de"]},
    {"name": "Haaretz", "domain": "haaretz.com", "category": "Global non-English", "keyword_langs": ["en"]},
    {"name": "Kommersant", "domain": "kommersant.ru", "category": "Global non-English", "keyword_langs": ["en", "ru"]},
    {"name": "La Nación", "domain": "lanacion.com.ar", "category": "Global non-English", "keyword_langs": ["en", "es"]},
    {"name": "La Repubblica", "domain": "repubblica.it", "category": "Global non-English", "keyword_langs": ["en", "it"]},
    {"name": "Le Figaro", "domain": "lefigaro.fr", "category": "Global non-English", "keyword_langs": ["en", "fr"]},
    {"name": "O Globo", "domain": "oglobo.globo.com", "category": "Global non-English", "keyword_langs": ["en", "pt"]},
    {"name": "Bloomberg Asia", "domain": "bloomberg.com/asia", "category": "East-Asian economy", "keyword_langs": ["en"]},
    {"name": "Caixin Global", "domain": "caixinglobal.com", "category": "East-Asian economy", "keyword_langs": ["en"]},
    {"name": "Nikkei Asia", "domain": "asia.nikkei.com", "category": "East-Asian economy", "keyword_langs": ["en"]},
    {"name": "Chemical & Engineering News", "domain": "cen.acs.org", "category": "Engineering/medical English", "keyword_langs": ["en"]},
    {"name": "Chemical Processing", "domain": "chemicalprocessing.com", "category": "Engineering/medical English", "keyword_langs": ["en"]},
    {"name": "Chemistry World", "domain": "chemistryworld.com", "category": "Engineering/medical English", "keyword_langs": ["en"]},
    {"name": "Medical News Today", "domain": "medicalnewstoday.com", "category": "Engineering/medical English", "keyword_langs": ["en"]},
    {"name": "The Chemical Engineer", "domain": "thechemicalengineer.com", "category": "Engineering/medical English", "keyword_langs": ["en"]},
]


# Per-language default-pages for the seeded default search.
DEFAULT_LANGUAGE_PAGES: dict[str, int] = {
    "en": 10,
    "de": 3,
    "fr": 3,
    "es": 3,
    "it": 3,
    "pt": 3,
    "ru": 3,
    "zh": 3,
    "ko": 3,
}


# Default search-term wording per language (overridable per-user / per-search).
DEFAULT_KEYWORDS: dict[str, str] = {
    "en": "Kobe University",
    "de": "Universität Kobe",
    "fr": "Université de Kobe",
    "es": "Universidad de Kobe",
    "it": "Università di Kobe",
    "pt": "Universidade de Kobe",
    "ru": "Университет Кобе",
    "zh": "神户大学",
    "ko": "고베대학교",
    "ja": "神戸大学",
}


SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "de", "fr", "es", "it", "pt", "ru", "zh", "ko", "ja")


# Domains never returned as results (social media + the searched institution's own site).
EXCLUDED_DOMAINS: tuple[str, ...] = (
    "twitter.com",
    "x.com",
    "t.co",
    "facebook.com",
    "fb.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
)
