import SwiftUI

struct EntryDetailView: View {
    let entry: JournalEntry

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
            }
            .padding()
        }
        .navigationTitle("Entry")
        .navigationBarTitleDisplayMode(.inline)
    }
}
