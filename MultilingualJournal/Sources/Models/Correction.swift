import Foundation

/// A single gentle, optional suggestion tied to one entry segment. Kept
/// separate from the companion chat entirely — corrections are something
/// the user opts into looking at, never something the companion brings up
/// mid-conversation.
struct Correction: Codable, Hashable, Identifiable {
    var id: UUID = UUID()
    var segmentID: UUID
    var originalText: String
    var suggestion: String
    var note: String
    var isDismissed: Bool = false
}
