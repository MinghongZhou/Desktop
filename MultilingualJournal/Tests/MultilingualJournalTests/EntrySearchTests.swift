import XCTest
@testable import MultilingualJournal

final class EntrySearchTests: XCTestCase {
    private func entry(_ text: String, language: String?) -> JournalEntry {
        JournalEntry(
            segments: [EntrySegment(text: text, languageCode: language, order: 0)],
            source: .text
        )
    }

    func testEmptyQueryReturnsEverything() {
        let entries = [entry("hello", language: "en"), entry("hola", language: "es")]
        XCTAssertEqual(EntrySearch.filter(entries, query: "").count, 2)
        XCTAssertEqual(EntrySearch.filter(entries, query: "   ").count, 2)
    }

    func testMatchesSubstringCaseInsensitively() {
        let target = entry("Today was a Good day", language: "en")
        XCTAssertTrue(EntrySearch.matches(target, query: "good"))
        XCTAssertTrue(EntrySearch.matches(target, query: "GOOD"))
        XCTAssertFalse(EntrySearch.matches(target, query: "terrible"))
    }

    func testMatchesIgnoringDiacritics() {
        // Someone searching from an English keyboard shouldn't have to type
        // the accent to find their Spanish entry.
        let target = entry("Hoy fue un buen día en el café", language: "es")
        XCTAssertTrue(EntrySearch.matches(target, query: "dia"))
        XCTAssertTrue(EntrySearch.matches(target, query: "cafe"))
    }

    func testMatchesOnLanguageName() {
        let target = entry("Hoy fue un buen día", language: "es")
        XCTAssertTrue(EntrySearch.matches(target, query: "spanish"))
        XCTAssertFalse(EntrySearch.matches(target, query: "japanese"))
    }

    func testFilterNarrowsToMatchingEntriesOnly() {
        let entries = [
            entry("I went running this morning", language: "en"),
            entry("Hoy fue un buen día", language: "es")
        ]
        let results = EntrySearch.filter(entries, query: "running")
        XCTAssertEqual(results.count, 1)
        XCTAssertEqual(results.first?.fullText, "I went running this morning")
    }
}
