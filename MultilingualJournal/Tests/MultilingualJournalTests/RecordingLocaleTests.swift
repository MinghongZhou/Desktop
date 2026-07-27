import XCTest
@testable import MultilingualJournal

final class RecordingLocaleTests: XCTestCase {
    private let supported = ["en-US", "es-ES", "zh-Hans-CN", "fr-FR"]

    func testPrefersSavedChoiceWhenSupported() {
        let result = RecordingLocale.resolve(
            savedIdentifier: "zh-Hans-CN",
            supported: supported,
            deviceLanguageCode: "en"
        )
        XCTAssertEqual(result, "zh-Hans-CN")
    }

    func testFallsBackToDeviceLanguageWhenNoSavedChoice() {
        let result = RecordingLocale.resolve(
            savedIdentifier: nil,
            supported: supported,
            deviceLanguageCode: "es"
        )
        XCTAssertEqual(result, "es-ES")
    }

    func testIgnoresSavedChoiceThatIsNoLongerSupported() {
        let result = RecordingLocale.resolve(
            savedIdentifier: "de-DE",
            supported: supported,
            deviceLanguageCode: "fr"
        )
        XCTAssertEqual(result, "fr-FR")
    }

    func testFallsBackToFirstSupportedWhenDeviceLanguageUnavailable() {
        let result = RecordingLocale.resolve(
            savedIdentifier: nil,
            supported: supported,
            deviceLanguageCode: "ja"
        )
        XCTAssertEqual(result, "en-US")
    }

    func testReturnsNilWhenNothingSupported() {
        XCTAssertNil(RecordingLocale.resolve(savedIdentifier: "en-US", supported: [], deviceLanguageCode: "en"))
    }

    func testLanguageCodeExtraction() {
        XCTAssertEqual(RecordingLocale.languageCode(of: "en-US"), "en")
        XCTAssertEqual(RecordingLocale.languageCode(of: "zh-Hans-CN"), "zh")
        XCTAssertEqual(RecordingLocale.languageCode(of: "es_ES"), "es")
    }
}
