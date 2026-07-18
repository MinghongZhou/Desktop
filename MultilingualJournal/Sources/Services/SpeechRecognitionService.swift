import Foundation
import Speech
import AVFoundation

/// Wraps on-device live speech recognition. Recognition is locale-locked
/// (a known Speech-framework limitation: it cannot detect language switches
/// mid-recording), so this records in a single chosen locale. Segment-level
/// language tagging happens afterward via `LanguageSegmenter` on the
/// resulting transcript.
@MainActor
final class SpeechRecognitionService: ObservableObject {
    @Published private(set) var transcript: String = ""
    @Published private(set) var isRecording: Bool = false
    @Published var authorizationError: String?

    private var recognizer: SFSpeechRecognizer?
    private let audioEngine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?

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
        transcript = ""

        guard let recognizer = SFSpeechRecognizer(locale: locale), recognizer.isAvailable else {
            throw RecognitionError.recognizerUnavailable
        }
        self.recognizer = recognizer

        let audioSession = AVAudioSession.sharedInstance()
        try audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
        try audioSession.setActive(true, options: .notifyOthersOnDeactivation)

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        if recognizer.supportsOnDeviceRecognition {
            request.requiresOnDeviceRecognition = true
        }
        self.request = request

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak request] buffer, _ in
            request?.append(buffer)
        }

        audioEngine.prepare()
        try audioEngine.start()
        isRecording = true

        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }
            Task { @MainActor in
                if let result {
                    self.transcript = result.bestTranscription.formattedString
                }
                if error != nil || (result?.isFinal ?? false) {
                    self.stopRecording()
                }
            }
        }
    }

    func stopRecording() {
        guard isRecording || audioEngine.isRunning else { return }
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        task?.cancel()
        task = nil
        request = nil
        isRecording = false
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
