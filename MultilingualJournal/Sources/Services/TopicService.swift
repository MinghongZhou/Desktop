import Foundation

/// Fetches news-based journaling topics: picks a target-language RSS feed,
/// downloads and parses it, and turns each headline into a prompt via
/// `TopicPromptBuilder`. Fails soft — if news is disabled, the feed is
/// unreachable, or parsing yields nothing, it returns evergreen prompts so
/// the feature always has something to show.
///
/// Only feed-fetching touches the network; journal entries never leave the
/// device.
enum TopicService {
    /// - Parameters:
    ///   - languageCode: the user's target language (drives feed + prompt language).
    ///   - newsEnabled: when false, skips the network entirely and returns evergreen.
    ///   - limit: max news topics to return.
    static func fetchTopics(languageCode: String, newsEnabled: Bool, limit: Int = 6) async -> [Topic] {
        guard newsEnabled else { return evergreenTopics(languageCode: languageCode) }

        let feed = FeedCatalog.feed(for: languageCode)
        guard let url = URL(string: feed.url) else {
            return evergreenTopics(languageCode: languageCode)
        }

        do {
            var request = URLRequest(url: url)
            request.timeoutInterval = 12
            request.setValue("MultilingualJournal/1.0", forHTTPHeaderField: "User-Agent")
            let (data, response) = try await URLSession.shared.data(for: request)

            if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
                return evergreenTopics(languageCode: languageCode)
            }

            let items = RSSFeedParser.parse(data)
            guard !items.isEmpty else { return evergreenTopics(languageCode: languageCode) }

            return items.prefix(limit).map { item in
                Topic(
                    headline: item.title,
                    prompt: TopicPromptBuilder.prompt(headline: item.title, languageCode: languageCode),
                    articleURL: item.link,
                    publisher: feed.publisher,
                    imageURL: item.imageURL,
                    languageCode: languageCode
                )
            }
        } catch {
            return evergreenTopics(languageCode: languageCode)
        }
    }

    /// Evergreen prompts with no article citation. Used as the fail-soft
    /// fallback and when news is turned off.
    static func evergreenTopics(languageCode: String, count: Int = 3) -> [Topic] {
        (0..<count).map { index in
            Topic(
                headline: "",
                prompt: TopicPromptBuilder.evergreen(languageCode: languageCode, seed: index),
                articleURL: "",
                publisher: "",
                languageCode: languageCode
            )
        }
    }
}
