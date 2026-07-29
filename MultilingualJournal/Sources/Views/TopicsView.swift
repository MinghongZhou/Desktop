import SwiftUI

/// The "Topics" tab: current news turned into target-language journaling
/// prompts. Runs as a tab root (RootView provides the NavigationStack).
struct TopicsView: View {
    @AppStorage(AppSettings.targetLanguageCodeKey) private var targetLanguageCode: String = ""
    @AppStorage(AppSettings.newsTopicsEnabledKey) private var newsEnabled: Bool = true

    @State private var topics: [Topic] = []
    @State private var isLoading = false
    @State private var selectedTopic: Topic?

    private var languageCode: String {
        if !targetLanguageCode.isEmpty { return targetLanguageCode }
        return Locale.current.language.languageCode?.identifier ?? "en"
    }

    private var showsEnglishFallbackNote: Bool {
        newsEnabled && !FeedCatalog.hasNativeFeed(for: languageCode)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("Topics")
                    .font(Theme.serif(28))
                    .foregroundStyle(Theme.heading)
                    .padding(.top, 8)

                Text(newsEnabled
                     ? "Today's news, turned into prompts in your target language. Tap one to journal about it."
                     : "News topics are off. These are timeless prompts. Turn on news in Settings for current events.")
                    .font(.system(size: 14))
                    .foregroundStyle(Theme.secondary)

                if showsEnglishFallbackNote {
                    Text("Your target language doesn't have a dedicated news feed yet, so these are in English.")
                        .font(.system(size: 13))
                        .foregroundStyle(Theme.secondary)
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Theme.neutral, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                }

                if isLoading && topics.isEmpty {
                    ProgressView()
                        .frame(maxWidth: .infinity)
                        .padding(.top, 40)
                } else {
                    ForEach(topics) { topic in
                        TopicCard(topic: topic) { selectedTopic = topic }
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 24)
        }
        .background(Theme.bg.ignoresSafeArea())
        .scrollContentBackground(.hidden)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    Task { await load() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .disabled(isLoading)
                .tint(Theme.accentDeep)
            }
        }
        .task {
            if topics.isEmpty { await load() }
        }
        .sheet(item: $selectedTopic) { topic in
            NewEntryView(topic: topic)
        }
    }

    private func load() async {
        isLoading = true
        topics = await TopicService.fetchTopics(languageCode: languageCode, newsEnabled: newsEnabled)
        isLoading = false
    }
}

private struct TopicCard: View {
    let topic: Topic
    let onJournal: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if topic.hasSource {
                Text(topic.headline)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Theme.secondary)
                    .lineLimit(2)
            }
            Text(topic.prompt)
                .font(Theme.serif(18))
                .foregroundStyle(Theme.heading)
                .fixedSize(horizontal: false, vertical: true)

            HStack {
                if topic.hasSource, let url = URL(string: topic.articleURL) {
                    Link(destination: url) {
                        Text("via \(topic.publisher)")
                            .font(.system(size: 13, weight: .medium))
                            .foregroundStyle(Theme.accentDeep)
                    }
                }
                Spacer()
                Button(action: onJournal) {
                    Text("Journal about this")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 9)
                        .background(Theme.accent, in: Capsule())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .warmCard()
    }
}

#Preview {
    NavigationStack { TopicsView() }
}
