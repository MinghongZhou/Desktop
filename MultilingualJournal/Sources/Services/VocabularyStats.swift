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
                for word in words(in: segment.text)
                where firstUse[word] == nil && !isStopword(word, languageCode: languageCode) {
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

    /// The language portion of a code ("en-US" -> "en"), lowercased.
    private static func base(_ code: String) -> String {
        code.split(whereSeparator: { $0 == "-" || $0 == "_" }).first.map(String.init)?.lowercased()
            ?? code.lowercased()
    }

    /// Whether a (already lowercased) word is a trivial function/filler word in
    /// the given language. Filtering these keeps "distinct words" and "new
    /// words" meaningful as a signal of vocabulary growth — "was, day, really"
    /// shouldn't read as earned vocabulary.
    static func isStopword(_ word: String, languageCode: String) -> Bool {
        stopwords[base(languageCode)]?.contains(word) ?? false
    }

    /// Small, deliberately conservative stopword lists. English + Spanish are
    /// covered per the polish spec; other languages simply aren't filtered
    /// (they fall through to counting everything, as before).
    static let stopwords: [String: Set<String>] = [
        "en": [
            "the", "a", "an", "and", "or", "but", "if", "then", "so", "as", "of",
            "to", "in", "on", "at", "by", "for", "with", "from", "into", "about",
            "is", "am", "are", "was", "were", "be", "been", "being", "do", "does",
            "did", "have", "has", "had", "will", "would", "can", "could", "should",
            "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
            "them", "my", "your", "his", "its", "our", "their", "this", "that",
            "these", "those", "there", "here", "not", "no", "yes", "just", "very",
            "really", "too", "also", "than", "some", "any", "all", "good", "day",
            "today", "up", "out", "so", "like",
        ],
        "es": [
            "el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "u",
            "pero", "que", "de", "del", "en", "a", "al", "con", "por", "para",
            "sin", "se", "su", "sus", "mi", "mis", "tu", "tus", "lo", "le", "les",
            "me", "te", "nos", "es", "era", "soy", "eres", "son", "fue", "muy",
            "más", "menos", "no", "sí", "ya", "yo", "él", "ella", "ellos", "este",
            "esta", "esto", "ese", "esa", "eso", "día", "hoy", "bueno", "buena",
            "como", "cuando", "porque", "también",
        ],
    ]

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
