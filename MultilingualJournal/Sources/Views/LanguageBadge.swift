import SwiftUI

struct LanguageBadge: View {
    let languageCode: String

    private var displayName: String {
        Locale.current.localizedString(forLanguageCode: languageCode)?.capitalized ?? languageCode
    }

    var body: some View {
        Text(displayName)
            .font(.caption2.weight(.medium))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(.tint.opacity(0.15), in: Capsule())
            .foregroundStyle(.tint)
    }
}
