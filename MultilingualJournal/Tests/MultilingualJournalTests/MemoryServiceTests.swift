import XCTest
@testable import MultilingualJournal

final class MemoryServiceTests: XCTestCase {
    private let calendar = Calendar(identifier: .gregorian)
    private var now: Date { calendar.date(from: DateComponents(year: 2026, month: 8, day: 1, hour: 12))! }
    private func daysAgo(_ n: Int) -> Date { calendar.date(byAdding: .day, value: -n, to: now)! }

    private func entry(_ text: String, date: Date) -> JournalEntry {
        JournalEntry(date: date, segments: [EntrySegment(text: text, languageCode: "en", order: 0)], source: .text)
    }

    func testKeywordsDropShortAndCommonWords() {
        let kw = MemoryService.keywords("I was really nervous about the presentation today")
        XCTAssertTrue(kw.contains("nervous"))
        XCTAssertTrue(kw.contains("presentation"))
        XCTAssertFalse(kw.contains("was"))     // < 4 chars
        XCTAssertFalse(kw.contains("really"))  // common word
        XCTAssertFalse(kw.contains("today"))   // common word
    }

    func testSelectsEntriesSharingKeywordsFirst() {
        let current = entry("Feeling nervous about the presentation", date: now)
        let related = entry("The presentation went better than expected", date: daysAgo(10))
        let unrelated = entry("Cooked pasta for dinner", date: daysAgo(1))

        let picked = MemoryService.selectEntries(for: current, from: [unrelated, related, current], maxEntries: 1)
        XCTAssertEqual(picked.count, 1)
        XCTAssertTrue(picked.first?.fullText.contains("presentation went better") == true)
    }

    func testExcludesCurrentEntryAndFutureEntries() {
        let current = entry("today's entry", date: daysAgo(5))
        let future = entry("later entry", date: now)
        let past = entry("earlier entry", date: daysAgo(10))

        let picked = MemoryService.selectEntries(for: current, from: [current, future, past], maxEntries: 5)
        XCTAssertEqual(picked.count, 1)
        XCTAssertEqual(picked.first?.fullText, "earlier entry")
    }

    func testFallsBackToRecentWhenNoOverlap() {
        let current = entry("quantum mechanics lecture", date: now)
        let older = entry("beach trip", date: daysAgo(20))
        let newer = entry("garden weeding", date: daysAgo(2))

        let picked = MemoryService.selectEntries(for: current, from: [older, newer], maxEntries: 1)
        // No keyword overlap → most recent wins.
        XCTAssertEqual(picked.first?.fullText, "garden weeding")
    }

    func testContextIsNilWithNoOtherEntries() {
        let current = entry("only entry", date: now)
        XCTAssertNil(MemoryService.context(for: current, from: [current], now: now))
    }

    func testContextIncludesPickedEntryTextChronologically() {
        let current = entry("nervous about the presentation again", date: now)
        let a = entry("first presentation prep", date: daysAgo(10))
        let b = entry("presentation feedback was good", date: daysAgo(2))

        let context = MemoryService.context(for: current, from: [b, a, current], maxEntries: 2, now: now)
        XCTAssertNotNil(context)
        // Both selected; oldest appears before newest in the block.
        let idxA = context!.range(of: "first presentation prep")
        let idxB = context!.range(of: "presentation feedback was good")
        XCTAssertNotNil(idxA)
        XCTAssertNotNil(idxB)
        XCTAssertTrue(idxA!.lowerBound < idxB!.lowerBound)
    }
}
