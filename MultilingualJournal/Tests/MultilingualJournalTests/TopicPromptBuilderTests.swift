import XCTest
@testable import MultilingualJournal

final class TopicPromptBuilderTests: XCTestCase {
    func testInsertsHeadlineIntoTemplate() {
        let prompt = TopicPromptBuilder.prompt(headline: "Coffee prices hit a record", languageCode: "en", seed: 0)
        XCTAssertTrue(prompt.contains("Coffee prices hit a record"))
        XCTAssertFalse(prompt.contains(TopicPromptBuilder.placeholder))
    }

    func testSeedRotatesThroughTemplates() {
        let a = TopicPromptBuilder.prompt(headline: "X", languageCode: "en", seed: 0)
        let b = TopicPromptBuilder.prompt(headline: "X", languageCode: "en", seed: 1)
        XCTAssertNotEqual(a, b)
    }

    func testSeedWrapsAroundPool() {
        let count = TopicPromptBuilder.newsTemplates["en"]!.count
        let first = TopicPromptBuilder.prompt(headline: "X", languageCode: "en", seed: 0)
        let wrapped = TopicPromptBuilder.prompt(headline: "X", languageCode: "en", seed: count)
        XCTAssertEqual(first, wrapped)
    }

    func testUsesTargetLanguageTemplate() {
        let es = TopicPromptBuilder.prompt(headline: "Titular", languageCode: "es", seed: 0)
        XCTAssertTrue(es.contains("Titular"))
        // A Spanish template contains Spanish-specific punctuation/words.
        XCTAssertTrue(es.contains("¿") || es.lowercased().contains("hoy") || es.contains("«"))
    }

    func testFallsBackToEnglishForUnknownLanguage() {
        let unknown = TopicPromptBuilder.prompt(headline: "Headline", languageCode: "xx", seed: 0)
        let english = TopicPromptBuilder.prompt(headline: "Headline", languageCode: "en", seed: 0)
        XCTAssertEqual(unknown, english)
    }

    func testHandlesRegionalCodeByBaseLanguage() {
        let zhHans = TopicPromptBuilder.prompt(headline: "标题", languageCode: "zh-Hans", seed: 0)
        let zh = TopicPromptBuilder.prompt(headline: "标题", languageCode: "zh", seed: 0)
        XCTAssertEqual(zhHans, zh)
    }

    func testEvergreenIsNonEmptyAndHeadlineFree() {
        let prompt = TopicPromptBuilder.evergreen(languageCode: "en", seed: 0)
        XCTAssertFalse(prompt.isEmpty)
        XCTAssertFalse(prompt.contains(TopicPromptBuilder.placeholder))
    }
}
