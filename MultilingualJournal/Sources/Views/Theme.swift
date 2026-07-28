import SwiftUI

/// Visual design system adapted from the "Voice Journal" design handoff:
/// a warm cream-and-terracotta palette with editorial serif headings.
///
/// Colors were converted from the design's oklch values to sRGB. The design
/// commits to a single warm light look, so these are fixed (not dark-mode
/// adaptive) and the app pins a light color scheme at the root. Fonts use the
/// system serif (New York) to approximate Lora, and the default sans for body
/// in place of Karla — close in character without bundling font files.
enum Theme {
    // Backgrounds
    static let bg = Color(red: 0.984, green: 0.957, blue: 0.922)
    static let bgRecord = Color(red: 0.278, green: 0.169, blue: 0.129)
    static let card = Color(red: 1.0, green: 0.992, blue: 0.976)

    // Accents (terracotta family)
    static let accent = Color(red: 0.776, green: 0.408, blue: 0.275)
    static let accentDeep = Color(red: 0.553, green: 0.255, blue: 0.161)
    static let accentSoft = Color(red: 0.980, green: 0.886, blue: 0.847)

    // Sage (used for positive stats)
    static let sageSoft = Color(red: 0.847, green: 0.937, blue: 0.863)
    static let sageDark = Color(red: 0.078, green: 0.275, blue: 0.137)

    // Neutrals & text
    static let neutral = Color(red: 0.945, green: 0.918, blue: 0.890)
    static let line = Color(red: 0.894, green: 0.867, blue: 0.831)
    static let heading = Color(red: 0.173, green: 0.133, blue: 0.106)
    static let bodyText = Color(red: 0.212, green: 0.169, blue: 0.141)
    static let secondary = Color(red: 0.447, green: 0.400, blue: 0.369)

    // Record screen (dark)
    static let recordRing = Color(red: 0.922, green: 0.769, blue: 0.702)
    static let recordWave = Color(red: 0.831, green: 0.682, blue: 0.616)
    static let recordMuted = Color(red: 0.847, green: 0.796, blue: 0.757)

    static let cardShadow = Color(red: 60 / 255, green: 40 / 255, blue: 20 / 255).opacity(0.06)

    // Serif (Lora stand-in) for headings and companion reflections.
    static func serif(_ size: CGFloat, weight: Font.Weight = .semibold) -> Font {
        .system(size: size, weight: weight, design: .serif)
    }
}

/// Soft rounded surface with the design's warm drop shadow.
private struct WarmCard: ViewModifier {
    var cornerRadius: CGFloat = 18
    func body(content: Content) -> some View {
        content
            .background(Theme.card, in: RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
            .shadow(color: Theme.cardShadow, radius: 12, x: 0, y: 8)
    }
}

extension View {
    func warmCard(cornerRadius: CGFloat = 18) -> some View {
        modifier(WarmCard(cornerRadius: cornerRadius))
    }

    /// An uppercase section label matching the design's small headers.
    func sectionLabel() -> some View {
        self
            .font(.system(size: 13, weight: .bold))
            .foregroundStyle(Theme.secondary)
            .textCase(.uppercase)
            .kerning(0.5)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Terracotta pill button used for primary actions (Save, Begin, etc.).
struct TerracottaButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 16, weight: .bold))
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(16)
            .background(Theme.accent.opacity(configuration.isPressed ? 0.85 : 1), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}
