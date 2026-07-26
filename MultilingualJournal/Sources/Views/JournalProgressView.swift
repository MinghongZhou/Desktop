import SwiftUI

/// Streak + vocabulary progress. Framed as encouragement rather than
/// assessment — see `VocabularyStats` for why the word counts are a "words
/// you've used" signal, not a proficiency measure.
struct JournalProgressView: View {
    let entries: [JournalEntry]
    @Environment(\.dismiss) private var dismiss
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
        NavigationStack {
            List {
                Section("Journaling") {
                    statRow(label: "Current streak", value: "\(currentStreak) day\(currentStreak == 1 ? "" : "s")")
                    statRow(label: "Longest streak", value: "\(longestStreak) day\(longestStreak == 1 ? "" : "s")")
                    statRow(label: "Total entries", value: "\(entries.count)")
                }

                if targetLanguageCode.isEmpty {
                    Section {
                        Text("Set the language you're learning in Settings to see your vocabulary grow here.")
                            .foregroundStyle(.secondary)
                            .font(.subheadline)
                    }
                } else {
                    Section("\(targetLanguageName) vocabulary") {
                        statRow(label: "Distinct words used", value: "\(vocabulary.totalUniqueWords)")
                        statRow(label: "New in the last 30 days", value: "\(vocabulary.newWordsInPeriod)")
                    }

                    if !vocabulary.recentNewWords.isEmpty {
                        Section {
                            Text(vocabulary.recentNewWords.joined(separator: " · "))
                                .font(.subheadline)
                        } header: {
                            Text("Recently used for the first time")
                        } footer: {
                            Text("Counts words you've actually written in \(targetLanguageName). It doesn't check whether they were used correctly — that's what gentle corrections are for.")
                        }
                    }
                }
            }
            .navigationTitle("Progress")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private func statRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text(value)
                .foregroundStyle(.secondary)
        }
    }
}

#Preview {
    JournalProgressView(entries: [])
}
