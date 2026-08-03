import Foundation

/// Mixes topics from several enabled `TopicSource`s into one list for the
/// Topics tab. Fetches each available source, then round-robin interleaves the
/// results so no single source dominates, and caps the total.
///
/// Fetching is sequential for now (there are few sources, and it sidesteps
/// sending non-Sendable sources across task boundaries); it can be parallelized
/// later if the source count grows.
enum TopicAggregator {
    static func topics(from sources: [TopicSource], languageCode: String, limit: Int) async -> [Topic] {
        var lists: [[Topic]] = []
        for source in sources where source.isAvailable(languageCode: languageCode) {
            let topics = await source.fetchTopics(languageCode: languageCode, limit: limit)
            if !topics.isEmpty { lists.append(topics) }
        }
        return interleave(lists, limit: limit)
    }

    /// Round-robin merge: take the first of each list, then the second, etc.,
    /// until `limit` is reached or all lists are exhausted. Pure/testable.
    static func interleave(_ lists: [[Topic]], limit: Int) -> [Topic] {
        var result: [Topic] = []
        var cursors = Array(repeating: 0, count: lists.count)
        var progressed = true
        while progressed && result.count < limit {
            progressed = false
            for i in lists.indices {
                guard cursors[i] < lists[i].count else { continue }
                result.append(lists[i][cursors[i]])
                cursors[i] += 1
                progressed = true
                if result.count >= limit { break }
            }
        }
        return result
    }
}
