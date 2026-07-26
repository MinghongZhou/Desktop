import SwiftUI
import Speech

struct NewEntryView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @StateObject private var speech = SpeechRecognitionService()

    @State private var recordingLocale: Locale = .current
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

    /// What the entry would contain right now, including any in-progress
    /// dictation that hasn't been folded into `text` yet.
    private var currentContent: String {
        speech.isRecording ? appended(text, speech.transcript) : text
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
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
            .navigationTitle("New Entry")
            .navigationBarTitleDisplayMode(.inline)
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
            Picker("Language", selection: $recordingLocale) {
                ForEach(availableLocales, id: \.identifier) { locale in
                    Text(Locale.current.localizedString(forIdentifier: locale.identifier) ?? locale.identifier)
                        .tag(locale)
                }
            }
            .disabled(speech.isRecording)

            ScrollView {
                Text(currentContent.isEmpty ? "Your words will appear here as you speak…" : currentContent)
                    .foregroundStyle(currentContent.isEmpty ? .secondary : .primary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
            }
            .frame(minHeight: 200)
            .background(.quaternary.opacity(0.3), in: RoundedRectangle(cornerRadius: 12))
            .padding(.horizontal)

            Button {
                toggleRecording()
            } label: {
                Image(systemName: speech.isRecording ? "stop.circle.fill" : "mic.circle.fill")
                    .font(.system(size: 64))
                    .foregroundStyle(speech.isRecording ? .red : .accentColor)
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
                try speech.startRecording(locale: recordingLocale)
            } catch {
                speech.authorizationError = error.localizedDescription
                showingPermissionAlert = true
            }
        }
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
            title: trimmedTitle.isEmpty ? nil : trimmedTitle
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
