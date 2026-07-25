import Foundation

/// Talks to the Claude API to produce the journaling companion's replies.
/// The journal entry's own text is always sent as the first "user" turn,
/// so the companion's opening line is a direct reaction to what was
/// written — the user doesn't have to type anything to start.
enum CompanionService {
    static let apiKeyAccount = "anthropicAPIKey"

    /// Update this if you want the companion to use a different Claude model.
    private static let model = "claude-sonnet-5"
    private static let endpoint = URL(string: "https://api.anthropic.com/v1/messages")!
    private static let apiVersion = "2023-06-01"
    private static let maxTokens = 300

    private static let systemPrompt = """
    You are a warm, curious journaling companion inside a personal journal app. \
    The user just wrote a journal entry, and it may mix multiple languages within \
    it — that's normal for how they naturally speak and think, not something to \
    flag or correct here.

    Guidelines:
    - Reply primarily in the same language(s) the entry used. If they mixed \
    languages, you may mix too — match their voice.
    - Keep replies short: 2-4 sentences.
    - Ask at most one open, gentle follow-up question. Don't interrogate.
    - You are a companion, not a therapist. Don't diagnose, label, or use \
    clinical language.
    - Never comment on grammar, word choice, or language mistakes in this \
    conversation — that happens elsewhere in the app, not here.
    - If the entry mentions self-harm, suicide, or being in crisis, respond with \
    warmth first, gently note that a crisis line or trusted person can help right \
    now, and do not attempt to resolve the crisis yourself.
    """

    enum CompanionError: LocalizedError {
        case missingAPIKey
        case requestFailed(String)

        var errorDescription: String? {
            switch self {
            case .missingAPIKey:
                return "Add your Claude API key in Settings to talk with your companion."
            case .requestFailed(let message):
                return message
            }
        }
    }

    /// - Parameters:
    ///   - entry: the journal entry being discussed; always sent as the first turn.
    ///   - history: prior companion/user turns for this entry, in order.
    ///   - newUserMessage: an additional message the user just typed, if any.
    ///     Pass `nil` to request the companion's opening reflection.
    static func reply(
        to entry: JournalEntry,
        history: [CompanionMessage],
        newUserMessage: String?
    ) async throws -> String {
        guard let apiKey = KeychainService.read(account: apiKeyAccount), !apiKey.isEmpty else {
            throw CompanionError.missingAPIKey
        }

        var messages: [APIMessage] = [APIMessage(role: "user", content: entry.fullText)]
        messages.append(contentsOf: history.map { APIMessage(role: $0.role.apiRole, content: $0.text) })
        if let newUserMessage {
            messages.append(APIMessage(role: "user", content: newUserMessage))
        }

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue(apiVersion, forHTTPHeaderField: "anthropic-version")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(
            APIRequest(model: model, max_tokens: maxTokens, system: systemPrompt, messages: messages)
        )

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            throw CompanionError.requestFailed("No response from server.")
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = (try? JSONDecoder().decode(APIErrorResponse.self, from: data).error.message)
                ?? "Request failed with status \(http.statusCode)."
            throw CompanionError.requestFailed(message)
        }

        let decoded = try JSONDecoder().decode(APIResponse.self, from: data)
        let text = decoded.content.compactMap { $0.text }.joined()
        guard !text.isEmpty else {
            throw CompanionError.requestFailed("The companion didn't have anything to say.")
        }
        return text
    }

    // MARK: - Wire types

    private struct APIMessage: Encodable {
        let role: String
        let content: String
    }

    private struct APIRequest: Encodable {
        let model: String
        let max_tokens: Int
        let system: String
        let messages: [APIMessage]
    }

    private struct APIResponse: Decodable {
        let content: [ContentBlock]
        struct ContentBlock: Decodable {
            let type: String
            let text: String?
        }
    }

    private struct APIErrorResponse: Decodable {
        let error: APIError
        struct APIError: Decodable {
            let message: String
        }
    }
}
