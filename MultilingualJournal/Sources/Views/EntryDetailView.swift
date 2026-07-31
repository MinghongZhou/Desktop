import SwiftUI

struct EntryDetailView: View {
    @Bindable var entry: JournalEntry
    @State private var isShowingCompanion = false
    @State private var isShowingCorrections = false

    private var hasTargetLanguageSegments: Bool {
        guard let target = AppSettings.targetLanguageCode else { return false }
        return entry.segments.contains { $0.languageCode == target }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    if let title = entry.title, !title.isEmpty {
                        Text(title)
                            .font(Theme.serif(26))
                            .foregroundStyle(Theme.heading)
                    }
                    Text(entry.date, style: .date)
                        .font(.subheadline)
                        .foregroundStyle(Theme.secondary)
                }

                if let headline = entry.sourceHeadline, !headline.isEmpty {
                    sourceCitation(headline: headline)
                }

                VStack(alignment: .leading, spacing: 14) {
                    ForEach(entry.segments.sorted(by: { $0.order < $1.order })) { segment in
                        VStack(alignment: .leading, spacing: 6) {
                            if let code = segment.languageCode {
                                LanguageBadge(languageCode: code)
                            }
                            Text(segment.text)
                                .font(.system(size: 16))
                                .foregroundStyle(Theme.bodyText)
                        }
                    }
                }
                .padding(18)
                .frame(maxWidth: .infinity, alignment: .leading)
                .warmCard()

                Button {
                    isShowingCompanion = true
                } label: {
                    Label(
                        entry.companionMessages.isEmpty ? "Talk about this entry" : "Continue the conversation",
                        systemImage: "bubble.left.and.bubble.right"
                    )
                }
                .buttonStyle(TerracottaButtonStyle())

                if hasTargetLanguageSegments {
                    Button {
                        isShowingCorrections = true
                    } label: {
                        Label("See gentle corrections", systemImage: "sparkles")
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundStyle(Theme.accentDeep)
                            .frame(maxWidth: .infinity)
                            .padding(14)
                            .background(Theme.accentSoft, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(20)
        }
        .background(Theme.bg.ignoresSafeArea())
        .scrollContentBackground(.hidden)
        .navigationTitle("Entry")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $isShowingCompanion) {
            CompanionChatView(entry: entry)
        }
        .sheet(isPresented: $isShowingCorrections) {
            CorrectionsView(entry: entry)
        }
    }

    private func sourceCitation(headline: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Inspired by")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(Theme.accentDeep)
                .textCase(.uppercase)
            if let urlString = entry.sourceURL, let url = URL(string: urlString), !urlString.isEmpty {
                Link(destination: url) {
                    Text(headline)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(Theme.accentDeep)
                        .multilineTextAlignment(.leading)
                }
            } else {
                Text(headline)
                    .font(.system(size: 14))
                    .foregroundStyle(Theme.bodyText)
            }
            if let publisher = entry.sourcePublisher, !publisher.isEmpty {
                Text("via \(publisher)")
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Theme.accentSoft, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}
