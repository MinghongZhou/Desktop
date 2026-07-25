import Foundation

/// Lightweight app-wide settings backed by UserDefaults (non-sensitive,
/// unlike the API key which lives in Keychain — see KeychainService).
enum AppSettings {
    static let targetLanguageCodeKey = "targetLanguageCode"
    static let autoSpeakRepliesKey = "autoSpeakCompanionReplies"

    /// The language the user is learning, used to decide which entry
    /// segments the Corrections feature should look at. Nil/empty means
    /// "not set yet" — corrections stay off until the user picks one.
    static var targetLanguageCode: String? {
        let value = UserDefaults.standard.string(forKey: targetLanguageCodeKey)
        return (value?.isEmpty ?? true) ? nil : value
    }
}
