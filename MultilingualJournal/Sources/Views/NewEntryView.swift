import SwiftUI
import Speech
import AVFoundation

/// Entry capture is voice-first: speaking is the only primary input. A small
/// keyboard fallback ("Fix text") is kept solely to correct a misrecognition,
/// or to write the entry when the recognizer is unavailable for the chosen
/// language — it is never the front-and-center way in.
struct NewEntryView: View {
    /// When present, the entry is being written in response to a Topic: its
    /// prompt is shown as a banner and its article is cited on the saved entry.
    var topic: Topic? = nil
    /// Called with the freshly-saved entry so the presenter can open it.
    var onSaved: (JournalEntry) -> Void = { _ in }

    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @StateObject private var speech = SpeechRecognitionService()

    /// Persisted so the recognizer defaults to the language you last spoke,
    /// instead of resetting to the device language (usually English) every
    /// time. Empty until the user has picked once; resolved against the
    /// recognizer's supported locales at use time.
    @AppStorage(AppSettings.lastRecordingLocaleKey) private var savedLocaleID: String = ""
    /// The language being learned, used to seed a sensible default recording
    /// locale before the user has chosen one.
    @AppStorage(AppSettings.targetLanguageCodeKey) private var targetLanguageCode: String = ""

    /// The entry's content. Voice dictation appends to it; the optional
    /// keyboard fallback edits it directly.
    @State private var text: String = ""
    @State private var usedVoice = false
    /// Reveals the keyboard fallback editor. Voice stays primary; this only
    /// exists to fix a misrecognition or write when voice is unavailable.
    @State private var isEditingText = false
    @State private var showingPriming = false
    @State private var recordingError: RecordingError?
    @State private var recordingErrorText = ""

    /// Distinguishes a permissions problem (fixable in Settings) from the
    /// recognizer/model being unavailable for the chosen language (recoverable
    /// by typing or changing the language) — they need different copy.
    private enum RecordingError: Identifiable {
        case permissionDenied
        case recognizerUnavailable
        var id: Int { hashValue }
    }

    /// All locales the on-device recognizer supports, sorted for a picker.
    /// Kept unfiltered (rather than a hardcoded language list) per the
    /// "fully open" language scope decision.
    private var availableLocales: [Locale] {
        SFSpeechRecognizer.supportedLocales()
            .sorted {
                (Locale.current.localizedString(forIdentifier: $0.identifier) ?? $0.identifier) <
                (Locale.current.localizedString(forIdentifier: $1.identifier) ?? $1.identifier)
            }
    }

    /// The identifier the recognizer will actually use, resolving the saved
    /// choice against what's supported (falling back to the learning language,
    /// then the device language).
    private var resolvedLocaleID: String {
        RecordingLocale.resolve(
            savedIdentifier: savedLocaleID.isEmpty ? nil : savedLocaleID,
            supported: availableLocales.map(\.identifier),
            deviceLanguageCode: Locale.current.language.languageCode?.identifier,
            learningLanguageCode: targetLanguageCode.isEmpty ? nil : targetLanguageCode
        ) ?? Locale.current.identifier
    }

    private var resolvedLanguageName: String {
        Locale.current.localizedString(forIdentifier: resolvedLocaleID) ?? resolvedLocaleID
    }

    /// Shows the currently-resolved locale as selected while writing any change
    /// back to the persisted choice.
    private var recordingSelection: Binding<String> {
        Binding(get: { resolvedLocaleID }, set: { savedLocaleID = $0 })
    }

