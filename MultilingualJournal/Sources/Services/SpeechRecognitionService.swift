import Foundation
import Speech
import AVFoundation

/// Wraps on-device live speech recognition. Recognition is locale-locked
/// (a known Speech-framework limitation: it cannot detect language switches
/// mid-recording), so this records in a single chosen locale. Segment-level
/// language tagging happens afterward via `LanguageSegmenter` on the
/// resulting transcript.
///
/// Supporting continuous, multi-sentence dictation is the tricky part here.
/// With on-device recognition, iOS frequently does NOT deliver an `isFinal`
/// result at a natural pause — instead it silently resets the current
/// request's internal buffer, after which `bestTranscription.formattedString`
/// returns only the newest utterance. Relying on `isFinal` to commit earlier
/// text therefore loses whole sentences when the speaker pauses.
///
/// So instead of waiting for iOS to signal the pause, this detects the pause
/// itself: every new partial resets a short silence timer, and when that
/// timer fires (the speaker has gone quiet) the current request's audio is
/// ended, which forces a final result. That result is folded into a
/// `finalizedText` accumulator and a fresh request is started over the
/// still-running audio engine, so each spoken sentence is committed before
/// iOS can drop it. `isFinal` is still handled as a belt-and-suspenders path.
@MainActor
final class SpeechRecognitionService: ObservableObject {
    @Published private(set) var transcript: String = ""
    @Published private(set) var isRecording: Bool = false
    @Published var authorizationError: String?

    private var recognizer: SFSpeechRecognizer?
    private let audioEngine = AVAudioEngine()
    private var task: SFSpeechRecognitionTask?

    /// Fires when no new partial has arrived for `silenceInterval`, i.e. the
    /// speaker paused — the cue to commit the current sentence and roll over.
    private var silenceTimer: Timer?
    private let silenceInterval: TimeInterval = 1.2

    /// Text from segments already committed. The live `transcript` is this
    /// plus the current in-progress partial.
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
        // Let the recognizer insert commas/periods itself, so multi-sentence
        // entries read naturally instead of as one unpunctuated run.
        request.addsPunctuation = true
        if recognizer.supportsOnDeviceRecognition {
            request.requiresOnDeviceRecognition = true
        }
        requestBox.request = request

        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            Task { @MainActor in
                self?.handle(result: result, error: error, from: request)
            }
        }
    }

    private func handle(result: SFSpeechRecognitionResult?, error: Error?, from request: SFSpeechAudioBufferRecognitionRequest) {
        // Ignore callbacks that arrive after the user has stopped (including
        // the cancellation callback triggered by `stopRecording`).
        guard isRecording else { return }

        // Ignore callbacks from a segment we've already rolled past. When we
        // force a final result (endAudio) and immediately start the next
        // segment, the old task keeps firing — a completion, then often an
        // error. Acting on those stale callbacks would call rollOverSegment()
        // again, nil out the freshly-created request, and orphan its task, so
        // after a sentence or two no audio reaches the live request and
        // recognition silently stalls. Only the current request may drive state.
        guard request === requestBox.request else { return }

        if let result {
            transcript = merged(partial: result.bestTranscription.formattedString)
            if result.isFinal {
                rollOverSegment()
            } else {
                // Still speaking — restart the pause detector.
                armSilenceTimer()
            }
        } else if error != nil {
            // The segment ended on an error (commonly a silence timeout).
            // Keep whatever we have and start a new segment so the user can
            // keep talking.
            rollOverSegment()
        }
    }

    /// (Re)starts the silence timer. When it fires, the speaker has paused, so
    /// we end the current request's audio to force a final result — which
    /// commits the sentence via the `isFinal` path before iOS can silently
    /// reset the buffer and lose it.
    private func armSilenceTimer() {
        silenceTimer?.invalidate()
        silenceTimer = Timer.scheduledTimer(withTimeInterval: silenceInterval, repeats: false) { [weak self] _ in
            Task { @MainActor in
                guard let self, self.isRecording else { return }
                // Ending audio triggers a final result for the current
                // request; `handle` then rolls over to a fresh segment.
                self.requestBox.request?.endAudio()
            }
        }
    }

    /// Folds the just-finalized segment into the accumulator and, if still
    /// recording, opens a new segment to continue.
    private func rollOverSegment() {
        silenceTimer?.invalidate()
        silenceTimer = nil
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
        let separator = needsSpaceJoin(after: finalizedText, before: partial) ? " " : ""
        return finalizedText + separator + partial
    }

    /// Whether a space belongs between two joined segments. Space-delimited
    /// scripts (Latin, Cyrillic, …) need one; scripts that don't space between
    /// words (Chinese, Japanese) must join tight, or multi-sentence entries
    /// come out with stray gaps like "今天很好 。 我很开心。".
    private func needsSpaceJoin(after base: String, before addition: String) -> Bool {
        guard let last = base.unicodeScalars.last,
              let first = addition.unicodeScalars.first else { return true }
        return !(isCJK(last) || isCJK(first))
    }

    private func isCJK(_ scalar: Unicode.Scalar) -> Bool {
        switch scalar.value {
        case 0x3000...0x303F,   // CJK symbols & punctuation （，。！？…）
             0x3040...0x30FF,   // Hiragana + Katakana
             0x3400...0x4DBF,   // CJK unified ideographs, extension A
             0x4E00...0x9FFF,   // CJK unified ideographs
             0xF900...0xFAFF,   // CJK compatibility ideographs
             0xFF00...0xFFEF:   // Fullwidth/halfwidth forms
            return true
        default:
            return false
        }
    }

    /// Clears the live transcript. Called by the view after it has folded a
    /// recording session's text into its own content, so the next session
    /// starts clean and can't be double-counted.
    func clearTranscript() {
        transcript = ""
        finalizedText = ""
    }

    func stopRecording() {
        guard isRecording || audioEngine.isRunning else { return }
        // Set this first so late recognition callbacks are ignored and can't
        // clobber the final transcript.
        isRecording = false
        silenceTimer?.invalidate()
        silenceTimer = nil
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
