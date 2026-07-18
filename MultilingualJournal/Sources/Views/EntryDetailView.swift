import SwiftUI

struct EntryDetailView: View {
    @Bindable var entry: JournalEntry
    @State private var isShowingCompanion = false

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
            }
            .padding()
        }
        .navigationTitle("Entry")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $isShowingCompanion) {
            CompanionChatView(entry: entry)
        }
    }
}
