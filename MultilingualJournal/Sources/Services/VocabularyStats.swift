import Foundation
import NaturalLanguage

/// Tracks which words the user has actually used in the language they're
/// learning, based only on segments already tagged as that language.
///
/// This is a "words you've used" count, not a "words you know" claim — it
/// says nothing about whether they were used correctly, and a typo or a
/// misrecognized word counts the same as a real one. Presented as
/// encouragement, not assessment.
struct VocabularyStats: Equatable {
    /// Every distinct word used in the target language, all time.
    var totalUniqueWords: Int
    /// Words whose *first* appearance falls inside the requested period.
    var newWordsInPeriod: Int
    /// A sample of those new words, most recent first, for display.
    var recentNewWords: [String]

    static let empty = VocabularyStats(totalUniqueWords: 0, newWordsInPeriod: 0, recentNewWords: [])
}

enum VocabularyAnalyzer {
    /// - Parameters:
    ///   - since: start of the "new words" window (e.g. 30 days ago).
    ///   - sampleLimit: how many recent new words to return for display.
    static func stats(
        for entries: [JournalEntry],
        languageCode: String,
        since: Date,
        sampleLimit: Int = 12
    ) -> VocabularyStats {
        // First use wins, so a word repeated later isn't counted as "new" again.
        var firstUse: [String: Date] = [:]

        for entry in entries.sorted(by: { $0.date < $1.date }) {
            for segment in entry.segments where segment.languageCode == languageCode {
                for word in words(in: segment.text) where firstUse[word] == nil {
                    firstUse[word] = entry.date
                }
            }
        }

        guard !firstUse.isEmpty else { return .empty }

        let newWords = firstUse
            .filter { $0.value >= since }
            .sorted { $0.value > $1.value }

        return VocabularyStats(
            totalUniqueWords: firstUse.count,
            newWordsInPeriod: newWords.count,
            recentNewWords: newWords.prefix(sampleLimit).map(\.key)
        )
    }

    /// Word-tokenizes text and normalizes for counting. Uses `NLTokenizer`
    /// rather than splitting on spaces so languages without spaces between
    /// words (Chinese, Japanese, Thai) segment correctly instead of counting
    /// a whole clause as one "word".
    static func words(in text: String) -> Set<String> {
        let tokenizer = NLTokenizer(unit: .word)
        tokenizer.string = text

        var result: Set<String> = []
        tokenizer.enumerateTokens(in: text.startIndex..<text.endIndex) { range, _ in
            let token = text[range]
                .lowercased()
                .trimmingCharacters(in: .punctuationCharacters)
            // Skip pure numbers and anything left empty after trimming.
            if !token.isEmpty, token.rangeOfCharacter(from: .letters) != nil {
                result.insert(token)
            }
            return true
        }
        return result
    }
}
