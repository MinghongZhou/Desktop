import SwiftUI

/// On-demand companion chat for a single entry. The entry's text is always
/// the companion's first turn of context, so opening this view alone
/// triggers a reflection — the user isn't required to type anything.
struct CompanionChatView: View {
    @Bindable var entry: JournalEntry
    @Environment(\.dismiss) private var dismiss

    @State private var draft: String = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingSettings = false

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

                inputBar
            }
            .navigationTitle("Companion")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
            .sheet(isPresented: $showingSettings) {
                SettingsView()
            }
            .task {
                if entry.companionMessages.isEmpty {
                    await requestReply(newUserMessage: nil)
                }
            }
        }
    }

    private var entryBubble: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("What you wrote")
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(entry.fullText)
                .padding(10)
                .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 12))
        }
    }

    private func bubble(for message: CompanionMessage) -> some View {
        HStack {
            if message.role == .companion { EmptyView() } else { Spacer(minLength: 40) }
            Text(message.text)
                .padding(10)
                .background(
                    message.role == .user ? Color.accentColor.opacity(0.2) : Color.secondary.opacity(0.15),
                    in: RoundedRectangle(cornerRadius: 12)
                )
            if message.role == .companion { Spacer(minLength: 40) } else { EmptyView() }
        }
    }

    private var inputBar: some View {
        HStack {
            TextField("Reply…", text: $draft, axis: .vertical)
                .textFieldStyle(.roundedBorder)
            Button {
                send()
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.title2)
            }
            .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isLoading)
        }
        .padding()
    }

    private func send() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        draft = ""
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

        do {
            let reply = try await CompanionService.reply(to: entry, history: history, newUserMessage: newUserMessage)
            entry.companionMessages.append(CompanionMessage(role: .companion, text: reply))
        } catch let error as CompanionService.CompanionError {
            errorMessage = error.errorDescription
            if case .missingAPIKey = error {
                showingSettings = true
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

#Preview {
    CompanionChatView(entry: JournalEntry(segments: [EntrySegment(text: "Hoy fue un buen día.", languageCode: "es", order: 0)], source: .text))
}
