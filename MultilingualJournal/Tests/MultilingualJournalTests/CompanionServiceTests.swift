import XCTest
@testable import MultilingualJournal

final class CompanionServiceTests: XCTestCase {
    func testBuildPromptIncludesEntryText() {
        let prompt = CompanionService.buildPrompt(entryText: "Today was calm.", history: [], newUserMessage: nil)
        XCTAssertTrue(prompt.contains("Today was calm."))
        XCTAssertTrue(prompt.contains("opening reflection"))
    }

    func testBuildPromptPrependsMemoryWhenProvided() {
        let memory = "For context, here are a few earlier entries:\n- (yesterday) I was nervous."
        let prompt = CompanionService.buildPrompt(
            entryText: "The presentation went fine.",
            history: [],
            newUserMessage: nil,
            memory: memory
        )
        // Memory appears, and before the current entry.
        let memoryRange = prompt.range(of: "I was nervous.")
        let entryRange = prompt.range(of: "The presentation went fine.")
        XCTAssertNotNil(memoryRange)
        XCTAssertNotNil(entryRange)
        XCTAssertTrue(memoryRange!.lowerBound < entryRange!.lowerBound)
    }

    func testBuildPromptOmitsMemorySectionWhenNil() {
        let prompt = CompanionService.buildPrompt(entryText: "Hi.", history: [], newUserMessage: nil, memory: nil)
        XCTAssertFalse(prompt.contains("For context"))
    }

    func testBuildPromptIncludesHistoryAndNewMessage() {
        let history = [
            CompanionMessage(role: .companion, text: "How did it feel?"),
            CompanionMessage(role: .user, text: "Good, mostly.")
        ]
        let prompt = CompanionService.buildPrompt(entryText: "entry", history: history, newUserMessage: "Tell me more")
        XCTAssertTrue(prompt.contains("How did it feel?"))
        XCTAssertTrue(prompt.contains("Good, mostly."))
        XCTAssertTrue(prompt.contains("Tell me more"))
    }
}
