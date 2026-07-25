import XCTest
@testable import MultilingualJournal

final class VocabularyStatsTests: XCTestCase {
    private let calendar = Calendar(identifier: .gregorian)

    private var now: Date {
        calendar.date(from: DateComponents(year: 2026, month: 7, day: 25, hour: 12))!
    }

    private func daysAgo(_ count: Int) -> Date {
        calendar.date(byAdding: .day, value: -count, to: now)!
    }

    private func entry(_ text: String, language: String, date: Date) -> JournalEntry {
        JournalEntry(
            date: date,
            segments: [EntrySegment(text: text, languageCode: language, order: 0)],
            source: .text
        )
    }

    func testWordsAreLowercasedAndStrippedOfPunctuation() {
        let words = VocabularyAnalyzer.words(in: "Hola, ¿qué tal?")
        XCTAssertTrue(words.contains("hola"))
        XCTAssertTrue(words.contains("qué"))
        XCTAssertFalse(words.contains("hola,"))
    }

    func testWordsExcludesBareNumbers() {
        let words = VocabularyAnalyzer.words(in: "I ran 5 miles")
        XCTAssertFalse(words.contains("5"))
        XCTAssertTrue(words.contains("miles"))
    }

    func testOnlyCountsSegmentsInTheTargetLanguage() {
        let entries = [
            entry("gato perro", language: "es", date: daysAgo(1)),
            entry("cat dog bird", language: "en", date: daysAgo(1))
        ]
        let stats = VocabularyAnalyzer.stats(for: entries, languageCode: "es", since: daysAgo(30))
        XCTAssertEqual(stats.totalUniqueWords, 2)
    }

    func testRepeatedWordsCountOnce() {
        let entries = [
            entry("gato gato gato", language: "es", date: daysAgo(2)),
            entry("gato perro", language: "es", date: daysAgo(1))
        ]
        let stats = VocabularyAnalyzer.stats(for: entries, languageCode: "es", since: daysAgo(30))
        XCTAssertEqual(stats.totalUniqueWords, 2)
    }

    func testNewWordsCountsOnlyFirstUsesInsideTheWindow() {
        let entries = [
            entry("gato", language: "es", date: daysAgo(60)),   // outside window
            entry("gato perro", language: "es", date: daysAgo(5)) // "perro" is new, "gato" isn't
        ]
        let stats = VocabularyAnalyzer.stats(for: entries, languageCode: "es", since: daysAgo(30))
        XCTAssertEqual(stats.totalUniqueWords, 2)
        XCTAssertEqual(stats.newWordsInPeriod, 1)
        XCTAssertEqual(stats.recentNewWords, ["perro"])
    }

    func testNoMatchingSegmentsYieldsEmptyStats() {
        let entries = [entry("hello world", language: "en", date: daysAgo(1))]
        let stats = VocabularyAnalyzer.stats(for: entries, languageCode: "es", since: daysAgo(30))
        XCTAssertEqual(stats, .empty)
    }

    func testSampleLimitCapsReturnedWords() {
        let text = (1...20).map { "palabra\($0)" }.joined(separator: " ")
        let entries = [entry(text, language: "es", date: daysAgo(1))]
        let stats = VocabularyAnalyzer.stats(for: entries, languageCode: "es", since: daysAgo(30), sampleLimit: 5)
        XCTAssertEqual(stats.newWordsInPeriod, 20)
        XCTAssertEqual(stats.recentNewWords.count, 5)
    }
}
