import SwiftUI
import SwiftData
import Speech

/// On-demand companion chat for a single entry. The entry's text is always
/// the companion's first turn of context, so opening this view alone
/// triggers a reflection — the user isn't required to say anything.
///
/// Replies are voice-first: the primary way to answer is to speak. A small
/// keyboard fallback is kept only to fix a misrecognition (or to reply when
/// the recognizer is unavailable for the chosen language).
struct CompanionChatView: View {
    @Bindable var entry: JournalEntry
    /// All entries, so the companion can privately recall relevant past ones
    /// (see `MemoryService`) when it opens the conversation.
    @Query(sort: \JournalEntry.date, order: .reverse) private var allEntries: [JournalEntry]
    @Environment(\.dismiss) private var dismiss

    @State private var draft: String = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var isTyping = false
    @StateObject private var speech = SpeechSynthesisService()
    @StateObject private var recorder = SpeechRecognitionService()
    @AppStorage(AppSettings.autoSpeakRepliesKey) private var autoSpeakReplies: Bool = true
    @AppStorage(AppSettings.lastRecordingLocaleKey) private var savedLocaleID: String = ""
    @AppStorage(AppSettings.targetLanguageCodeKey) private var targetLanguageCode: String = ""

    /// Recording locale for a spoken reply — the same resolved choice used when
    /// writing entries, so the user speaks in a consistent language.
    private var availableLocales: [Locale] {
        SFSpeechRecognizer.supportedLocales().sorted {
            (Locale.current.localizedString(forIdentifier: $0.identifier) ?? $0.identifier) <
            (Locale.current.localizedString(forIdentifier: $1.identifier) ?? $1.identifier)
        }
    }

    private var resolvedLocaleID: String {
        RecordingLocale.resolve(
            savedIdentifier: savedLocaleID.isEmpty ? nil : savedLocaleID,
            supported: availableLocales.map(\.identifier),
            deviceLanguageCode: Locale.current.language.languageCode?.identifier,
            learningLanguageCode: targetLanguageCode.isEmpty ? nil : targetLanguageCode
        ) ?? Locale.current.identifier
    }

