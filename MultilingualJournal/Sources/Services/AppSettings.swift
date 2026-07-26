import Foundation

/// Lightweight app-wide settings backed by UserDefaults (non-sensitive,
/// unlike the API key which lives in Keychain — see KeychainService).
enum AppSettings {
    static let targetLanguageCodeKey = "targetLanguageCode"
    static let autoSpeakRepliesKey = "autoSpeakCompanionReplies"
    static let dailyReminderEnabledKey = "dailyReminderEnabled"
    /// Reminder time stored as minutes past midnight, so it survives as a
    /// plain Int in UserDefaults rather than needing Date encoding.
    static let dailyReminderMinutesKey = "dailyReminderMinutes"

    static let defaultReminderMinutes = 20 * 60  // 8:00 PM

    /// The language the user is learning, used to decide which entry
    /// segments the Corrections feature should look at. Nil/empty means
    /// "not set yet" — corrections stay off until the user picks one.
    static var targetLanguageCode: String? {
        let value = UserDefaults.standard.string(forKey: targetLanguageCodeKey)
        return (value?.isEmpty ?? true) ? nil : value
    }
}
