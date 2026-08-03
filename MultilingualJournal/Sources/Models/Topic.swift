import Foundation

/// Where a topic came from. Lets the Topics tab badge each prompt and mix
/// sources, and lets each kind carry its own framing.
enum TopicSourceKind: String, Codable, CaseIterable, Hashable {
    case news
    case onThisDay
    case wordOfDay
    case personal
    case evergreen

    var displayName: String {
        switch self {
        case .news: return "News"
        case .onThisDay: return "On this day"
        case .wordOfDay: return "Word of the day"
        case .personal: return "For you"
        case .evergreen: return "Prompt"
        }
    }
}

/// A journaling prompt derived from a source (news article, historical event,
/// word of the day, a personal follow-up, or an evergreen fallback). Fetched
/// on demand and not persisted on its own — when the user journals about a
/// topic, the citation is copied onto the `JournalEntry`.
struct Topic: Identifiable, Hashable, Codable {
    var id: UUID = UUID()
    /// Which source produced this topic.
    var sourceKind: TopicSourceKind = .news
    /// The article headline, in the target language. Empty for evergreen
    /// fallback topics that aren't tied to an article.
    var headline: String
    /// The full journaling prompt shown to the user (template + headline).
    var prompt: String
    /// The publisher's article summary (feed `<description>`), in the article's
    /// language — extra context/reading beyond the headline. Empty for
    /// evergreen fallbacks or when the feed provided none.
    var summary: String = ""
    /// Link to the source article; empty for evergreen fallbacks.
    var articleURL: String
    /// Publisher name for attribution ("BBC Mundo"); empty for fallbacks.
    var publisher: String
    /// A representative article image, if the feed provided one.
    var imageURL: String = ""
    var languageCode: String
    var fetchedAt: Date = .now

    /// True when this topic cites a real article (vs. an evergreen prompt).
    var hasSource: Bool { !articleURL.isEmpty && !headline.isEmpty }
}
