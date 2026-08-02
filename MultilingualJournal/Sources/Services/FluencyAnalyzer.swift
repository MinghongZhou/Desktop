import Foundation
import NaturalLanguage

/// One entry's share of words written in the target language, for the trend line.
struct FluencyPoint: Equatable {
    let date: Date
    /// 0…1 — fraction of the entry's words that were in the target language.
    let targetRatio: Double
}

/// Honest, data-backed fluency signal computed from the user's own entries —
/// no fabricated scores. Every number here is derived from what they actually
/// wrote, which is the whole differentiator: your real corpus, not a quiz.
struct FluencySummary: Equatable {
    /// Per-entry target-language ratio over time, oldest → newest.
    var points: [FluencyPoint]
    /// Average target-language ratio across the most recent entries (0…1).
    var currentTargetRatio: Double
    /// Same for the earlier entries, so the UI can show a trend (0…1).
    var earlierTargetRatio: Double
    /// Average words per target-language sentence — a simple complexity proxy.
    var avgWordsPerSentence: Double
    /// Average language switches per entry (recent) — the app's signature metric.
    var codeSwitchRate: Double
    /// True once there are at least two data points to show a trend.
    var hasTrend: Bool

    static let empty = FluencySummary(
        points: [], currentTargetRatio: 0, earlierTargetRatio: 0,
        avgWordsPerSentence: 0, codeSwitchRate: 0, hasTrend: false
    )

    /// Positive = leaning on the target language more than before.
    var ratioDelta: Double { currentTargetRatio - earlierTargetRatio }
}

enum FluencyAnalyzer {
    /// Counts word tokens (letters only — skips numbers/punctuation). Uses
    /// `NLTokenizer` so spaceless languages (zh/ja/th) count correctly.
    static func wordCount(_ text: String) -> Int {
        let tokenizer = NLTokenizer(unit: .word)
        tokenizer.string = text
        var count = 0
        tokenizer.enumerateTokens(in: text.startIndex..<text.endIndex) { range, _ in
            if text[range].rangeOfCharacter(from: .letters) != nil { count += 1 }
            return true
        }
        return count
    }

    /// Fraction of an entry's words that are in the target language, or nil if
    /// the entry has no countable words.
    static func targetRatio(for entry: JournalEntry, targetCode: String) -> Double? {
        var total = 0
        var target = 0
        for segment in entry.segments {
            let count = wordCount(segment.text)
            total += count
            if segment.languageCode == targetCode { target += count }
        }
        guard total > 0 else { return nil }
        return Double(target) / Double(total)
    }

    /// Number of times the language changes between consecutive segments —
    /// a proxy for how often the writer fell out of the target language.
    static func codeSwitches(in entry: JournalEntry) -> Int {
        let langs = entry.segments.sorted { $0.order < $1.order }.compactMap(\.languageCode)
        guard langs.count > 1 else { return 0 }
        return zip(langs, langs.dropFirst()).reduce(0) { $0 + ($1.0 == $1.1 ? 0 : 1) }
    }

    static func summary(for entries: [JournalEntry], targetCode: String, recentCount: Int = 5) -> FluencySummary {
        guard !targetCode.isEmpty else { return .empty }
        let sorted = entries.sorted { $0.date < $1.date }

        let points = sorted.compactMap { entry -> FluencyPoint? in
            guard let ratio = targetRatio(for: entry, targetCode: targetCode) else { return nil }
            return FluencyPoint(date: entry.date, targetRatio: ratio)
        }
        guard !points.isEmpty else { return .empty }

        let recentPoints = Array(points.suffix(recentCount))
        let earlierPoints = points.count > recentCount ? Array(points.dropLast(recentPoints.count)) : []
        let current = average(recentPoints.map(\.targetRatio))
        let earlier = earlierPoints.isEmpty ? current : average(earlierPoints.map(\.targetRatio))

        // Complexity + code-switch over the recent *entries* (not just points).
        let recentEntries = Array(sorted.suffix(recentCount))
        let targetSegments = recentEntries.flatMap { $0.segments.filter { $0.languageCode == targetCode } }
        let avgWPS = targetSegments.isEmpty
            ? 0
            : Double(targetSegments.map { wordCount($0.text) }.reduce(0, +)) / Double(targetSegments.count)
        let csRate = recentEntries.isEmpty
            ? 0
            : Double(recentEntries.map { codeSwitches(in: $0) }.reduce(0, +)) / Double(recentEntries.count)

        return FluencySummary(
            points: points,
            currentTargetRatio: current,
            earlierTargetRatio: earlier,
            avgWordsPerSentence: avgWPS,
            codeSwitchRate: csRate,
            hasTrend: points.count >= 2
        )
    }

    private static func average(_ values: [Double]) -> Double {
        values.isEmpty ? 0 : values.reduce(0, +) / Double(values.count)
    }
}
