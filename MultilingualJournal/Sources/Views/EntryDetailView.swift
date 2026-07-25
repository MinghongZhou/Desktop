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
                Text(entry.date, style: .date)
                    .font(.title3.weight(.semibold))

                ForEach(entry.segments.sorted(by: { $0.order < $1.order })) { segment in
                    VStack(alignment: .leading, spacing: 4) {
                        if let code = segment.languageCode {
                            LanguageBadge(languageCode: code)
                        }
                        Text(segment.text)
                    }
                }

                Button {
                    isShowingCompanion = true
                } label: {
                    Label(
                        entry.companionMessages.isEmpty ? "Talk about this entry" : "Continue the conversation",
                        systemImage: "bubble.left.and.bubble.right"
                    )
                }
                .buttonStyle(.borderedProminent)
                .padding(.top, 8)

                if hasTargetLanguageSegments {
                    Button {
                        isShowingCorrections = true
                    } label: {
                        Label("See gentle corrections", systemImage: "sparkles")
                    }
                    .buttonStyle(.bordered)
                }
            }
            .padding()
        }
        .navigationTitle("Entry")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $isShowingCompanion) {
            CompanionChatView(entry: entry)
        }
        .sheet(isPresented: $isShowingCorrections) {
            CorrectionsView(entry: entry)
        }
    }
}
