import SwiftUI

struct LanguageBadge: View {
    let languageCode: String

    private var displayName: String {
        Locale.current.localizedString(forLanguageCode: languageCode)?.capitalized ?? languageCode
    }

    var body: some View {
        Text(displayName)
            .font(.system(size: 12, weight: .semibold))
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(Theme.accentSoft, in: Capsule())
            .foregroundStyle(Theme.accentDeep)
    }
}
