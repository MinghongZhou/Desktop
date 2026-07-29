import SwiftUI
import Speech

struct NewEntryView: View {
    /// When present, the entry is being written in response to a Topic: its
    /// prompt is shown as a banner and its article is cited on the saved entry.
    var topic: Topic? = nil

    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @StateObject private var speech = SpeechRecognitionService()

    /// Persisted so the recognizer defaults to the language you last spoke,
    /// instead of resetting to the device language (usually English) every
    /// time. Empty until the user has picked once; resolved against the
    /// recognizer's supported locales at use time.
    @AppStorage(AppSettings.lastRecordingLocaleKey) private var savedLocaleID: String = ""
    /// Single source of truth for the entry's content, shared across voice
    /// and text modes. Voice dictation appends to it; the text editor edits
    /// it directly — so switching modes never loses what's already there.
    @State private var text: String = ""
    @State private var title: String = ""
    @State private var mode: Mode = .voice
    @State private var usedVoice = false
    @State private var showingPermissionAlert = false

    private enum Mode: String, CaseIterable {
        case voice = "Voice"
        case text = "Text"
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
    /// choice against what's supported (falling back to device language).
    private var resolvedLocaleID: String {
        RecordingLocale.resolve(
            savedIdentifier: savedLocaleID.isEmpty ? nil : savedLocaleID,
            supported: availableLocales.map(\.identifier),
            deviceLanguageCode: Locale.current.language.languageCode?.identifier
        ) ?? Locale.current.identifier
    }

    /// Picker binding: reads the resolved identifier, writes the user's pick
    /// straight to persistent storage so it sticks for next time.
    private var localeSelection: Binding<String> {
        Binding(get: { resolvedLocaleID }, set: { savedLocaleID = $0 })
    }

    /// What the entry would contain right now, including any in-progress
    /// dictation that hasn't been folded into `text` yet.
    private var currentContent: String {
        speech.isRecording ? appended(text, speech.transcript) : text
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                if let topic {
                    topicBanner(topic)
                }

                TextField("Title (optional)", text: $title)
                    .font(.headline)
                    .textFieldStyle(.roundedBorder)
                    .padding(.horizontal)

                Picker("Mode", selection: $mode) {
                    ForEach(Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)

                if mode == .voice {
                    voiceEntry
                } else {
                    textEntry
                }

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
            .onChange(of: mode) { _, newMode in
                // Leaving voice mode mid-recording: stop and keep the text.
                if newMode == .text, speech.isRecording {
                    foldRecording()
                }
            }
            .alert("Permission needed", isPresented: $showingPermissionAlert, presenting: speech.authorizationError) { _ in
                Button("OK", role: .cancel) {}
            } message: { message in
                Text(message)
            }
        }
    }

    private var voiceEntry: some View {
        VStack(spacing: 16) {
            // Prominent, persistent language selector. Apple's recognizer
            // can't detect the language or switch mid-recording, so this must
            // be set before recording — hence the emphasis and helper text.
            HStack(spacing: 8) {
                Image(systemName: "globe")
                    .foregroundStyle(.secondary)
                Text("Speaking in")
                    .foregroundStyle(.secondary)
                Picker("Language", selection: localeSelection) {
                    ForEach(availableLocales, id: \.identifier) { locale in
                        Text(Locale.current.localizedString(forIdentifier: locale.identifier) ?? locale.identifier)
                            .tag(locale.identifier)
                    }
                }
                .labelsHidden()
                .disabled(speech.isRecording)
                Spacer()
            }
            .padding(.horizontal)

            Text("Pick your language before recording — it can't switch languages once you start.")
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal)

            ScrollView {
                Text(currentContent.isEmpty ? "Your words will appear here as you speak…" : currentContent)
                    .font(.system(size: 16))
                    .foregroundStyle(currentContent.isEmpty ? Theme.secondary : Theme.bodyText)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
            }
            .frame(minHeight: 200)
            .warmCard()
            .padding(.horizontal)

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
    }

    private var textEntry: some View {
        TextEditor(text: $text)
            .frame(minHeight: 240)
            .padding(.horizontal)
            .overlay(alignment: .topLeading) {
                if text.isEmpty {
                    Text("Write today's entry, in whatever language(s) feel right…")
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 20)
                        .padding(.top, 8)
                        .allowsHitTesting(false)
                }
            }
    }

    private func toggleRecording() {
        if speech.isRecording {
            foldRecording()
            return
        }
        Task {
            let authorized = await speech.requestAuthorization()
            guard authorized else {
                showingPermissionAlert = true
                return
            }
            do {
                try speech.startRecording(locale: Locale(identifier: resolvedLocaleID))
            } catch {
                speech.authorizationError = error.localizedDescription
                showingPermissionAlert = true
            }
        }
    }

    private func topicBanner(_ topic: Topic) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Today's topic")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(Theme.accentDeep)
                .textCase(.uppercase)
            Text(topic.prompt)
                .font(Theme.serif(17))
                .foregroundStyle(Theme.heading)
                .fixedSize(horizontal: false, vertical: true)
            if topic.hasSource {
                Text("via \(topic.publisher)")
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.secondary)
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

        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let entry = JournalEntry(
            segments: segments,
            source: usedVoice ? .voice : .text,
            title: trimmedTitle.isEmpty ? nil : trimmedTitle,
            sourceHeadline: topic?.hasSource == true ? topic?.headline : nil,
            sourceURL: topic?.hasSource == true ? topic?.articleURL : nil,
            sourcePublisher: topic?.hasSource == true ? topic?.publisher : nil
        )
        modelContext.insert(entry)
        // Flush immediately rather than relying on autosave timing, so the
        // entry survives even if the app is backgrounded/killed right after.
        try? modelContext.save()
        dismiss()
    }
}

#Preview {
    NewEntryView()
        .modelContainer(for: JournalEntry.self, inMemory: true)
}
