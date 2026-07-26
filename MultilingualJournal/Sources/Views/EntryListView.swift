import SwiftUI
import SwiftData

struct EntryListView: View {
    @Query(sort: \JournalEntry.date, order: .reverse) private var entries: [JournalEntry]
    @Environment(\.modelContext) private var modelContext
    @State private var isPresentingNewEntry = false
    @State private var isPresentingSettings = false
    @State private var isPresentingProgress = false
    @State private var searchText = ""

    private var visibleEntries: [JournalEntry] {
        EntrySearch.filter(entries, query: searchText)
    }

    private var currentStreak: Int {
        StreakCalculator.currentStreak(dates: entries.map(\.date))
    }

    var body: some View {
        NavigationStack {
            Group {
                if entries.isEmpty {
                    ContentUnavailableView(
                        "No entries yet",
                        systemImage: "mic.circle",
                        description: Text("Tap the mic to record your first journal entry, in any language.")
                    )
                } else if visibleEntries.isEmpty {
                    ContentUnavailableView.search(text: searchText)
                } else {
                    List {
                        if searchText.isEmpty, currentStreak > 0 {
                            StreakBanner(streak: currentStreak) {
                                isPresentingProgress = true
                            }
                        }
                        ForEach(visibleEntries) { entry in
                            NavigationLink(value: entry) {
                                EntryRow(entry: entry)
                            }
                        }
                        .onDelete(perform: deleteEntries)
                    }
                }
            }
            .searchable(
                text: $searchText,
                placement: .navigationBarDrawer(displayMode: .always),
                prompt: "Search your entries"
            )
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
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        isPresentingProgress = true
                    } label: {
                        Image(systemName: "chart.line.uptrend.xyaxis")
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
            .sheet(isPresented: $isPresentingProgress) {
                JournalProgressView(entries: entries)
            }
        }
    }

    /// Offsets come from the *filtered* list, so they must be resolved
    /// against `visibleEntries` — indexing into `entries` would delete the
    /// wrong row whenever a search is active.
    private func deleteEntries(at offsets: IndexSet) {
        let toDelete = offsets.map { visibleEntries[$0] }
        for entry in toDelete {
            modelContext.delete(entry)
        }
    }
}

private struct StreakBanner: View {
    let streak: Int
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 10) {
                Image(systemName: "flame.fill")
                    .foregroundStyle(.orange)
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(streak) day\(streak == 1 ? "" : "s") in a row")
                        .font(.subheadline.weight(.medium))
                    Text("See your progress")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
        }
        .buttonStyle(.plain)
    }
}

private struct EntryRow: View {
    let entry: JournalEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(entry.displayTitle)
                .font(.headline)
                .lineLimit(1)
            Text(entry.date, style: .date)
                .font(.caption)
                .foregroundStyle(.secondary)
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
