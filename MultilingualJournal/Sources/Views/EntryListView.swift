import SwiftUI
import SwiftData

struct EntryListView: View {
    @Query(sort: \JournalEntry.date, order: .reverse) private var entries: [JournalEntry]
    @Environment(\.modelContext) private var modelContext
    @State private var isPresentingNewEntry = false
    @State private var isPresentingSettings = false

    var body: some View {
        NavigationStack {
            Group {
                if entries.isEmpty {
                    ContentUnavailableView(
                        "No entries yet",
                        systemImage: "mic.circle",
                        description: Text("Tap the mic to record your first journal entry, in any language.")
                    )
                } else {
                    List {
                        ForEach(entries) { entry in
                            NavigationLink(value: entry) {
                                EntryRow(entry: entry)
                            }
                        }
                        .onDelete(perform: deleteEntries)
                    }
                }
            }
            .navigationTitle("Journal")
            .navigationDestination(for: JournalEntry.self) { entry in
                EntryDetailView(entry: entry)
            }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        isPresentingSettings = true
                    } label: {
                        Image(systemName: "gearshape")
                    }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        isPresentingNewEntry = true
                    } label: {
                        Image(systemName: "mic.fill")
                    }
                }
            }
            .sheet(isPresented: $isPresentingNewEntry) {
                NewEntryView()
            }
            .sheet(isPresented: $isPresentingSettings) {
                SettingsView()
            }
        }
    }

    private func deleteEntries(at offsets: IndexSet) {
        for index in offsets {
            modelContext.delete(entries[index])
        }
    }
}

private struct EntryRow: View {
    let entry: JournalEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(entry.date, style: .date)
                .font(.headline)
            Text(entry.fullText)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            if !entry.languageCodes.isEmpty {
                HStack(spacing: 4) {
                    ForEach(entry.languageCodes, id: \.self) { code in
                        LanguageBadge(languageCode: code)
                    }
                }
            }
        }
        .padding(.vertical, 4)
    }
}

#Preview {
    EntryListView()
        .modelContainer(for: JournalEntry.self, inMemory: true)
}
