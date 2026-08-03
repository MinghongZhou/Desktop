import Foundation

/// A provider of journaling topics for a target language — news, "on this day",
/// word of the day, personal follow-ups, etc. Each source is a small conformer;
/// `TopicAggregator` mixes whichever ones are enabled. Adding a new topic source
/// is just a new type conforming to this.
protocol TopicSource {
    var kind: TopicSourceKind { get }

    /// Cheap check for whether this source can produce anything for the given
    /// language (and, for AI sources, this device). Avoids spinning up a fetch
    /// that can't succeed.
    func isAvailable(languageCode: String) -> Bool

    /// Fetches up to `limit` topics. Must fail soft — return `[]` on any error
    /// rather than throwing, so one broken source never breaks the Topics tab.
    func fetchTopics(languageCode: String, limit: Int) async -> [Topic]
}
