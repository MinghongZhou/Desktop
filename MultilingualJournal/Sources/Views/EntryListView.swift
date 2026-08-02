import SwiftUI
import SwiftData

struct EntryListView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \JournalEntry.date, order: .reverse) private var entries: [JournalEntry]
    @AppStorage(AppSettings.targetLanguageCodeKey) private var targetLanguageCode: String = ""
    @AppStorage(AppSettings.newsTopicsEnabledKey) private var newsEnabled: Bool = true
    @State private var isPresentingNewEntry = false
    @State private var searchText = ""
    @State private var todaysTopic: Topic?
    @State private var topicForEntry: Topic?
    @State private var path: [JournalEntry] = []
    @State private var entryPendingDeletion: JournalEntry?
    /// Set by the New Entry sheet on save so we can push into the new entry
    /// once the sheet finishes dismissing (pushing mid-dismiss is janky).
    @State private var justSavedEntry: JournalEntry?

    private var visibleEntries: [JournalEntry] {
        EntrySearch.filter(entries, query: searchText)
    }

    private var languageCode: String {
        targetLanguageCode.isEmpty
            ? (Locale.current.language.languageCode?.identifier ?? "en")
            : targetLanguageCode
    }

    private var currentStreak: Int {
        StreakCalculator.currentStreak(dates: entries.map(\.date))
    }

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    header

                    if entries.isEmpty {
                        emptyState
                    } else {
                        if searchText.isEmpty {
                            if currentStreak > 0 { streakCard }
                            if let topic = todaysTopic { todaysTopicCard(topic) }
                            newEntryButton
                        }
                        Text(searchText.isEmpty ? "Recent entries" : "Results")
                            .sectionLabel()
                            .padding(.top, 4)

                        if visibleEntries.isEmpty {
                            Text("No entries match “\(searchText)”.")
                                .font(.subheadline)
                                .foregroundStyle(Theme.secondary)
                                .padding(.vertical, 8)
                        } else {
                            ForEach(visibleEntries) { entry in
                                DeletableEntryRow(
                                    entry: entry,
                                    onTap: { path.append(entry) },
                                    onRequestDelete: { entryPendingDeletion = entry }
                                )
                            }
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 24)
            }
            .background(Theme.bg.ignoresSafeArea())
            .scrollContentBackground(.hidden)
            .searchable(
                text: $searchText,
                placement: .navigationBarDrawer(displayMode: .always),
                prompt: "Search your entries"
            )
            .navigationBarTitleDisplayMode(.inline)
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: JournalEntry.self) { entry in
                EntryDetailView(entry: entry)
            }
            .sheet(isPresented: $isPresentingNewEntry, onDismiss: openJustSavedEntry) {
                NewEntryView(onSaved: { justSavedEntry = $0 })
            }
            .sheet(item: $topicForEntry, onDismiss: openJustSavedEntry) { topic in
                NewEntryView(topic: topic, onSaved: { justSavedEntry = $0 })
            }
            .confirmationDialog(
                "Delete this entry?",
                isPresented: Binding(
                    get: { entryPendingDeletion != nil },
                    set: { if !$0 { entryPendingDeletion = nil } }
                ),
                titleVisibility: .visible,
                presenting: entryPendingDeletion
            ) { entry in
                Button("Delete", role: .destructive) { delete(entry) }
                Button("Cancel", role: .cancel) { entryPendingDeletion = nil }
            } message: { _ in
                Text("This can't be undone.")
            }
            .task {
                if todaysTopic == nil {
                    let topics = await TopicService.fetchTopics(languageCode: languageCode, newsEnabled: newsEnabled, limit: 1)
                    todaysTopic = topics.first
                }
            }
        }
    }

    private func delete(_ entry: JournalEntry) {
        modelContext.delete(entry)
        try? modelContext.save()
        entryPendingDeletion = nil
    }

    /// Called after the New Entry sheet fully dismisses. If an entry was just
    /// saved, push into its detail so the user can immediately reflect on it.
    private func openJustSavedEntry() {
        guard let entry = justSavedEntry else { return }
        justSavedEntry = nil
        path.append(entry)
    }

    private func todaysTopicCard(_ topic: Topic) -> some View {
        Button {
            topicForEntry = topic
        } label: {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Today's topic")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(.white.opacity(0.85))
                        .textCase(.uppercase)
                    Spacer()
                    Image(systemName: "newspaper.fill")
                        .font(.system(size: 13))
                        .foregroundStyle(.white.opacity(0.85))
                }
                if !topic.imageURL.isEmpty, let url = URL(string: topic.imageURL) {
                    ArticleImage(url: url, height: 120)
                }
                Text(topic.prompt)
                    .font(Theme.serif(18))
                    .foregroundStyle(.white)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if topic.hasSource {
                    Text("via \(topic.publisher)")
                        .font(.system(size: 12))
                        .foregroundStyle(.white.opacity(0.8))
                }
            }
            .padding(20)
            .background(Theme.accentDeep, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Pieces

    private var header: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(greeting)
                .font(.system(size: 14))
                .foregroundStyle(Theme.secondary)
            Text("Your journal")
                .font(Theme.serif(28))
                .foregroundStyle(Theme.heading)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, 8)
    }

    private var greeting: String {
        switch Calendar.current.component(.hour, from: .now) {
        case 5..<12: return "Good morning"
        case 12..<17: return "Good afternoon"
        default: return "Good evening"
        }
    }

    private var streakCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("\(currentStreak)-day streak")
                    .font(Theme.serif(20))
                    .foregroundStyle(Theme.accentDeep)
                Spacer()
                Image(systemName: "flame.fill")
                    .foregroundStyle(Theme.accent)
            }
            HStack(spacing: 6) {
                ForEach(weekActivity.indices, id: \.self) { i in
                    RoundedRectangle(cornerRadius: 4)
                        .fill(weekActivity[i] ? Theme.accent : Theme.line)
                        .frame(height: 8)
                }
            }
        }
        .padding(18)
        .background(Theme.accentSoft, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    /// Last 7 days (oldest→today), true where an entry exists.
    private var weekActivity: [Bool] {
        let cal = Calendar.current
        let days = Set(entries.map { cal.startOfDay(for: $0.date) })
        let today = cal.startOfDay(for: .now)
        return (0..<7).reversed().map { offset in
            guard let day = cal.date(byAdding: .day, value: -offset, to: today) else { return false }
            return days.contains(day)
        }
    }

    private var newEntryButton: some View {
        Button {
            isPresentingNewEntry = true
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Today")
                        .font(.system(size: 13))
                        .foregroundStyle(.white.opacity(0.85))
                    Text("Start a new entry")
                        .font(Theme.serif(18))
                        .foregroundStyle(.white)
                }
                Spacer()
                ZStack {
                    Circle().fill(Theme.accent).frame(width: 52, height: 52)
                    Image(systemName: "mic.fill").foregroundStyle(.white)
                }
            }
            .padding(22)
            .background(Theme.accentDeep, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        }
        .buttonStyle(.plain)
    }

    private var emptyState: some View {
        VStack(spacing: 20) {
            newEntryButton
            VStack(spacing: 6) {
                Text("No entries yet")
                    .font(Theme.serif(20))
                    .foregroundStyle(Theme.heading)
                Text("Tap above to record or write your first entry, in any language.")
                    .font(.subheadline)
                    .foregroundStyle(Theme.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.top, 8)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 20)
    }
}

