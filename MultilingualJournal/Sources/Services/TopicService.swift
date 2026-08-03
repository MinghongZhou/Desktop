import Foundation

/// Entry point the UI calls for journaling topics. Assembles the enabled
/// `TopicSource`s, mixes them via `TopicAggregator`, and falls back to evergreen
/// prompts when nothing is available (news off, feeds down, empty results) so
/// the Topics tab always has something to show.
///
/// Only source-fetching touches the network; journal entries never leave the
/// device.
enum TopicService {
    /// - Parameters:
    ///   - languageCode: the user's target language (drives feed + prompt language).
    ///   - newsEnabled: when false, the news source is excluded.
    ///   - limit: max topics to return.
    static func fetchTopics(languageCode: String, newsEnabled: Bool, limit: Int = 6) async -> [Topic] {
        let sources = enabledSources(newsEnabled: newsEnabled)
        let topics = await TopicAggregator.topics(from: sources, languageCode: languageCode, limit: limit)
        return topics.isEmpty ? evergreenTopics(languageCode: languageCode) : topics
    }

    /// The sources to draw from, given current preferences. As new sources land
    /// (on-this-day, word-of-day, personal), they're added here behind their
    /// own toggles.
    static func enabledSources(newsEnabled: Bool) -> [TopicSource] {
        var sources: [TopicSource] = []
        if newsEnabled { sources.append(NewsSource()) }
        return sources
    }

    /// Evergreen prompts with no article citation. Used as the fail-soft
    /// fallback and when every source is off.
    static func evergreenTopics(languageCode: String, count: Int = 3) -> [Topic] {
        (0..<count).map { index in
            Topic(
                sourceKind: .evergreen,
                headline: "",
                prompt: TopicPromptBuilder.evergreen(languageCode: languageCode, seed: index),
                articleURL: "",
                publisher: "",
                languageCode: languageCode
            )
        }
    }
}
