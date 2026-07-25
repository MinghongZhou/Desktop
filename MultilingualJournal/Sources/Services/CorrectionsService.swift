import Foundation

/// Generates gentle, optional corrections for the segments of an entry
/// written in the user's target (learning) language. Deliberately
/// conservative: skips sentences that are already fine, and caps how many
/// suggestions come back per entry, so this reads as a friend noticing
/// something occasionally — not a red pen pass over everything you wrote.
enum CorrectionsService {
    private static let model = "claude-sonnet-5"
    private static let endpoint = URL(string: "https://api.anthropic.com/v1/messages")!
    private static let apiVersion = "2023-06-01"
    private static let maxTokens = 600

    enum CorrectionsError: LocalizedError {
        case missingAPIKey
        case missingTargetLanguage
        case requestFailed(String)

        var errorDescription: String? {
            switch self {
            case .missingAPIKey:
                return "Add your Claude API key in Settings first."
            case .missingTargetLanguage:
                return "Pick the language you're learning in Settings first."
            case .requestFailed(let message):
                return message
            }
        }
    }

    /// - Returns: corrections for segments worth flagging. May be empty if
    ///   nothing needed a suggestion, or if the entry has no segments in the
    ///   configured target language.
    static func fetchCorrections(for entry: JournalEntry) async throws -> [Correction] {
        guard let apiKey = KeychainService.read(account: CompanionService.apiKeyAccount), !apiKey.isEmpty else {
            throw CorrectionsError.missingAPIKey
        }
        guard let targetLanguageCode = AppSettings.targetLanguageCode else {
            throw CorrectionsError.missingTargetLanguage
        }

        let targetSegments = entry.segments
            .sorted { $0.order < $1.order }
            .filter { $0.languageCode == targetLanguageCode }
        guard !targetSegments.isEmpty else { return [] }

        let languageName = Locale.current.localizedString(forLanguageCode: targetLanguageCode) ?? targetLanguageCode
        let numbered = targetSegments.enumerated()
            .map { "\($0.offset). \($0.element.text)" }
            .joined(separator: "\n")

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue(apiVersion, forHTTPHeaderField: "anthropic-version")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(
            APIRequest(
                model: model,
                max_tokens: maxTokens,
                system: systemPrompt(languageName: languageName),
                messages: [APIMessage(role: "user", content: "Sentences:\n\(numbered)")]
            )
        )

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            throw CorrectionsError.requestFailed("No response from server.")
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = (try? JSONDecoder().decode(APIErrorResponse.self, from: data).error.message)
                ?? "Request failed with status \(http.statusCode)."
            throw CorrectionsError.requestFailed(message)
        }

        let decoded = try JSONDecoder().decode(APIResponse.self, from: data)
        let rawText = decoded.content.compactMap { $0.text }.joined()
        return try parseCorrections(from: rawText, targetSegments: targetSegments)
    }

    /// Parses the model's raw reply text (expected to be JSON, optionally
    /// wrapped in a ```-fenced code block) into `Correction`s, mapping each
    /// item's `segmentIndex` back to the segment it refers to. Split out
    /// from `fetchCorrections` so this — the part actually worth unit
    /// testing — doesn't require a network call to exercise.
    static func parseCorrections(from rawText: String, targetSegments: [EntrySegment]) throws -> [Correction] {
        let jsonText = stripCodeFence(rawText)

        guard let jsonData = jsonText.data(using: .utf8),
              let parsed = try? JSONDecoder().decode(CorrectionsPayload.self, from: jsonData) else {
            throw CorrectionsError.requestFailed("Couldn't read the companion's suggestions this time.")
        }

        return parsed.corrections.compactMap { item in
            guard targetSegments.indices.contains(item.segmentIndex) else { return nil }
            let segment = targetSegments[item.segmentIndex]
            return Correction(
                segmentID: segment.id,
                originalText: segment.text,
                suggestion: item.suggestion,
                note: item.note
            )
        }
    }

    private static func systemPrompt(languageName: String) -> String {
        """
        You help a language learner journal in \(languageName). You'll be given \
        numbered sentences they wrote in \(languageName).

        Rules:
        - Only flag genuine errors (grammar, word choice, agreement, etc.) — never \
        nitpick stylistic choices or sentences that are already correct.
        - Skip a sentence entirely if it's fine; don't force a suggestion.
        - At most 2 sentences total should get a suggestion — pick the most useful \
        ones, not every one you notice.
        - Keep your tone warm and encouraging, like a supportive friend, never a red \
        pen. Never say "wrong" — frame it as "a more natural way to say this might be...".
        - Respond with ONLY JSON, no other text, in exactly this shape:
        {"corrections": [{"segmentIndex": <int>, "suggestion": "<corrected sentence>", "note": "<one short, warm sentence explaining the change>"}]}
        If nothing is worth flagging, respond with {"corrections": []}.
        """
    }

    private static func stripCodeFence(_ text: String) -> String {
        var result = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard result.hasPrefix("```") else { return result }
        if let firstNewline = result.firstIndex(of: "\n") {
            result = String(result[result.index(after: firstNewline)...])
        }
        if let closingRange = result.range(of: "```", options: .backwards) {
            result = String(result[..<closingRange.lowerBound])
        }
        return result.trimmingCharacters(in: .whitespacesAndNewlines)
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

    private struct CorrectionsPayload: Decodable {
        let corrections: [Item]
        struct Item: Decodable {
            let segmentIndex: Int
            let suggestion: String
            let note: String
        }
    }
}
