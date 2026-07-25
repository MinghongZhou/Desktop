import XCTest
@testable import MultilingualJournal

final class StreakCalculatorTests: XCTestCase {
    private let calendar = Calendar(identifier: .gregorian)

    /// Fixed reference "today" so these tests don't drift with the wall clock.
    private var today: Date {
        calendar.date(from: DateComponents(year: 2026, month: 7, day: 25, hour: 14))!
    }

    private func daysAgo(_ count: Int, hour: Int = 10) -> Date {
        let start = calendar.startOfDay(for: today)
        let shifted = calendar.date(byAdding: .day, value: -count, to: start)!
        return calendar.date(byAdding: .hour, value: hour, to: shifted)!
    }

    func testNoEntriesMeansNoStreak() {
        XCTAssertEqual(StreakCalculator.currentStreak(dates: [], today: today, calendar: calendar), 0)
        XCTAssertEqual(StreakCalculator.longestStreak(dates: [], calendar: calendar), 0)
    }

    func testConsecutiveDaysEndingTodayCount() {
        let dates = [daysAgo(0), daysAgo(1), daysAgo(2)]
        XCTAssertEqual(StreakCalculator.currentStreak(dates: dates, today: today, calendar: calendar), 3)
    }

    func testMultipleEntriesSameDayCountOnce() {
        let dates = [daysAgo(0, hour: 9), daysAgo(0, hour: 21), daysAgo(1)]
        XCTAssertEqual(StreakCalculator.currentStreak(dates: dates, today: today, calendar: calendar), 2)
    }

    func testStreakSurvivesWhenLatestEntryWasYesterday() {
        // The grace day: nothing written yet today shouldn't zero the streak.
        let dates = [daysAgo(1), daysAgo(2)]
        XCTAssertEqual(StreakCalculator.currentStreak(dates: dates, today: today, calendar: calendar), 2)
    }

    func testStreakBreaksAfterTwoQuietDays() {
        let dates = [daysAgo(2), daysAgo(3)]
        XCTAssertEqual(StreakCalculator.currentStreak(dates: dates, today: today, calendar: calendar), 0)
    }

    func testGapStopsTheCurrentStreak() {
        let dates = [daysAgo(0), daysAgo(1), daysAgo(3), daysAgo(4)]
        XCTAssertEqual(StreakCalculator.currentStreak(dates: dates, today: today, calendar: calendar), 2)
    }

    func testLongestStreakFindsBestRunNotTheCurrentOne() {
        // Current run is 1 day; the older run is 3.
        let dates = [daysAgo(0), daysAgo(5), daysAgo(6), daysAgo(7)]
        XCTAssertEqual(StreakCalculator.longestStreak(dates: dates, calendar: calendar), 3)
    }

    func testSingleEntryIsALongestStreakOfOne() {
        XCTAssertEqual(StreakCalculator.longestStreak(dates: [daysAgo(4)], calendar: calendar), 1)
    }
}
