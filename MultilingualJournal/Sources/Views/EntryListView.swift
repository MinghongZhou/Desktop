import SwiftUI
import SwiftData

struct EntryListView: View {
    @Query(sort: \JournalEntry.date, order: .reverse) private var entries: [JournalEntry]
    @AppStorage(AppSettings.targetLanguageCodeKey) private var targetLanguageCode: String = ""
    @AppStorage(AppSettings.newsTopicsEnabledKey) private var newsEnabled: Bool = true
    @State private var isPresentingNewEntry = false
    @State private var searchText = ""
    @State private var todaysTopic: Topic?
    @State private var topicForEntry: Topic?

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
        NavigationStack {
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
                                NavigationLink(value: entry) {
                                    EntryCard(entry: entry)
                                }
                                .buttonStyle(.plain)
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
            .sheet(isPresented: $isPresentingNewEntry) {
                NewEntryView()
            }
            .sheet(item: $topicForEntry) { topic in
                NewEntryView(topic: topic)
            }
            .task {
                if todaysTopic == nil {
                    let topics = await TopicService.fetchTopics(languageCode: languageCode, newsEnabled: newsEnabled, limit: 1)
                    todaysTopic = topics.first
                }
            }
        }
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
