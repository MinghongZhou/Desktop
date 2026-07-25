import SwiftUI
import Speech

struct NewEntryView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @StateObject private var speech = SpeechRecognitionService()

    @State private var recordingLocale: Locale = .current
    @State private var manualText: String = ""
    @State private var mode: Mode = .voice
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

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
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
                        .disabled(currentTranscript.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .alert("Permission needed", isPresented: $showingPermissionAlert, presenting: speech.authorizationError) { _ in
                Button("OK", role: .cancel) {}
            } message: { message in
                Text(message)
            }
        }
    }

    private var currentTranscript: String {
        mode == .voice ? speech.transcript : manualText
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
                Text(speech.transcript.isEmpty ? "Your words will appear here as you speak…" : speech.transcript)
                    .foregroundStyle(speech.transcript.isEmpty ? .secondary : .primary)
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
        TextEditor(text: $manualText)
            .frame(minHeight: 240)
            .padding(.horizontal)
            .overlay(alignment: .topLeading) {
                if manualText.isEmpty {
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
            speech.stopRecording()
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

    private func save() {
        // Capture the text before stopping so a late recognition callback
        // can't affect what we persist.
        let text = currentTranscript
        speech.stopRecording()

        let segments = LanguageSegmenter.segment(text)
        guard !segments.isEmpty else { return }

        let entry = JournalEntry(segments: segments, source: mode == .voice ? .voice : .text)
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