    /// The reply text pending send: the live transcript while recording,
    /// otherwise the current draft.
    private var pendingText: String {
        (recorder.isRecording ? recorder.transcript : draft)
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 12) {
                            entryBubble

                            ForEach(entry.companionMessages) { message in
                                bubble(for: message)
                                    .id(message.id)
                            }

                            if isLoading {
                                HStack {
                                    ProgressView()
                                    Text("Companion is thinking…")
                                        .foregroundStyle(.secondary)
                                }
                                .font(.subheadline)
                            }
                        }
                        .padding()
                    }
                    .onChange(of: entry.companionMessages.count) {
                        if let last = entry.companionMessages.last {
                            withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                        }
                    }
                }

                if let errorMessage {
                    Text(errorMessage)
                        .font(.footnote)
                        .foregroundStyle(.red)
                        .padding(.horizontal)
                }

                if speech.isSpeaking {
                    HStack {
                        Image(systemName: "speaker.wave.2.fill")
                        Text("Speaking…")
                        Spacer()
                        Button("Stop") { speech.stop() }
                    }
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal)
                }

                inputBar
            }
            .background(Theme.bg.ignoresSafeArea())
            .navigationTitle("Companion")
            .navigationBarTitleDisplayMode(.inline)
            .tint(Theme.accentDeep)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") {
                        speech.stop()
                        recorder.stopRecording()
                        dismiss()
                    }
                }
            }
            .task {
                if entry.companionMessages.isEmpty {
                    await requestReply(newUserMessage: nil)
                }
            }
            .onDisappear {
                speech.stop()
                recorder.stopRecording()
            }
        }
    }

    private var entryBubble: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("What you wrote")
                .font(.caption)
                .foregroundStyle(Theme.secondary)
            Text(entry.fullText)
                .font(.system(size: 15))
                .foregroundStyle(Theme.bodyText)
                .padding(12)
                .background(Theme.neutral, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
    }

    private func bubble(for message: CompanionMessage) -> some View {
        HStack(alignment: .bottom) {
            if message.role == .companion { EmptyView() } else { Spacer(minLength: 40) }
            // Render as markdown so stray tokens like *Hugs* show as emphasis
            // rather than literal asterisks. Falls back to plain text if the
            // string isn't valid markdown.
            Text(LocalizedStringKey(message.text))
                .font(message.role == .companion ? Theme.serif(16, weight: .regular) : .system(size: 15))
                .foregroundStyle(message.role == .companion ? Theme.bodyText : .white)
                .padding(12)
                .background(
                    message.role == .user ? Theme.accent : Theme.card,
                    in: RoundedRectangle(cornerRadius: 14, style: .continuous)
                )
                .shadow(color: message.role == .companion ? Theme.cardShadow : .clear, radius: 8, y: 4)
            if message.role == .companion {
                Button {
                    speech.speak(message.text)
                } label: {
                    Image(systemName: "speaker.wave.2")
                }
                .buttonStyle(.borderless)
                .foregroundStyle(.secondary)
            } else {
                EmptyView()
            }
            if message.role == .companion { Spacer(minLength: 40) } else { EmptyView() }
        }
    }

    // MARK: - Voice-first input

    private var inputBar: some View {
        VStack(spacing: 10) {
            // Live transcript while speaking, or the pending draft to review
            // before sending.
            if recorder.isRecording || !draft.isEmpty {
                replyPreview
            }

            if isTyping {
                HStack(spacing: 10) {
                    TextField("Type your reply…", text: $draft, axis: .vertical)
                        .textFieldStyle(.roundedBorder)
                        .autocorrectionDisabled(true)
                    Button { withAnimation { isTyping = false } } label: {
                        Image(systemName: "mic.fill")
                            .font(.title3)
                            .foregroundStyle(Theme.accentDeep)
                    }
                    sendButton
                }
            } else {
                HStack {
                    // Keyboard fallback — only for fixing what voice got wrong.
                    Button { withAnimation { isTyping = true } } label: {
                        Image(systemName: "keyboard")
                            .font(.title3)
                            .foregroundStyle(Theme.secondary)
                            .frame(width: 44, height: 44)
                    }
                    Spacer()
                    recordButton
                    Spacer()
                    sendButton
                        .frame(width: 44, height: 44)
                }
            }
        }
        .padding()
    }

    private var replyPreview: some View {
        let previewText = recorder.isRecording ? recorder.transcript : draft
        return Text(previewText.isEmpty ? "Listening…" : previewText)
            .font(.system(size: 15))
            .foregroundStyle(previewText.isEmpty ? Theme.secondary : Theme.bodyText)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(10)
            .background(Theme.neutral, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    private var recordButton: some View {
        Button { toggleRecording() } label: {
            ZStack {
                Circle()
                    .fill(recorder.isRecording ? Theme.accentDeep : Theme.accent)
                    .frame(width: 56, height: 56)
                Image(systemName: recorder.isRecording ? "stop.fill" : "mic.fill")
                    .font(.system(size: 22))
                    .foregroundStyle(.white)
            }
        }
        .disabled(isLoading)
    }

    private var sendButton: some View {
        Button { send() } label: {
            Image(systemName: "arrow.up.circle.fill")
                .font(.title2)
                .foregroundStyle(pendingText.isEmpty ? Theme.secondary.opacity(0.5) : Theme.accentDeep)
        }
        .disabled(pendingText.isEmpty || isLoading)
    }

    private func toggleRecording() {
        if recorder.isRecording {
            foldRecording()
            return
        }
        Task {
            guard await recorder.requestAuthorization() else {
                errorMessage = recorder.authorizationError
                    ?? "Enable the microphone and speech recognition in Settings to reply by voice."
                return
            }
            errorMessage = nil
            do {
                try recorder.startRecording(locale: Locale(identifier: resolvedLocaleID))
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }

    /// Stops recording and folds the spoken transcript into the draft so it can
    /// be reviewed, corrected via the keyboard fallback, or sent.
    private func foldRecording() {
        recorder.stopRecording()
        let spoken = recorder.transcript.trimmingCharacters(in: .whitespacesAndNewlines)
        if !spoken.isEmpty {
            draft = draft.isEmpty ? spoken : draft + " " + spoken
        }
        recorder.clearTranscript()
    }

    private func send() {
        if recorder.isRecording { foldRecording() }
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        draft = ""
        isTyping = false
        entry.companionMessages.append(CompanionMessage(role: .user, text: text))
        Task { await requestReply(newUserMessage: text) }
    }

    private func requestReply(newUserMessage: String?) async {
        isLoading = true
        errorMessage = nil
        // History excludes the message we just optimistically appended for
        // `newUserMessage` (it's passed separately) and excludes the reply
        // we're about to add.
        let history = newUserMessage == nil
            ? entry.companionMessages
            : Array(entry.companionMessages.dropLast())

        // Give the companion memory of past entries only on the opening
        // reflection — later turns already have the conversation as context,
        // so re-sending it every message would be redundant.
        let memory = newUserMessage == nil
            ? MemoryService.context(for: entry, from: allEntries)
            : nil

        do {
            let reply = try await CompanionService.reply(to: entry, history: history, newUserMessage: newUserMessage, memory: memory)
            entry.companionMessages.append(CompanionMessage(role: .companion, text: reply))
            if autoSpeakReplies {
                speech.speak(reply)
            }
        } catch let error as CompanionService.CompanionError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

#Preview {
    CompanionChatView(entry: JournalEntry(segments: [EntrySegment(text: "Hoy fue un buen día.", languageCode: "es", order: 0)], source: .text))
}
