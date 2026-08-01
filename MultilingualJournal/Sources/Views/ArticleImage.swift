import SwiftUI

/// Loads and displays an article thumbnail from a URL, with a warm placeholder
/// while loading and nothing shown on failure (so a broken image never leaves
/// an ugly gap). Rounded to match the card aesthetic.
struct ArticleImage: View {
    let url: URL
    var height: CGFloat = 130

    var body: some View {
        AsyncImage(url: url) { phase in
            switch phase {
            case .success(let image):
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            case .empty:
                Theme.neutral
                    .overlay(ProgressView().tint(Theme.secondary))
            case .failure:
                // A clean muted block with a subtle icon, never a broken image.
                Theme.neutral.overlay(
                    Image(systemName: "newspaper")
                        .font(.title2)
                        .foregroundStyle(Theme.secondary.opacity(0.5))
                )
            @unknown default:
                Theme.neutral
            }
        }
        .frame(maxWidth: .infinity)
        .frame(height: height)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}
