import XCTest
@testable import MultilingualJournal

final class FluencyAnalyzerTests: XCTestCase {
    private let calendar = Calendar(identifier: .gregorian)
    private var now: Date { calendar.date(from: DateComponents(year: 2026, month: 8, day: 1, hour: 12))! }
    private func daysAgo(_ n: Int) -> Date { calendar.date(byAdding: .day, value: -n, to: now)! }

    private func entry(_ segments: [(String, String?)], date: Date) -> JournalEntry {
        JournalEntry(
            date: date,
            segments: segments.enumerated().map { EntrySegment(text: $0.element.0, languageCode: $0.element.1, order: $0.offset) },
            source: .text
        )
    }

    func testWordCountIgnoresNumbersAndPunctuation() {
        XCTAssertEqual(FluencyAnalyzer.wordCount("I ran 5 miles today!"), 4)
        XCTAssertEqual(FluencyAnalyzer.wordCount("¿Qué tal?"), 2)
    }

    func testTargetRatioIsFractionOfTargetWords() {
        // 2 English words + 2 Spanish words → 0.5 Spanish.
        let e = entry([("hello there", "en"), ("hola amigo", "es")], date: now)
        XCTAssertEqual(FluencyAnalyzer.targetRatio(for: e, targetCode: "es")!, 0.5, accuracy: 0.001)
    }

    func testTargetRatioNilWhenNoWords() {
        let e = entry([("123 !!!", nil)], date: now)
        XCTAssertNil(FluencyAnalyzer.targetRatio(for: e, targetCode: "es"))
    }

    func testCodeSwitchesCountsLanguageTransitions() {
        let e = entry([("uno", "es"), ("two", "en"), ("tres", "es"), ("cuatro", "es")], date: now)
        // es→en, en→es, es→es(no) = 2 switches.
        XCTAssertEqual(FluencyAnalyzer.codeSwitches(in: e), 2)
    }

    func testSummaryTrendsRatioUpwardOverTime() {
        let entries = [
            entry([("hello there friend", "en"), ("hola", "es")], date: daysAgo(20)),  // 1/4 es
            entry([("hola amigo", "es"), ("bien", "es")], date: daysAgo(1)),            // 3/3 es
        ]
        let s = FluencyAnalyzer.summary(for: entries, targetCode: "es", recentCount: 1)
        XCTAssertEqual(s.points.count, 2)
        XCTAssertGreaterThan(s.currentTargetRatio, s.earlierTargetRatio)
        XCTAssertGreaterThan(s.ratioDelta, 0)
        XCTAssertTrue(s.hasTrend)
    }

    func testEmptyWhenNoTargetLanguageSet() {
        let entries = [entry([("hello", "en")], date: now)]
        XCTAssertEqual(FluencyAnalyzer.summary(for: entries, targetCode: ""), .empty)
    }

    func testEmptyWhenNoCountableEntries() {
        let entries = [entry([("123", nil)], date: now)]
        XCTAssertEqual(FluencyAnalyzer.summary(for: entries, targetCode: "es"), .empty)
    }

    func testAvgWordsPerSentenceUsesTargetSegmentsOnly() {
        let entries = [entry([("uno dos tres", "es"), ("hello", "en")], date: now)]
        let s = FluencyAnalyzer.summary(for: entries, targetCode: "es")
        XCTAssertEqual(s.avgWordsPerSentence, 3, accuracy: 0.001)
    }
}
