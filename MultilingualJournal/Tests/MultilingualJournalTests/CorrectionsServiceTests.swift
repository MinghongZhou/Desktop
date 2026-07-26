import XCTest
@testable import MultilingualJournal

final class CorrectionsServiceTests: XCTestCase {
    private let segments = [
        EntrySegment(text: "Yo tiene un perro.", languageCode: "es", order: 0),
        EntrySegment(text: "Me gusta correr.", languageCode: "es", order: 1)
    ]

    func testMapsDraftToItsSegment() {
        let drafts = [
            CorrectionsService.CorrectionDraft(segmentIndex: 0, suggestion: "Yo tengo un perro.", note: "Conjugate tener as tengo for yo.")
        ]

        let corrections = CorrectionsService.mapDrafts(drafts, targetSegments: segments)

        XCTAssertEqual(corrections.count, 1)
        XCTAssertEqual(corrections[0].segmentID, segments[0].id)
        XCTAssertEqual(corrections[0].originalText, "Yo tiene un perro.")
        XCTAssertEqual(corrections[0].suggestion, "Yo tengo un perro.")
    }

    func testEmptyDraftsYieldNoCorrections() {
        XCTAssertTrue(CorrectionsService.mapDrafts([], targetSegments: segments).isEmpty)
    }

    func testOutOfRangeSegmentIndexIsDropped() {
        let drafts = [CorrectionsService.CorrectionDraft(segmentIndex: 5, suggestion: "x", note: "y")]
        XCTAssertTrue(CorrectionsService.mapDrafts(drafts, targetSegments: segments).isEmpty)
    }

    func testMultipleDraftsMapToCorrectSegments() {
        let drafts = [
            CorrectionsService.CorrectionDraft(segmentIndex: 1, suggestion: "Me gusta correr mucho.", note: "A touch more natural."),
            CorrectionsService.CorrectionDraft(segmentIndex: 0, suggestion: "Yo tengo un perro.", note: "Verb agreement.")
        ]

        let corrections = CorrectionsService.mapDrafts(drafts, targetSegments: segments)

        XCTAssertEqual(corrections.count, 2)
        XCTAssertEqual(corrections[0].segmentID, segments[1].id)
        XCTAssertEqual(corrections[1].segmentID, segments[0].id)
    }

    func testPromptNumbersSentencesFromZero() {
        let prompt = CorrectionsService.prompt(for: ["Uno.", "Dos."])
        XCTAssertTrue(prompt.contains("0. Uno."))
        XCTAssertTrue(prompt.contains("1. Dos."))
    }
}
