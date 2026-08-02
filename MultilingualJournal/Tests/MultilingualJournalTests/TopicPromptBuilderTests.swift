import XCTest
@testable import MultilingualJournal

final class TopicPromptBuilderTests: XCTestCase {
    func testNonEnglishTemplateInsertsHeadline() {
        // Non-English templates still quote the headline (hand-verified copy).
        let prompt = TopicPromptBuilder.prompt(headline: "Titular único", languageCode: "es")
        XCTAssertTrue(prompt.contains("Titular único"))
        XCTAssertFalse(prompt.contains(TopicPromptBuilder.placeholder))
    }

    func testEnglishPromptDoesNotRequoteHeadline() {
        // The headline is shown separately in the card, so English prompts
        // should ask the question directly rather than re-quote it.
        let headline = "Coffee prices hit an unusual record today"
        let prompt = TopicPromptBuilder.prompt(headline: headline, languageCode: "en")
        XCTAssertFalse(prompt.contains(headline))
        XCTAssertFalse(prompt.contains(TopicPromptBuilder.placeholder))
        XCTAssertFalse(prompt.isEmpty)
    }

    func testSelectionIsStableForSameHeadline() {
        let a = TopicPromptBuilder.prompt(headline: "A stable headline", languageCode: "en")
        let b = TopicPromptBuilder.prompt(headline: "A stable headline", languageCode: "en")
        XCTAssertEqual(a, b)
    }

    func testDifferentHeadlinesSpreadAcrossTemplates() {
        // Across a batch of headlines we should see more than one template used.
        let prompts = Set((0..<40).map {
            TopicPromptBuilder.prompt(headline: "Headline number \($0)", languageCode: "en")
        })
        XCTAssertGreaterThan(prompts.count, 1)
    }

    func testUsesTargetLanguageTemplate() {
        let es = TopicPromptBuilder.prompt(headline: "Titular", languageCode: "es")
        XCTAssertTrue(es.contains("Titular"))
        // A Spanish template contains Spanish-specific punctuation/words.
        XCTAssertTrue(es.contains("¿") || es.lowercased().contains("hoy") || es.contains("«"))
    }

    func testFallsBackToEnglishForUnknownLanguage() {
        let unknown = TopicPromptBuilder.prompt(headline: "Headline", languageCode: "xx")
        let english = TopicPromptBuilder.prompt(headline: "Headline", languageCode: "en")
        XCTAssertEqual(unknown, english)
    }

    func testHandlesRegionalCodeByBaseLanguage() {
        let zhHans = TopicPromptBuilder.prompt(headline: "标题", languageCode: "zh-Hans")
        let zh = TopicPromptBuilder.prompt(headline: "标题", languageCode: "zh")
        XCTAssertEqual(zhHans, zh)
    }

    func testEvergreenIsNonEmptyAndHeadlineFree() {
        let prompt = TopicPromptBuilder.evergreen(languageCode: "en", seed: 0)
        XCTAssertFalse(prompt.isEmpty)
        XCTAssertFalse(prompt.contains(TopicPromptBuilder.placeholder))
    }
}
