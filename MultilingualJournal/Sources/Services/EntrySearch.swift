import Foundation

/// Filters entries for the timeline's search field.
///
/// Matching is deliberately case- *and* diacritic-insensitive: in a
/// multilingual journal, typing "dia" should still find "día" and "cafe"
/// should find "café", since users often search without switching keyboard
/// layouts or reaching for accented characters.
enum EntrySearch {
    static func filter(_ entries: [JournalEntry], query: String) -> [JournalEntry] {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return entries }
        return entries.filter { matches($0, query: trimmed) }
    }

    static func matches(_ entry: JournalEntry, query: String) -> Bool {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return true }

        if contains(entry.fullText, trimmed) { return true }

        // Also match on language names ("spanish", "japanese") so a user can
        // pull up everything they wrote in a given language without
        // remembering specific words from it.
        return entry.languageCodes.contains { code in
            guard let name = Locale.current.localizedString(forLanguageCode: code) else { return false }
            return contains(name, trimmed)
        }
    }

    private static func contains(_ haystack: String, _ needle: String) -> Bool {
        haystack.range(of: needle, options: [.caseInsensitive, .diacriticInsensitive]) != nil
    }
}