    /// What the entry would contain right now, including any in-progress
    /// dictation that hasn't been folded into `text` yet.
    private var currentContent: String {
        speech.isRecording ? appended(text, speech.transcript) : text
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 18) {
                if let topic {
                    topicBanner(topic)
                }

                voiceEntry

                Spacer()
            }
            .padding(.top)
            .background(Theme.bg.ignoresSafeArea())
            .navigationTitle("New Entry")
            .navigationBarTitleDisplayMode(.inline)
            .tint(Theme.accentDeep)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        speech.stopRecording()
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { save() }
                        .disabled(currentContent.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .alert(
                recordingErrorTitle,
                isPresented: Binding(
                    get: { recordingError != nil },
                    set: { if !$0 { recordingError = nil } }
                ),
                presenting: recordingError
            ) { kind in
                switch kind {
                case .permissionDenied:
                    Button("OK", role: .cancel) {}
                case .recognizerUnavailable:
                    // No text mode to fall back to anymore — offer the keyboard
                    // editor so the entry can still be written.
                    Button("Type instead") {
                        isEditingText = true
                        recordingError = nil
                    }
                    Button("Cancel", role: .cancel) {}
                }
            } message: { _ in
                Text(recordingErrorText)
            }
            .sheet(isPresented: $showingPriming) {
                permissionPrimingSheet
            }
        }
    }

    private var recordingErrorTitle: String {
        switch recordingError {
        case .permissionDenied: return "Permission needed"
        case .recognizerUnavailable: return "Language unavailable"
        case .none: return ""
        }
    }

    /// Shown once, before the system prompts, so a cold "Don't Allow" is less
    /// likely. Only presented when authorization hasn't been decided yet.
    private var permissionPrimingSheet: some View {
        VStack(spacing: 20) {
            Image(systemName: "mic.circle.fill")
                .font(.system(size: 54))
                .foregroundStyle(Theme.accent)
            Text("Journal by voice")
                .font(Theme.serif(24))
                .foregroundStyle(Theme.heading)
            Text("To transcribe your voice on-device, the app needs the microphone and speech recognition. Nothing is uploaded — transcription happens right here on your iPhone.")
                .font(.system(size: 15))
                .foregroundStyle(Theme.bodyText)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            Button("Continue") {
                showingPriming = false
                beginRecordingFlow()
            }
            .buttonStyle(TerracottaButtonStyle())
            Button("Not now") { showingPriming = false }
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(Theme.secondary)
        }
        .padding(28)
        .presentationDetents([.medium])
        .background(Theme.bg.ignoresSafeArea())
    }

    private var voiceEntry: some View {
        VStack(spacing: 16) {
            // Inline, one-tap recording-language switch — the decision happens
            // right here, just before speaking. Disabled mid-recording since
            // the recognizer can't change locale on the fly.
            HStack(spacing: 6) {
                Menu {
                    Picker("Recording language", selection: recordingSelection) {
                        ForEach(availableLocales, id: \.identifier) { locale in
                            Text(Locale.current.localizedString(forIdentifier: locale.identifier) ?? locale.identifier)
                                .tag(locale.identifier)
                        }
                    }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "globe").font(.caption)
                        Text("Recording in \(resolvedLanguageName)")
                            .font(.caption.weight(.semibold))
                        Image(systemName: "chevron.up.chevron.down").font(.system(size: 10))
                    }
                    .foregroundStyle(Theme.accentDeep)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 7)
                    .background(Theme.accentSoft, in: Capsule())
                }
                .disabled(speech.isRecording)
                Spacer()
            }
            .padding(.horizontal)

            transcriptCard

            recordButton
        }
    }

    /// The dictated text. Read-only while listening; tapping "Fix text" flips
    /// it into an editable keyboard fallback for correcting a misrecognition.
    private var transcriptCard: some View {
        Group {
            if isEditingText {
                TextEditor(text: $text)
                    // Off protects multilingual writing — English autocorrect
                    // mangles other languages as you type.
                    .autocorrectionDisabled(true)
                    .scrollContentBackground(.hidden)
                    .frame(minHeight: 200)
                    .padding(8)
                    .warmCard()
                    .padding(.horizontal)
                    .overlay(alignment: .bottomTrailing) {
                        Button {
                            isEditingText = false
                        } label: {
                            Label("Done", systemImage: "checkmark.circle.fill")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 7)
                                .background(Theme.accent, in: Capsule())
                        }
                        .padding(20)
                    }
            } else {
                ScrollView {
                    Text(currentContent.isEmpty ? "Tap the mic and just talk — your words appear here." : currentContent)
                        .font(.system(size: 16))
                        .foregroundStyle(currentContent.isEmpty ? Theme.secondary : Theme.bodyText)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding()
                }
                .frame(minHeight: 200)
                .warmCard()
                .padding(.horizontal)
                .overlay(alignment: .bottomTrailing) {
                    // Keyboard fallback for fixing what voice got wrong. Only
                    // once there's text to fix and we're not actively recording.
                    if !currentContent.isEmpty && !speech.isRecording {
                        Button {
                            isEditingText = true
                        } label: {
                            Label("Fix text", systemImage: "keyboard")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(Theme.secondary)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 7)
                                .background(Theme.neutral, in: Capsule())
                        }
                        .padding(20)
                    }
                }
            }
        }
    }

    private var recordButton: some View {
        Button {
            toggleRecording()
        } label: {
            ZStack {
                Circle()
                    .fill(speech.isRecording ? Theme.accentDeep : Theme.accent)
                    .frame(width: 78, height: 78)
                if speech.isRecording {
                    RoundedRectangle(cornerRadius: 6).fill(.white).frame(width: 26, height: 26)
                } else {
                    Image(systemName: "mic.fill").font(.system(size: 30)).foregroundStyle(.white)
                }
            }
        }
    }

    private func toggleRecording() {
        if speech.isRecording {
            foldRecording()
            return
        }
        // Recording takes over as the source of truth; leave the keyboard
        // fallback so the live transcript is visible.
        isEditingText = false
        // Prime with an in-app explanation before the system prompts, but only
        // the first time (when authorization hasn't been decided yet).
        if needsPermissionPriming {
            showingPriming = true
        } else {
            beginRecordingFlow()
        }
    }

    /// True when neither speech recognition nor the microphone has been decided
    /// yet, so a priming screen is worthwhile before the system dialogs.
    private var needsPermissionPriming: Bool {
        SFSpeechRecognizer.authorizationStatus() == .notDetermined
            || AVAudioApplication.shared.recordPermission == .undetermined
    }

    private func beginRecordingFlow() {
        Task {
            let authorized = await speech.requestAuthorization()
            guard authorized else {
                recordingErrorText = speech.authorizationError
                    ?? "Enable the microphone and speech recognition in Settings to journal by voice."
                recordingError = .permissionDenied
                return
            }
            do {
                try speech.startRecording(locale: Locale(identifier: resolvedLocaleID))
            } catch {
                recordingErrorText = error.localizedDescription
                recordingError = .recognizerUnavailable
            }
        }
    }

    private func topicBanner(_ topic: Topic) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Today's topic")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(Theme.accentDeep)
                .textCase(.uppercase)

            if !topic.imageURL.isEmpty, let url = URL(string: topic.imageURL) {
                ArticleImage(url: url, height: 130)
            }

            Text(topic.prompt)
                .font(Theme.serif(17))
                .foregroundStyle(Theme.heading)
                .fixedSize(horizontal: false, vertical: true)

            if topic.hasSource {
                if let url = URL(string: topic.articleURL) {
                    Link(destination: url) {
                        HStack(spacing: 4) {
                            Text("Read on \(topic.publisher)")
                            Image(systemName: "arrow.up.right")
                        }
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(Theme.accentDeep)
                    }
                } else {
                    Text("via \(topic.publisher)")
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.secondary)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Theme.accentSoft, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .padding(.horizontal)
    }

    /// Stops recording and appends what was dictated onto the shared text,
    /// then clears the recognizer so the next session starts fresh.
    private func foldRecording() {
        speech.stopRecording()
        if !speech.transcript.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            text = appended(text, speech.transcript)
            usedVoice = true
        }
        speech.clearTranscript()
    }

    /// Joins new dictation onto existing content with a single separating
    /// space, tolerant of leading/trailing whitespace on either side.
    private func appended(_ base: String, _ addition: String) -> String {
        let trimmedAddition = addition.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedAddition.isEmpty else { return base }
        let trimmedBase = base.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedBase.isEmpty else { return trimmedAddition }
        return trimmedBase + " " + trimmedAddition
    }

    private func save() {
        if speech.isRecording {
            foldRecording()
        } else {
            speech.stopRecording()
        }

        let segments = LanguageSegmenter.segment(text)
        guard !segments.isEmpty else { return }

        let entry = JournalEntry(
            segments: segments,
            // Voice is the primary path; the keyboard fallback only ever
            // corrects a voice draft, so treat a used recording as voice.
            source: usedVoice ? .voice : .text,
            title: nil,
            sourceHeadline: topic?.hasSource == true ? topic?.headline : nil,
            sourceURL: topic?.hasSource == true ? topic?.articleURL : nil,
            sourcePublisher: topic?.hasSource == true ? topic?.publisher : nil
        )
        modelContext.insert(entry)
        // Flush immediately rather than relying on autosave timing, so the
        // entry survives even if the app is backgrounded/killed right after.
        try? modelContext.save()
        // Hand the saved entry back so the presenter can open it (momentum:
        // the just-written entry is the ideal moment to reflect or talk).
        onSaved(entry)
        dismiss()
    }
}

#Preview {
    NewEntryView()
        .modelContainer(for: JournalEntry.self, inMemory: true)
}
