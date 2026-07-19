import XCTest
@testable import MultilingualJournal

final class LanguageSegmenterTests: XCTestCase {
    func testEmptyStringProducesNoSegments() {
        XCTAssertEqual(LanguageSegmenter.segment(""), [])
        XCTAssertEqual(LanguageSegmenter.segment("   \n  "), [])
    }

    func testSplitsIntoSentencesWithIncreasingOrder() {
        let text = "The weather today was absolutely beautiful. I felt very happy about it."
        let segments = LanguageSegmenter.segment(text)

        XCTAssertEqual(segments.count, 2)
        XCTAssertEqual(segments.map(\.order), [0, 1])
        XCTAssertEqual(segments[0].text, "The weather today was absolutely beautiful.")
        XCTAssertEqual(segments[1].text, "I felt very happy about it.")
    }

    func testDetectsDistinctLanguagesPerSentence() {
        // NLLanguageRecognizer confidence improves with longer, unambiguous
        // sentences, so these are deliberately not short fragments.
        let text = "The weather today was absolutely beautiful and I felt very happy. Hoy fue un día maravilloso y me sentí muy feliz."
        let segments = LanguageSegmenter.segment(text)

        XCTAssertEqual(segments.count, 2)
        XCTAssertEqual(segments[0].languageCode, "en")
        XCTAssertEqual(segments[1].languageCode, "es")
    }

    func testFallsBackToSingleSegmentWithoutSentencePunctuation() {
        let segments = LanguageSegmenter.segment("just some words with no terminal punctuation")

        XCTAssertEqual(segments.count, 1)
        XCTAssertEqual(segments[0].order, 0)
        XCTAssertEqual(segments[0].text, "just some words with no terminal punctuation")
    }
}
