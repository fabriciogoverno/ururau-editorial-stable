"""Configuration constants and defaults for the scraper."""

from .models import ScraperConfig

DEFAULT_CONFIG = ScraperConfig()

GOOGLE_NEWS_URL = "https://news.google.com/search"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"

USER_AGENTS: list[str] = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:137.0) Gecko/20100101 Firefox/137.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/134.0.3124.95",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    # Firefox on Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0",
    # Chrome on Android
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
    # Safari on iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1",
]

SUPPORTED_COUNTRIES: dict[str, str] = {
    "US": "United States",
    "BR": "Brazil",
    "IN": "India",
    "GB": "United Kingdom",
    "CA": "Canada",
    "AU": "Australia",
    "DE": "Germany",
    "FR": "France",
    "JP": "Japan",
    "MX": "Mexico",
}

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "pt": "Portuguese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "hi": "Hindi",
    "it": "Italian",
    "ru": "Russian",
    "zh": "Chinese",
}

# Image domains/patterns to treat as ads and ignore
IMAGE_BLACKLIST: list[str] = [
    "googleads",
    "doubleclick",
    "googlesyndication",
    "google-analytics",
    "facebook.com/tr",
    "fbcdn",
    "amazon-adsystem",
    "adsystem",
    "outbrain",
    "taboola",
    "scorecardresearch",
    "1x1.gif",
    "beacon",
    "tracker",
    "pixel",
]

# HTML element IDs/classes that indicate ads, social widgets, comments, etc.
ID_CLASS_BLACKLIST: list[str] = [
    "ad",
    "ads",
    "advertisement",
    "advert",
    "social",
    "share",
    "sharing",
    "comment",
    "comments",
    "related",
    "sidebar",
    "newsletter",
    "subscribe",
    "follow",
    "popular",
    "trending",
    "outbrain",
    "taboola",
    "sponsored",
    "promoted",
    "affiliate",
    "cookie",
    "consent",
    "modal",
    "popup",
    "newsletter-signup",
    "email-signup",
    "recommend",
    "recommended",
    "read-more",
    "see-also",
    "most-read",
    "top-stories",
    "footer-",
    "header-ad",
    "banner-ad",
    "interstitial",
]
