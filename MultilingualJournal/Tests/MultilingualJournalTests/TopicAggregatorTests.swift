import XCTest
@testable import MultilingualJournal

/// A canned source for exercising the aggregator without any network.
private struct MockSource: TopicSource {
    let kind: TopicSourceKind
    var available = true
    var topics: [Topic]
    func isAvailable(languageCode: String) -> Bool { available }
    func fetchTopics(languageCode: String, limit: Int) async -> [Topic] { Array(topics.prefix(limit)) }
}

private func topic(_ prompt: String, kind: TopicSourceKind) -> Topic {
    Topic(sourceKind: kind, headline: "", prompt: prompt, articleURL: "", publisher: "", languageCode: "en")
}

final class TopicAggregatorTests: XCTestCase {
    func testInterleaveRoundRobinsAcrossLists() {
        let a = [topic("a1", kind: .news), topic("a2", kind: .news), topic("a3", kind: .news)]
        let b = [topic("b1", kind: .onThisDay), topic("b2", kind: .onThisDay)]
        let merged = TopicAggregator.interleave([a, b], limit: 10)
        XCTAssertEqual(merged.map(\.prompt), ["a1", "b1", "a2", "b2", "a3"])
    }

    func testInterleaveRespectsLimit() {
        let a = [topic("a1", kind: .news), topic("a2", kind: .news)]
        let b = [topic("b1", kind: .onThisDay), topic("b2", kind: .onThisDay)]
        let merged = TopicAggregator.interleave([a, b], limit: 3)
        XCTAssertEqual(merged.count, 3)
        XCTAssertEqual(merged.map(\.prompt), ["a1", "b1", "a2"])
    }

    func testInterleaveHandlesEmptyAndUnevenLists() {
        let merged = TopicAggregator.interleave([[], [topic("only", kind: .news)]], limit: 5)
        XCTAssertEqual(merged.map(\.prompt), ["only"])
    }

    func testTopicsMixesEnabledSources() async {
        let news = MockSource(kind: .news, topics: [topic("n1", kind: .news), topic("n2", kind: .news)])
        let day = MockSource(kind: .onThisDay, topics: [topic("d1", kind: .onThisDay)])
        let merged = await TopicAggregator.topics(from: [news, day], languageCode: "en", limit: 10)
        XCTAssertEqual(merged.map(\.prompt), ["n1", "d1", "n2"])
    }

    func testTopicsSkipsUnavailableSources() async {
        let off = MockSource(kind: .personal, available: false, topics: [topic("x", kind: .personal)])
        let on = MockSource(kind: .news, topics: [topic("n1", kind: .news)])
        let merged = await TopicAggregator.topics(from: [off, on], languageCode: "en", limit: 10)
        XCTAssertEqual(merged.map(\.prompt), ["n1"])
    }

    func testTopicsEmptyWhenNoSourcesProduce() async {
        let empty = MockSource(kind: .news, topics: [])
        let merged = await TopicAggregator.topics(from: [empty], languageCode: "en", limit: 10)
        XCTAssertTrue(merged.isEmpty)
    }
}
