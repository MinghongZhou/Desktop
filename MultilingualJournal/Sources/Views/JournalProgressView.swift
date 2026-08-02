import SwiftUI
import SwiftData

/// The "Trends" tab: streak + vocabulary progress in the warm design language.
/// Framed as encouragement rather than assessment — see `VocabularyStats` for
/// why the word counts are a "words you've used" signal, not proficiency.
/// Runs as a tab root (no NavigationStack/Done of its own — RootView provides
/// the stack) and reads entries via `@Query`.
struct JournalProgressView: View {
    @Query(sort: \JournalEntry.date, order: .reverse) private var entries: [JournalEntry]
    @AppStorage(AppSettings.targetLanguageCodeKey) private var targetLanguageCode: String = ""

    private var currentStreak: Int {
        StreakCalculator.currentStreak(dates: entries.map(\.date))
    }

    private var longestStreak: Int {
        StreakCalculator.longestStreak(dates: entries.map(\.date))
    }

    private var windowStart: Date {
        Calendar.current.date(byAdding: .day, value: -30, to: .now) ?? .distantPast
    }

    private var vocabulary: VocabularyStats {
        guard !targetLanguageCode.isEmpty else { return .empty }
        return VocabularyAnalyzer.stats(for: entries, languageCode: targetLanguageCode, since: windowStart)
    }

    private var targetLanguageName: String {
        Locale.current.localizedString(forLanguageCode: targetLanguageCode) ?? targetLanguageCode
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("Your growth")
                    .font(Theme.serif(28))
                    .foregroundStyle(Theme.heading)
                    .padding(.top, 8)

                HStack(spacing: 10) {
                    StatTile(label: "Current streak", value: "\(currentStreak)", unit: currentStreak == 1 ? "day" : "days", tone: .terracotta)
                    StatTile(label: "Longest streak", value: "\(longestStreak)", unit: longestStreak == 1 ? "day" : "days", tone: .neutral)
                }

                StatTile(label: "Total entries", value: "\(entries.count)", unit: entries.count == 1 ? "entry" : "entries", tone: .neutral)
                    .frame(maxWidth: .infinity)

                Text("Practice calendar")
                    .sectionLabel()
                    .padding(.top, 6)
                calendar

                if targetLanguageCode.isEmpty {
                    Text("Set the language you're learning in Settings to see your vocabulary grow here.")
                        .font(.subheadline)
                        .foregroundStyle(Theme.secondary)
                        .padding(16)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .warmCard()
                } else {
                    Text("\(targetLanguageName) vocabulary")
                        .sectionLabel()
                        .padding(.top, 6)
                    HStack(spacing: 10) {
                        StatTile(label: "Distinct words", value: "\(vocabulary.totalUniqueWords)", unit: "used", tone: .sage)
                        StatTile(label: "New (30 days)", value: "\(vocabulary.newWordsInPeriod)", unit: "words", tone: .terracotta)
                    }
                    if !vocabulary.recentNewWords.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Recently used for the first time")
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundStyle(Theme.secondary)
                            FlowChips(items: vocabulary.recentNewWords)
                        }
                        .padding(16)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .warmCard()
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 24)
        }
        .background(Theme.bg.ignoresSafeArea())
        .scrollContentBackground(.hidden)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar(.hidden, for: .navigationBar)
    }

    /// A weekday-aligned 4-week heatmap. Columns are fixed weekdays (with
    /// header labels), the intensity grows with entries per day, and today's
    /// cell is ringed so "when did I practice" is actually readable.
    private var calendar: some View {
        let cal = Calendar.current
        let today = cal.startOfDay(for: .now)
        let weeks = 4

        // Entry counts per day, so cells can intensity-shade.
        var counts: [Date: Int] = [:]
        for entry in entries {
            counts[cal.startOfDay(for: entry.date), default: 0] += 1
        }

        // Column 0 is the calendar's first weekday; find today's column so the
        // grid's last row ends on today, aligned to the weekday headers.
        let weekday = cal.component(.weekday, from: today)
        let todayColumn = (weekday - cal.firstWeekday + 7) % 7

        // Weekday header symbols, rotated to start at the calendar's firstWeekday.
        let symbols = cal.veryShortStandaloneWeekdaySymbols
        let headers = (0..<7).map { symbols[(cal.firstWeekday - 1 + $0) % 7] }

        let columns = Array(repeating: GridItem(.flexible(), spacing: 6), count: 7)

        return VStack(spacing: 6) {
            LazyVGrid(columns: columns, spacing: 6) {
                ForEach(0..<7, id: \.self) { col in
                    Text(headers[col])
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(Theme.secondary)
                        .frame(maxWidth: .infinity)
                }
            }
            LazyVGrid(columns: columns, spacing: 6) {
                ForEach(0..<(weeks * 7), id: \.self) { index in
                    let row = index / 7
                    let col = index % 7
                    let dayOffset = (weeks - 1 - row) * 7 + (todayColumn - col)
                    calendarCell(dayOffset: dayOffset, today: today, counts: counts, cal: cal)
                }
            }
        }
        .padding(16)
        .warmCard()
    }

    @ViewBuilder
    private func calendarCell(dayOffset: Int, today: Date, counts: [Date: Int], cal: Calendar) -> some View {
        if dayOffset < 0 {
            // Future days in the current week: keep the grid rectangular but empty.
            Color.clear.aspectRatio(1, contentMode: .fit)
        } else {
            let day = cal.date(byAdding: .day, value: -dayOffset, to: today) ?? today
            let count = counts[day] ?? 0
            let isToday = dayOffset == 0
            RoundedRectangle(cornerRadius: 6)
                .fill(count > 0 ? Theme.accent.opacity(min(1.0, 0.55 + 0.15 * Double(count))) : Theme.line)
                .aspectRatio(1, contentMode: .fit)
                .overlay {
                    if isToday {
                        RoundedRectangle(cornerRadius: 6)
                            .strokeBorder(Theme.accentDeep, lineWidth: 2)
                    }
                }
        }
    }
}