/// An entry row with a decisive swipe-to-delete. The screen is a ScrollView of
/// custom cards (not a `List`), where a lingering "reveal, then tap the button"
/// affordance is unreliable — the revealed button's tap gets swallowed by the
/// card. So a deliberate left swipe past a threshold triggers the delete
/// confirmation directly; a red trash slides in behind as visual feedback. The
/// gesture only engages when the drag is clearly horizontal, leaving vertical
/// scrolling and the row's tap-to-open intact.
private struct DeletableEntryRow: View {
    let entry: JournalEntry
    let onTap: () -> Void
    let onRequestDelete: () -> Void

    @State private var offset: CGFloat = 0
    private let maxReveal: CGFloat = 92
    /// How far left the row must be dragged to arm the delete confirmation.
    private let triggerThreshold: CGFloat = 80

    var body: some View {
        ZStack(alignment: .trailing) {
            // Delete affordance that slides into view as the card is dragged.
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(Color.red)
                .overlay(alignment: .trailing) {
                    Image(systemName: "trash.fill")
                        .font(.system(size: 18))
                        .foregroundStyle(.white)
                        .padding(.trailing, 28)
                }
                .opacity(offset < -6 ? 1 : 0)

            // A plain card (not a NavigationLink) so the swipe gesture wins
            // arbitration inside the ScrollView. Navigation is driven
            // programmatically on tap; the horizontal drag reveals delete and
            // a simultaneous gesture keeps vertical scrolling intact.
            EntryCard(entry: entry)
                // Opaque background so the delete action stays hidden when closed.
                .background(Theme.bg)
                .offset(x: offset)
                .contentShape(Rectangle())
                .onTapGesture { onTap() }
                .simultaneousGesture(
                    DragGesture(minimumDistance: 12)
                        .onChanged { value in
                            // Left-only, clearly-horizontal drags reveal delete.
                            guard value.translation.width < 0,
                                  abs(value.translation.width) > abs(value.translation.height) else { return }
                            offset = max(-maxReveal, value.translation.width)
                        }
                        .onEnded { value in
                            let decisiveLeftSwipe = value.translation.width < -triggerThreshold
                                && abs(value.translation.width) > abs(value.translation.height)
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.85)) {
                                offset = 0
                            }
                            // Fire after the snap-back so the confirmation
                            // dialog isn't presented mid-animation.
                            if decisiveLeftSwipe { onRequestDelete() }
                        }
                )
        }
        .contextMenu {
            Button(role: .destructive) {
                onRequestDelete()
            } label: {
                Label("Delete", systemImage: "trash")
            }
        }
    }
}

private struct EntryCard: View {
    let entry: JournalEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(entry.date, format: .dateTime.month().day())
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Theme.secondary)
                Spacer()
                HStack(spacing: 4) {
                    ForEach(entry.languageCodes, id: \.self) { code in
                        LanguageBadge(languageCode: code)
                    }
                }
            }
            if let title = entry.title, !title.isEmpty {
                Text(title)
                    .font(Theme.serif(17))
                    .foregroundStyle(Theme.heading)
                    .lineLimit(1)
            }
            Text(entry.fullText)
                .font(.system(size: 15))
                .foregroundStyle(Theme.bodyText)
                .lineLimit(2)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(18)
        .warmCard()
    }
}

#Preview {
    EntryListView()
        .modelContainer(for: JournalEntry.self, inMemory: true)
}
