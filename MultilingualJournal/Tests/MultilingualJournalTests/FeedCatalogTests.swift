import XCTest
@testable import MultilingualJournal

final class FeedCatalogTests: XCTestCase {
    func testKnownLanguageReturnsItsFeed() {
        XCTAssertEqual(FeedCatalog.feed(for: "es").publisher, "BBC Mundo")
        XCTAssertEqual(FeedCatalog.feed(for: "fr").publisher, "Le Monde")
    }

    func testRegionalCodeResolvesToBaseLanguage() {
        XCTAssertEqual(FeedCatalog.feed(for: "zh-Hans"), FeedCatalog.feed(for: "zh"))
        XCTAssertEqual(FeedCatalog.feed(for: "es_MX").publisher, "BBC Mundo")
    }

    func testUnknownLanguageFallsBackToEnglish() {
        XCTAssertEqual(FeedCatalog.feed(for: "xx"), FeedCatalog.english)
    }

    func testHasNativeFeed() {
        XCTAssertTrue(FeedCatalog.hasNativeFeed(for: "ja"))
        XCTAssertTrue(FeedCatalog.hasNativeFeed(for: "zh-Hant"))
        XCTAssertFalse(FeedCatalog.hasNativeFeed(for: "sv"))
    }

    func testFeedURLsAreValid() {
        for code in ["en", "es", "fr", "zh", "ja", "ar"] {
            XCTAssertNotNil(URL(string: FeedCatalog.feed(for: code).url), "invalid URL for \(code)")
        }
    }
}
