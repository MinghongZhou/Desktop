import Foundation

/// Gives the companion a private, on-device "memory": a short context block of
/// the person's relevant earlier entries so it can thread them across time
/// ("how did that presentation go?"). Selection is pure and unit-tested;
/// the entries never leave the device — that privacy is the whole point.
enum MemoryService {
    /// Picks the most relevant earlier entries for the current one: entries
    /// that share keywords rank first, with more recent entries breaking ties
    /// (and filling in when nothing overlaps, so there's always some memory).
    /// Returned oldest→newest so the context reads chronologically.
    static func selectEntries(for current: JournalEntry, from all: [JournalEntry], maxEntries: Int = 3) -> [JournalEntry] {
        let candidates = all.filter { candidate in
            candidate !== current
                && candidate.date <= current.date
                && !candidate.fullText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
        guard !candidates.isEmpty else { return [] }

        let currentKeywords = keywords(current.fullText)
        let ranked = candidates
            .map { (entry: $0, overlap: keywords($0.fullText).intersection(currentKeywords).count) }
            .sorted { a, b in
                a.overlap != b.overlap ? a.overlap > b.overlap : a.entry.date > b.entry.date
            }

        return ranked.prefix(maxEntries).map(\.entry).sorted { $0.date < $1.date }
    }

    /// Formats the selected entries into a context block for the model, or nil
    /// when there's nothing to remember.
    static func context(
        for current: JournalEntry,
        from all: [JournalEntry],
        maxEntries: Int = 3,
        maxCharsEach: Int = 220,
        now: Date = .now
    ) -> String? {
        let picked = selectEntries(for: current, from: all, maxEntries: maxEntries)
        guard !picked.isEmpty else { return nil }

        var lines = [
            "For context, here are a few of this person's earlier journal entries. You may gently reference them if it feels natural, but don't force it or list them back:"
        ]
        for entry in picked {
            lines.append("- (\(relativeLabel(for: entry.date, now: now))) \(truncated(entry.fullText, max: maxCharsEach))")
        }
        return lines.joined(separator: "\n")
    }

    /// Significant words for overlap scoring: lowercased, ≥4 chars, minus a few
    /// ultra-common words. Deliberately language-agnostic and simple.
    static func keywords(_ text: String) -> Set<String> {
        let lowered = text.lowercased()
        let tokens = lowered.split { !$0.isLetter }.map(String.init)
        return Set(tokens.filter { $0.count >= 4 && !commonWords.contains($0) })
    }

    private static let commonWords: Set<String> = [
        "this", "that", "with", "have", "just", "really", "today", "about",
        "would", "there", "their", "them", "then", "from", "were", "been",
        "pero", "para", "porque", "también", "cuando", "esto", "esta",
    ]

    private static func truncated(_ text: String, max: Int) -> String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.count > max else { return trimmed }
        return String(trimmed.prefix(max)).trimmingCharacters(in: .whitespaces) + "…"
    }

    private static func relativeLabel(for date: Date, now: Date) -> String {
        let days = Calendar.current.dateComponents([.day], from: Calendar.current.startOfDay(for: date), to: Calendar.current.startOfDay(for: now)).day ?? 0
        switch days {
        case ..<1: return "today"
        case 1: return "yesterday"
        case 2..<7: return "\(days) days ago"
        case 7..<14: return "last week"
        case 14..<31: return "a couple of weeks ago"
        default: return "a while ago"
        }
    }
}
