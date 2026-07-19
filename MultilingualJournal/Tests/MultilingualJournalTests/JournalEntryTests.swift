import XCTest
@testable import MultilingualJournal

final class JournalEntryTests: XCTestCase {
    func testFullTextJoinsSegmentsInOrderRegardlessOfInsertionOrder() {
        let entry = JournalEntry(
            segments: [
                EntrySegment(text: "second.", languageCode: "en", order: 1),
                EntrySegment(text: "first.", languageCode: "en", order: 0)
            ],
            source: .text
        )

        XCTAssertEqual(entry.fullText, "first. second.")
    }

    func testLanguageCodesAreDistinctInFirstAppearanceOrder() {
        let entry = JournalEntry(
            segments: [
                EntrySegment(text: "Hello.", languageCode: "en", order: 0),
                EntrySegment(text: "Hola.", languageCode: "es", order: 1),
                EntrySegment(text: "Hi again.", languageCode: "en", order: 2),
                EntrySegment(text: "???", languageCode: nil, order: 3)
            ],
            source: .text
        )

        XCTAssertEqual(entry.languageCodes, ["en", "es"])
    }

    func testLanguageCodesEmptyWhenNoSegmentsDetected() {
        let entry = JournalEntry(
            segments: [EntrySegment(text: "???", languageCode: nil, order: 0)],
            source: .text
        )

        XCTAssertEqual(entry.languageCodes, [])
    }
}
