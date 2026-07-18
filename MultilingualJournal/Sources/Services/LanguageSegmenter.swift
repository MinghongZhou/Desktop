import Foundation
import NaturalLanguage

/// Splits a transcript into sentence-level segments and tags each with a
/// detected language, so a single entry can preserve code-switching instead
/// of being flattened to one language.
enum LanguageSegmenter {
    static func segment(_ text: String) -> [EntrySegment] {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return [] }

        let tokenizer = NLTokenizer(unit: .sentence)
        tokenizer.string = trimmed

        var segments: [EntrySegment] = []
        var order = 0
        tokenizer.enumerateTokens(in: trimmed.startIndex..<trimmed.endIndex) { range, _ in
            let sentence = String(trimmed[range]).trimmingCharacters(in: .whitespacesAndNewlines)
            guard !sentence.isEmpty else { return true }

            let recognizer = NLLanguageRecognizer()
            recognizer.processString(sentence)
            let languageCode = recognizer.dominantLanguage?.rawValue

            segments.append(EntrySegment(text: sentence, languageCode: languageCode, order: order))
            order += 1
            return true
        }

        // Fallback: tokenizer found no sentence boundaries (e.g. no punctuation).
        if segments.isEmpty {
            let recognizer = NLLanguageRecognizer()
            recognizer.processString(trimmed)
            segments.append(EntrySegment(text: trimmed, languageCode: recognizer.dominantLanguage?.rawValue, order: 0))
        }

        return segments
    }
}
