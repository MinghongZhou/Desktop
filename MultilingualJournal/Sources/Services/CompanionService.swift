import Foundation
import FoundationModels

/// Produces the journaling companion's replies using Apple's on-device
/// Foundation Models framework — no API key, no network, nothing leaves the
/// device (a good fit for a private journal). Requires iOS 26+ on an
/// Apple-Intelligence-capable device; callers get a clear `.unavailable`
/// error otherwise, and the rest of the app keeps working.
enum CompanionService {
    static let systemPrompt = """
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
        /// The on-device model can't run here (old OS, ineligible device, or
        /// Apple Intelligence not enabled). `message` is user-facing.
        case unavailable(String)
        case requestFailed(String)

        var errorDescription: String? {
            switch self {
            case .unavailable(let message): return message
            case .requestFailed(let message): return message
            }
        }
    }

    /// - Parameters:
    ///   - entry: the journal entry being discussed; always the first context.
    ///   - history: prior companion/user turns for this entry, in order.
    ///   - newUserMessage: an additional message the user just typed, if any.
    ///     Pass `nil` to request the companion's opening reflection.
    static func reply(
        to entry: JournalEntry,
        history: [CompanionMessage],
        newUserMessage: String?
    ) async throws -> String {
        guard #available(iOS 26.0, *) else {
            throw CompanionError.unavailable(Self.unavailableMessage)
        }
        return try await OnDeviceCompanion.reply(
            entryText: entry.fullText,
            history: history,
            newUserMessage: newUserMessage
        )
    }

    static let unavailableMessage =
        "The companion runs on Apple Intelligence, which needs iOS 26 or later on a supported device (iPhone 15 Pro or newer). Your journal entries still work everywhere."

    /// Builds the single prompt describing the entry and conversation so far.
    /// Shared with the on-device path (kept here, free of framework types, so
    /// it's easy to reason about and adjust).
    static func buildPrompt(entryText: String, history: [CompanionMessage], newUserMessage: String?) -> String {
        var lines = ["The person's journal entry:", "\"\"\"", entryText, "\"\"\""]

        if !history.isEmpty {
            lines.append("")
            lines.append("Conversation so far:")
            for message in history {
                let speaker = message.role == .companion ? "You" : "Them"
                lines.append("\(speaker): \(message.text)")
            }
        }

        lines.append("")
        if let newUserMessage, !newUserMessage.isEmpty {
            lines.append("Them: \(newUserMessage)")
            lines.append("Respond as the companion.")
        } else if history.isEmpty {
            lines.append("Respond as the companion with a brief opening reflection on what they wrote.")
        } else {
            lines.append("Respond as the companion.")
        }

        return lines.joined(separator: "\n")
    }
}

@available(iOS 26.0, *)
private enum OnDeviceCompanion {
    static func reply(entryText: String, history: [CompanionMessage], newUserMessage: String?) async throws -> String {
        switch SystemLanguageModel.default.availability {
        case .available:
            break
        case .unavailable:
            throw CompanionService.CompanionError.unavailable(CompanionService.unavailableMessage)
        @unknown default:
            throw CompanionService.CompanionError.unavailable(CompanionService.unavailableMessage)
        }

        let session = LanguageModelSession(instructions: CompanionService.systemPrompt)
        let prompt = CompanionService.buildPrompt(
            entryText: entryText,
            history: history,
            newUserMessage: newUserMessage
        )

        do {
            let response = try await session.respond(to: prompt)
            let text = response.content.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !text.isEmpty else {
                throw CompanionService.CompanionError.requestFailed("The companion didn't have anything to say.")
            }
            return text
        } catch let error as CompanionService.CompanionError {
            throw error
        } catch {
            throw CompanionService.CompanionError.requestFailed(error.localizedDescription)
        }
    }
}
