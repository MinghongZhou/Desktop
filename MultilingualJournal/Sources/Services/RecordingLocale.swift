import Foundation

/// Chooses which locale the speech recognizer should use for a recording.
///
/// Apple's recognizer is locale-locked — it can't detect the spoken language
/// or switch mid-recording — so the language must be chosen up front. To make
/// that less annoying, the app remembers the last language used; this resolves
/// a saved choice against what the recognizer actually supports, falling back
/// to the device language, then to any supported locale.
enum RecordingLocale {
    /// - Parameters:
    ///   - savedIdentifier: the previously chosen locale identifier, if any.
    ///   - supported: locale identifiers the recognizer supports.
    ///   - deviceLanguageCode: the device's language code (e.g. "en", "zh").
    /// - Returns: the identifier to record with, or nil if nothing is supported.
    static func resolve(
        savedIdentifier: String?,
        supported: [String],
        deviceLanguageCode: String?
    ) -> String? {
        // 1. The saved choice, if it's still supported.
        if let savedIdentifier, supported.contains(savedIdentifier) {
            return savedIdentifier
        }
        // 2. A supported locale matching the device's language.
        if let deviceLanguageCode,
           let match = supported.first(where: { languageCode(of: $0) == deviceLanguageCode }) {
            return match
        }
        // 3. Anything supported, or nil if the list is empty.
        return supported.first
    }

    /// The language portion of a locale identifier ("en-US" -> "en",
    /// "zh-Hans-CN" -> "zh"), lowercased for comparison.
    static func languageCode(of identifier: String) -> String {
        let separator: Character = identifier.contains("-") ? "-" : "_"
        return identifier.split(separator: separator).first.map { $0.lowercased() } ?? identifier.lowercased()
    }
}