private struct StatTile: View {
    enum Tone { case terracotta, sage, neutral }
    let label: String
    let value: String
    let unit: String
    let tone: Tone

    private var background: Color {
        switch tone {
        case .terracotta: return Theme.accentSoft
        case .sage: return Theme.sageSoft
        case .neutral: return Theme.neutral
        }
    }

    private var valueColor: Color {
        switch tone {
        case .terracotta: return Theme.accentDeep
        case .sage: return Theme.sageDark
        case .neutral: return Theme.heading
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(valueColor.opacity(0.8))
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(value)
                    .font(Theme.serif(26))
                    .foregroundStyle(valueColor)
                Text(unit)
                    .font(.system(size: 13))
                    .foregroundStyle(valueColor.opacity(0.7))
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(background, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

/// Simple wrapping chip row for vocabulary words.
private struct FlowChips: View {
    let items: [String]

    var body: some View {
        // A basic wrapping layout using a flexible grid of chips.
        FlexibleChipLayout(spacing: 8) {
            ForEach(items, id: \.self) { word in
                Text(word)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(Theme.accentDeep)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 6)
                    .background(Theme.accentSoft, in: Capsule())
            }
        }
    }
}

/// Minimal flow layout so chips wrap onto multiple lines.
private struct FlexibleChipLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x + size.width > maxWidth, x > 0 {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
        return CGSize(width: maxWidth == .infinity ? x : maxWidth, height: y + rowHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x + size.width > bounds.maxX, x > bounds.minX {
                x = bounds.minX
                y += rowHeight + spacing
                rowHeight = 0
            }
            view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}

#Preview {
    NavigationStack { JournalProgressView() }
        .modelContainer(for: JournalEntry.self, inMemory: true)
}
