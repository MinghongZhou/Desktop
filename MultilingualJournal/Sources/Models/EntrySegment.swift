import Foundation

/// A contiguous run of text detected as a single language within an entry.
/// Kept separate (rather than flattening the transcript) so code-switched
/// entries can be displayed and searched language-aware.
struct EntrySegment: Codable, Hashable, Identifiable {
    var id: UUID = UUID()
    var text: String
    /// BCP-47 language code, e.g. "en", "es", "zh-Hans". Nil if detection was inconclusive.
    var languageCode: String?
    var order: Int

    var languageDisplayName: String {
        guard let languageCode else { return "Unknown" }
        return Locale.current.localizedString(forLanguageCode: languageCode) ?? languageCode
    }
}
