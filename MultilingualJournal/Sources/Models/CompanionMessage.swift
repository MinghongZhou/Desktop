import Foundation

enum CompanionRole: String, Codable {
    case user
    case companion

    var apiRole: String {
        switch self {
        case .user: return "user"
        case .companion: return "assistant"
        }
    }
}

struct CompanionMessage: Codable, Hashable, Identifiable {
    var id: UUID = UUID()
    var role: CompanionRole
    var text: String
    var date: Date = .now
}
