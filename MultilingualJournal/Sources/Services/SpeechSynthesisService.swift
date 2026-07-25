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
        utterance.voice = languageCode.flatMap(AVSpeechSynthesisVoice.init(language:))
        isSpeaking = true
        synthesizer.speak(utterance)
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
