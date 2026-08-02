import AVFoundation
import NaturalLanguage

/// Speaks companion replies aloud, picking a voice that matches the
/// reply's detected language rather than always using the device's
/// default voice/locale.
@MainActor
final class SpeechSynthesisService: ObservableObject {
    @Published private(set) var isSpeaking = false

    private let synthesizer = AVSpeechSynthesizer()
    private let delegate = Delegate()

    init() {
        synthesizer.delegate = delegate
        delegate.onFinish = { [weak self] in
            Task { @MainActor in self?.isSpeaking = false }
        }
    }

    func speak(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        stop()

        let recognizer = NLLanguageRecognizer()
        recognizer.processString(trimmed)
        let languageCode = recognizer.dominantLanguage?.rawValue

        let utterance = AVSpeechUtterance(string: trimmed)
        utterance.voice = languageCode.flatMap(Self.bestVoice(for:))
        // A touch slower than the default reads as warmer and more human,
        // which suits a gentle journaling companion.
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate * 0.95
        isSpeaking = true
        synthesizer.speak(utterance)
    }

    /// Picks the highest-quality installed voice for a language rather than the
    /// default compact (robotic) tier that `AVSpeechSynthesisVoice(language:)`
    /// returns. Prefers `.premium`, then `.enhanced`, then `.default`.
    ///
    /// NOTE: premium/enhanced voices only exist here if the user has downloaded
    /// them (Settings → Accessibility → Spoken Content → Voices). When none is
    /// installed we fall back to the compact voice so speech still works.
    static func bestVoice(for languageCode: String) -> AVSpeechSynthesisVoice? {
        let base = languageCode.split(whereSeparator: { $0 == "-" || $0 == "_" })
            .first.map(String.init)?.lowercased() ?? languageCode.lowercased()
        let matches = AVSpeechSynthesisVoice.speechVoices().filter {
            $0.language.lowercased().hasPrefix(base)
        }
        let best = matches.max { $0.quality.rawValue < $1.quality.rawValue }
        return best ?? AVSpeechSynthesisVoice(language: languageCode)
    }

    func stop() {
        guard synthesizer.isSpeaking else { return }
        synthesizer.stopSpeaking(at: .immediate)
        isSpeaking = false
    }

    private final class Delegate: NSObject, AVSpeechSynthesizerDelegate {
        var onFinish: (() -> Void)?

        func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
            onFinish?()
        }

        func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
            onFinish?()
        }
    }
}
