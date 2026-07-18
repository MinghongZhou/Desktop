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
    var moodTag: String?

    init(date: Date = .now, segments: [EntrySegment], source: EntrySource, moodTag: String? = nil) {
        self.date = date
        self.segments = segments
        self.source = source
        self.moodTag = moodTag
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
