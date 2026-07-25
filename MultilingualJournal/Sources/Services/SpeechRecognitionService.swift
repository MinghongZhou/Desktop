import Foundation
import Speech
import AVFoundation

/// Wraps on-device live speech recognition. Recognition is locale-locked
/// (a known Speech-framework limitation: it cannot detect language switches
/// mid-recording), so this records in a single chosen locale. Segment-level
/// language tagging happens afterward via `LanguageSegmenter` on the
/// resulting transcript.
///
/// iOS finalizes a recognition request at natural pauses (and at a length
/// limit). A single request stops producing results once it finalizes, and
/// each request's transcription reflects only its own audio — so naively
/// reusing one request loses earlier sentences when the speaker pauses. To
/// support continuous, multi-sentence dictation this keeps a `finalizedText`
/// accumulator and starts a fresh request each time a segment finalizes,
/// while leaving the audio engine running, so nothing spoken is dropped.
@MainActor
final class SpeechRecognitionService: ObservableObject {
    @Published private(set) var transcript: String = ""
    @Published private(set) var isRecording: Bool = false
    @Published var authorizationError: String?

    private var recognizer: SFSpeechRecognizer?
    private let audioEngine = AVAudioEngine()
    private var task: SFSpeechRecognitionTask?

    /// Text from segments iOS has already finalized. The live `transcript` is
    /// this plus the current in-progress partial.
    private var finalizedText: String = ""

    /// Holds the active request so the audio tap (which runs on a background
    /// thread) can append buffers to whichever request is current, even as
    /// segments are swapped out on the main actor.
    private let requestBox = RequestBox()

    private final class RequestBox: @unchecked Sendable {
        var request: SFSpeechAudioBufferRecognitionRequest?
    }

    func requestAuthorization() async -> Bool {
        let speechStatus = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status)
            }
        }
        guard speechStatus == .authorized else {
            authorizationError = "Speech recognition access was denied. Enable it in Settings to journal by voice."
            return false
        }

        let micGranted = await AVAudioApplication.requestRecordPermission()
        guard micGranted else {
            authorizationError = "Microphone access was denied. Enable it in Settings to journal by voice."
            return false
        }

        return true
    }

    /// - Parameter locale: recognition locale, e.g. Locale(identifier: "es-ES").
    ///   Defaults to the device's current locale.
    func startRecording(locale: Locale = .current) throws {
        stopRecording()
        finalizedText = ""
        transcript = ""

        guard let recognizer = SFSpeechRecognizer(locale: locale), recognizer.isAvailable else {
            throw RecognitionError.recognizerUnavailable
        }
        self.recognizer = recognizer

        let audioSession = AVAudioSession.sharedInstance()
        try audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
        try audioSession.setActive(true, options: .notifyOthersOnDeactivation)

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [requestBox] buffer, _ in
            requestBox.request?.append(buffer)
        }

        audioEngine.prepare()
        try audioEngine.start()
        isRecording = true

        beginSegment()
    }

    /// Starts a fresh recognition request over the already-running audio
    /// engine. Called once when recording starts, then again each time a
    /// segment finalizes, so recognition continues seamlessly across pauses.
    private func beginSegment() {
        guard let recognizer else { return }

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        if recognizer.supportsOnDeviceRecognition {
            request.requiresOnDeviceRecognition = true
        }
        requestBox.request = request

        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            Task { @MainActor in
                self?.handle(result: result, error: error)
            }
        }
    }

    private func handle(result: SFSpeechRecognitionResult?, error: Error?) {
        // Ignore callbacks that arrive after the user has stopped (including
        // the cancellation callback triggered by `stopRecording`).
        guard isRecording else { return }

        if let result {
            transcript = merged(partial: result.bestTranscription.formattedString)
            if result.isFinal {
                rollOverSegment()
            }
        } else if error != nil {
            // The segment ended on an error (commonly a silence timeout).
            // Keep whatever we have and start a new segment so the user can
            // keep talking.
            rollOverSegment()
        }
    }

    /// Folds the just-finalized segment into the accumulator and, if still
    /// recording, opens a new segment to continue.
    private func rollOverSegment() {
        finalizedText = transcript
        task = nil
        requestBox.request = nil
        if isRecording {
            beginSegment()
        }
    }

    private func merged(partial: String) -> String {
        if finalizedText.isEmpty { return partial }
        if partial.isEmpty { return finalizedText }
        return finalizedText + " " + partial
    }

    func stopRecording() {
        guard isRecording || audioEngine.isRunning else { return }
        // Set this first so late recognition callbacks are ignored and can't
        // clobber the final transcript.
        isRecording = false
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        requestBox.request?.endAudio()
        task?.cancel()
        task = nil
        requestBox.request = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    enum RecognitionError: LocalizedError {
        case recognizerUnavailable

        var errorDescription: String? {
            switch self {
            case .recognizerUnavailable:
                return "Speech recognition isn't available for this language on this device right now."
            }
        }
    }
}
