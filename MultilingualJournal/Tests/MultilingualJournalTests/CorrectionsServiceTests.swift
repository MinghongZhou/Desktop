import XCTest
@testable import MultilingualJournal

final class CorrectionsServiceTests: XCTestCase {
    private let segments = [
        EntrySegment(text: "Yo tiene un perro.", languageCode: "es", order: 0),
        EntrySegment(text: "Me gusta correr.", languageCode: "es", order: 1)
    ]

    func testParsesPlainJSON() throws {
        let raw = """
        {"corrections": [{"segmentIndex": 0, "suggestion": "Yo tengo un perro.", "note": "Conjugate tener as tengo for yo."}]}
        """

        let corrections = try CorrectionsService.parseCorrections(from: raw, targetSegments: segments)

        XCTAssertEqual(corrections.count, 1)
        XCTAssertEqual(corrections[0].segmentID, segments[0].id)
        XCTAssertEqual(corrections[0].originalText, "Yo tiene un perro.")
        XCTAssertEqual(corrections[0].suggestion, "Yo tengo un perro.")
    }

    func testStripsMarkdownCodeFence() throws {
        let raw = """
        ```json
        {"corrections": [{"segmentIndex": 1, "suggestion": "Me gusta correr.", "note": "Already natural!"}]}
        ```
        """

        let corrections = try CorrectionsService.parseCorrections(from: raw, targetSegments: segments)

        XCTAssertEqual(corrections.count, 1)
        XCTAssertEqual(corrections[0].segmentID, segments[1].id)
    }

    func testEmptyCorrectionsArrayReturnsEmpty() throws {
        let raw = #"{"corrections": []}"#

        let corrections = try CorrectionsService.parseCorrections(from: raw, targetSegments: segments)

        XCTAssertTrue(corrections.isEmpty)
    }

    func testOutOfRangeSegmentIndexIsDropped() throws {
        let raw = #"{"corrections": [{"segmentIndex": 5, "suggestion": "x", "note": "y"}]}"#

        let corrections = try CorrectionsService.parseCorrections(from: raw, targetSegments: segments)

        XCTAssertTrue(corrections.isEmpty)
    }

    func testMalformedJSONThrows() {
        let raw = "not json at all"

        XCTAssertThrowsError(try CorrectionsService.parseCorrections(from: raw, targetSegments: segments)) { error in
            XCTAssertTrue(error is CorrectionsService.CorrectionsError)
        }
    }
}
