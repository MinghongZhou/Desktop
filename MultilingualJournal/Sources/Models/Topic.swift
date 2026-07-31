import Foundation

/// A journaling prompt derived from a current news article (or an evergreen
/// fallback). Fetched on demand and not persisted on its own — when the user
/// journals about a topic, the citation is copied onto the `JournalEntry`.
struct Topic: Identifiable, Hashable, Codable {
    var id: UUID = UUID()
    /// The article headline, in the target language. Empty for evergreen
    /// fallback topics that aren't tied to an article.
    var headline: String
    /// The full journaling prompt shown to the user (template + headline).
    var prompt: String
    /// Link to the source article; empty for evergreen fallbacks.
    var articleURL: String
    /// Publisher name for attribution ("BBC Mundo"); empty for fallbacks.
    var publisher: String
    var languageCode: String
    var fetchedAt: Date = .now

    /// True when this topic cites a real article (vs. an evergreen prompt).
    var hasSource: Bool { !articleURL.isEmpty && !headline.isEmpty }
}
