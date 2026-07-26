import Foundation

/// Computes journaling streaks from entry dates.
///
/// A streak counts *distinct calendar days* that have at least one entry, so
/// writing five entries in one evening is still one day. The current streak
/// stays alive if the most recent entry was today or yesterday — that grace
/// day means someone journaling nightly doesn't watch their streak read zero
/// every morning before they've written.
enum StreakCalculator {
    static func currentStreak(dates: [Date], today: Date = .now, calendar: Calendar = .current) -> Int {
        let days = distinctDays(dates, calendar: calendar)
        guard !days.isEmpty else { return 0 }

        let todayStart = calendar.startOfDay(for: today)
        guard let yesterdayStart = calendar.date(byAdding: .day, value: -1, to: todayStart) else { return 0 }

        var cursor: Date
        if days.contains(todayStart) {
            cursor = todayStart
        } else if days.contains(yesterdayStart) {
            cursor = yesterdayStart
        } else {
            return 0
        }

        var streak = 0
        while days.contains(cursor) {
            streak += 1
            guard let previous = calendar.date(byAdding: .day, value: -1, to: cursor) else { break }
            cursor = previous
        }
        return streak
    }

    static func longestStreak(dates: [Date], calendar: Calendar = .current) -> Int {
        let days = distinctDays(dates, calendar: calendar).sorted()
        guard !days.isEmpty else { return 0 }

        var longest = 1
        var running = 1
        for (previous, current) in zip(days, days.dropFirst()) {
            let gap = calendar.dateComponents([.day], from: previous, to: current).day ?? 0
            if gap == 1 {
                running += 1
                longest = max(longest, running)
            } else {
                running = 1
            }
        }
        return longest
    }

    private static func distinctDays(_ dates: [Date], calendar: Calendar) -> Set<Date> {
        Set(dates.map { calendar.startOfDay(for: $0) })
    }
}
