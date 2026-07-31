import Foundation
import SwiftData

enum EntrySource: String, Codable {
    case voice
    case text
}

@Model
final class JournalEntry {
    var date: Date
    var segments: [EntrySegment]
    var source: EntrySource
    var title: String?
    var moodTag: String?
    var companionMessages: [CompanionMessage] = []
    var corrections: [Correction] = []
    var correctionsFetchedAt: Date?

    // Optional citation when the entry was written in response to a Topic
    // (a news article turned into a prompt). Entries keep the source so it
    // can be shown and linked, while the article itself stays external.
    var sourceHeadline: String?
    var sourceURL: String?
    var sourcePublisher: String?

    init(
        date: Date = .now,
        segments: [EntrySegment],
        source: EntrySource,
        title: String? = nil,
        moodTag: String? = nil,
        sourceHeadline: String? = nil,
        sourceURL: String? = nil,
        sourcePublisher: String? = nil
    ) {
        self.date = date
        self.segments = segments
        self.source = source
        self.title = title
        self.moodTag = moodTag
        self.sourceHeadline = sourceHeadline
        self.sourceURL = sourceURL
        self.sourcePublisher = sourcePublisher
    }

    /// A short label for lists: the user's title if given, otherwise the
    /// start of the entry text as a fallback so rows are never blank.
    var displayTitle: String {
        if let title, !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return title
        }
        let preview = fullText.trimmingCharacters(in: .whitespacesAndNewlines)
        return preview.isEmpty ? "Untitled entry" : preview
    }

    var fullText: String {
        segments
            .sorted { $0.order < $1.order }
            .map(\.text)
            .joined(separator: " ")
    }

    /// Distinct languages present in this entry, in order of first appearance.
    var languageCodes: [String] {
        var seen = Set<String>()
        var result: [String] = []
        for segment in segments.sorted(by: { $0.order < $1.order }) {
            guard let code = segment.languageCode, !seen.contains(code) else { continue }
            seen.insert(code)
            result.append(code)
        }
        return result
    }
}
