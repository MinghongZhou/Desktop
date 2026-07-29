import Foundation

/// Maps a target language to a news RSS feed in that language. Kept small and
/// curated: most entries use the BBC's multilingual feeds (same reliable
/// format), with a couple of other reputable outlets where the BBC has none.
/// Languages without a mapping fall back to English (BBC News).
enum FeedCatalog {
    struct Feed: Equatable {
        let url: String
        let publisher: String
    }

    static let english = Feed(url: "https://feeds.bbci.co.uk/news/rss.xml", publisher: "BBC News")

    private static let feeds: [String: Feed] = [
        "en": english,
        "es": Feed(url: "https://feeds.bbci.co.uk/mundo/rss.xml", publisher: "BBC Mundo"),
        "zh": Feed(url: "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml", publisher: "BBC 中文"),
        "ar": Feed(url: "https://feeds.bbci.co.uk/arabic/rss.xml", publisher: "BBC Arabic"),
        "fr": Feed(url: "https://www.lemonde.fr/rss/une.xml", publisher: "Le Monde"),
        "ja": Feed(url: "https://www3.nhk.or.jp/rss/news/cat0.xml", publisher: "NHK"),
    ]

    /// The feed for a language code (e.g. "es", "zh-Hans" → "zh"), or English.
    static func feed(for languageCode: String) -> Feed {
        let base = languageCode.split(whereSeparator: { $0 == "-" || $0 == "_" }).first.map(String.init)?.lowercased()
            ?? languageCode.lowercased()
        return feeds[base] ?? english
    }

    /// Whether a language has a dedicated (non-fallback) feed — used to tell
    /// the user when their target language will show English news instead.
    static func hasNativeFeed(for languageCode: String) -> Bool {
        let base = languageCode.split(whereSeparator: { $0 == "-" || $0 == "_" }).first.map(String.init)?.lowercased()
            ?? languageCode.lowercased()
        return feeds[base] != nil
    }
}
