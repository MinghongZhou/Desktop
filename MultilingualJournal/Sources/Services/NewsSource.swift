import Foundation

/// Topic source backed by a target-language news RSS feed: fetches, parses, and
/// turns each headline into a prompt via `TopicPromptBuilder`. Fails soft
/// (returns `[]`); the evergreen fallback is applied one level up so it isn't
/// interleaved with real sources.
struct NewsSource: TopicSource {
    let kind: TopicSourceKind = .news

    /// News always has *something* — a language without a native feed falls
    /// back to the English feed.
    func isAvailable(languageCode: String) -> Bool { true }

    func fetchTopics(languageCode: String, limit: Int) async -> [Topic] {
        let feed = FeedCatalog.feed(for: languageCode)
        guard let url = URL(string: feed.url) else { return [] }

        do {
            var request = URLRequest(url: url)
            request.timeoutInterval = 12
            request.setValue("MultilingualJournal/1.0", forHTTPHeaderField: "User-Agent")
            let (data, response) = try await URLSession.shared.data(for: request)

            if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
                return []
            }

            let items = RSSFeedParser.parse(data)
            guard !items.isEmpty else { return [] }

            // The language the prompt/headline are actually in: the target's own
            // language when it has a native feed, else English (the fallback
            // feed). Stored on the topic so recording defaults to that language.
            let contentLanguage = FeedCatalog.hasNativeFeed(for: languageCode)
                ? RecordingLocale.languageCode(of: languageCode)
                : "en"

            return items.prefix(limit).map { item in
                Topic(
                    sourceKind: .news,
                    headline: item.title,
                    prompt: TopicPromptBuilder.prompt(headline: item.title, languageCode: contentLanguage),
                    summary: item.summary,
                    articleURL: item.link,
                    publisher: feed.publisher,
                    imageURL: item.imageURL,
                    languageCode: contentLanguage
                )
            }
        } catch {
            return []
        }
    }
}
