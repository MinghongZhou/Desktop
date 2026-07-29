import Foundation
#if canImport(FoundationModels)
import FoundationModels
#endif

/// Generates gentle, optional corrections for the target-language segments of
/// an entry, using Apple's on-device Foundation Models with guided generation
/// (so the structured result doesn't depend on the model emitting valid JSON).
/// On-device: no key, no network. Requires iOS 26+ on a supported device.
enum CorrectionsService {
    enum CorrectionsError: LocalizedError {
        case unavailable(String)
        case missingTargetLanguage
        case requestFailed(String)

        var errorDescription: String? {
            switch self {
            case .unavailable(let message): return message
            case .missingTargetLanguage:
                return "Pick the language you're learning in Settings first."
            case .requestFailed(let message): return message
            }
        }
    }

    /// Plain (non-`@Generable`) draft used for the pure mapping step, so the
    /// segment-index → `Correction` logic can be unit tested without the
    /// Foundation Models framework.
    struct CorrectionDraft: Equatable {
        let segmentIndex: Int
        let suggestion: String
        let note: String
    }

    static func fetchCorrections(for entry: JournalEntry) async throws -> [Correction] {
        guard let targetLanguageCode = AppSettings.targetLanguageCode else {
            throw CorrectionsError.missingTargetLanguage
        }

        let targetSegments = entry.segments
            .sorted { $0.order < $1.order }
            .filter { $0.languageCode == targetLanguageCode }
        guard !targetSegments.isEmpty else { return [] }

        #if canImport(FoundationModels)
        guard #available(iOS 26.0, *) else {
            throw CorrectionsError.unavailable(osTooOldMessage)
        }

        let languageName = Locale.current.localizedString(forLanguageCode: targetLanguageCode) ?? targetLanguageCode
        let drafts = try await OnDeviceCorrections.drafts(
            for: targetSegments.map(\.text),
            languageName: languageName
        )
        return mapDrafts(drafts, targetSegments: targetSegments)
        #else
        // Built with an SDK that predates Foundation Models (Xcode < 26) — a
        // property of the build machine's Xcode, not the phone's iOS version.
        throw CorrectionsError.unavailable(compiledWithoutSupportMessage)
        #endif
    }

    static let compiledWithoutSupportMessage =
        "This build was compiled without Apple Intelligence support. Rebuild the app with Xcode 26 or later (updating the phone to iOS 26 isn't enough — the app itself must be built on Xcode 26)."

    static let osTooOldMessage =
        "Gentle corrections need iOS 26 or later."

    /// Maps model drafts back to the segments they refer to, dropping any with
    /// an out-of-range index. Pure and framework-free for testability.
    static func mapDrafts(_ drafts: [CorrectionDraft], targetSegments: [EntrySegment]) -> [Correction] {
        drafts.compactMap { draft in
            guard targetSegments.indices.contains(draft.segmentIndex) else { return nil }
            let segment = targetSegments[draft.segmentIndex]
            return Correction(
                segmentID: segment.id,
                originalText: segment.text,
                suggestion: draft.suggestion,
                note: draft.note
            )
        }
    }

    static func instructions(languageName: String) -> String {
        """
        You help a language learner journal in \(languageName). You'll be given \
        numbered sentences they wrote in \(languageName).

        Rules:
        - Only flag genuine errors (grammar, word choice, agreement, etc.) — never \
        nitpick stylistic choices or sentences that are already correct.
        - Skip a sentence entirely if it's fine; don't force a suggestion.
        - Return at most 2 suggestions total — pick the most useful ones, not every \
        one you notice. Return an empty list if nothing is worth flagging.
        - Keep your tone warm and encouraging, like a supportive friend, never a red \
        pen. Never say "wrong" — frame it as "a more natural way to say this might be...".
        - segmentIndex must be the 0-based number of the sentence you're correcting.
        """
    }

    static func prompt(for sentences: [String]) -> String {
        let numbered = sentences.enumerated()
            .map { "\($0.offset). \($0.element)" }
            .joined(separator: "\n")
        return "Sentences:\n\(numbered)"
    }
}

#if canImport(FoundationModels)
@available(iOS 26.0, *)
private enum OnDeviceCorrections {
    @Generable
    struct Suggestions {
        @Guide(description: "At most 2 corrections; empty if nothing needs flagging.")
        var corrections: [Item]
    }

    @Generable
    struct Item {
        @Guide(description: "0-based index of the sentence being corrected.")
        var segmentIndex: Int
        @Guide(description: "The corrected, more natural version of the sentence.")
        var suggestion: String
        @Guide(description: "One short, warm sentence explaining the change.")
        var note: String
    }

    static func drafts(for sentences: [String], languageName: String) async throws -> [CorrectionsService.CorrectionDraft] {
        switch SystemLanguageModel.default.availability {
        case .available:
            break
        case .unavailable(let reason):
            throw CorrectionsService.CorrectionsError.unavailable(message(for: reason))
        @unknown default:
            throw CorrectionsService.CorrectionsError.unavailable("Apple Intelligence isn't available on this device right now.")
        }

        let session = LanguageModelSession(instructions: CorrectionsService.instructions(languageName: languageName))
        do {
            let response = try await session.respond(
                to: CorrectionsService.prompt(for: sentences),
                generating: Suggestions.self
            )
            return response.content.corrections.map {
                CorrectionsService.CorrectionDraft(segmentIndex: $0.segmentIndex, suggestion: $0.suggestion, note: $0.note)
            }
        } catch {
            throw CorrectionsService.CorrectionsError.requestFailed(error.localizedDescription)
        }
    }

    static func message(for reason: SystemLanguageModel.Availability.UnavailableReason) -> String {
        switch reason {
        case .deviceNotEligible:
            return "This device doesn't support Apple Intelligence, so corrections can't run here. (It needs an iPhone 15 Pro or newer.)"
        case .appleIntelligenceNotEnabled:
            return "Turn on Apple Intelligence to use corrections: Settings → Apple Intelligence & Siri → turn it on."
        case .modelNotReady:
            return "Apple Intelligence is still downloading its model. Try again once it finishes (Settings → Apple Intelligence & Siri)."
        @unknown default:
            return "Apple Intelligence isn't available on this device right now."
        }
    }
}
#endif
