import SwiftUI

struct EntryDetailView: View {
    @Bindable var entry: JournalEntry
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss
    /// Read reactively (rather than via `AppSettings.targetLanguageCode`) so the
    /// corrections entry point recomputes when the learning language changes.
    @AppStorage(AppSettings.targetLanguageCodeKey) private var targetLanguageCode: String = ""

    @State private var isShowingCompanion = false
    @State private var isShowingCorrections = false
    @State private var isEditing = false
    @State private var isConfirmingDelete = false

    /// True when any segment is in the language the user is learning. Compared
    /// on the base language code so region variants (`en` vs `en-US`) still match.
    private var hasTargetLanguageSegments: Bool {
        let target = baseCode(targetLanguageCode)
        guard !target.isEmpty else { return false }
        return entry.segments.contains { segment in
            guard let code = segment.languageCode else { return false }
            return baseCode(code) == target
        }
    }

    private func baseCode(_ code: String) -> String {
        code.split(whereSeparator: { $0 == "-" || $0 == "_" }).first.map(String.init)?.lowercased()
            ?? code.lowercased()
    }

    /// Plain-text export for sharing: title, date, then the full entry.
    private var shareText: String {
        var parts: [String] = []
        if let title = entry.title, !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            parts.append(title)
        }
        parts.append(entry.date.formatted(date: .long, time: .omitted))
        parts.append(entry.fullText)
        return parts.joined(separator: "\n\n")
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    if let title = entry.title, !title.isEmpty {
                        Text(title)
                            .font(Theme.serif(26))
                            .foregroundStyle(Theme.heading)
                    }
                    Text(entry.date, style: .date)
                        .font(.subheadline)
                        .foregroundStyle(Theme.secondary)
                }

                if let headline = entry.sourceHeadline, !headline.isEmpty {
                    sourceCitation(headline: headline)
                }

                VStack(alignment: .leading, spacing: 14) {
                    ForEach(entry.segments.sorted(by: { $0.order < $1.order })) { segment in
                        VStack(alignment: .leading, spacing: 6) {
                            if let code = segment.languageCode {
                                LanguageBadge(languageCode: code)
                            }
                            Text(segment.text)
                                .font(.system(size: 16))
                                .foregroundStyle(Theme.bodyText)
                        }
                    }
                }
                .padding(18)
                .frame(maxWidth: .infinity, alignment: .leading)
                .warmCard()

                Button {
                    isShowingCompanion = true
                } label: {
                    Label(
                        entry.companionMessages.isEmpty ? "Talk about this entry" : "Continue the conversation",
                        systemImage: "bubble.left.and.bubble.right"
                    )
                }
                .buttonStyle(TerracottaButtonStyle())

                if hasTargetLanguageSegments {
                    Button {
                        isShowingCorrections = true
                    } label: {
                        Label("See gentle corrections", systemImage: "sparkles")
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundStyle(Theme.accentDeep)
                            .frame(maxWidth: .infinity)
                            .padding(14)
                            .background(Theme.accentSoft, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(20)
        }
        .background(Theme.bg.ignoresSafeArea())
        .scrollContentBackground(.hidden)
        .navigationTitle("Entry")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button {
                        isEditing = true
                    } label: {
                        Label("Edit", systemImage: "pencil")
                    }
                    ShareLink(item: shareText) {
                        Label("Share", systemImage: "square.and.arrow.up")
                    }
                    Divider()
                    Button(role: .destructive) {
                        isConfirmingDelete = true
                    } label: {
                        Label("Delete", systemImage: "trash")
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
                .tint(Theme.accentDeep)
            }
        }
        .sheet(isPresented: $isShowingCompanion) {
            CompanionChatView(entry: entry)
        }
        .sheet(isPresented: $isShowingCorrections) {
            CorrectionsView(entry: entry)
        }
        .sheet(isPresented: $isEditing) {
            EditEntrySheet(entry: entry)
        }
        .confirmationDialog(
            "Delete this entry?",
            isPresented: $isConfirmingDelete,
            titleVisibility: .visible
        ) {
            Button("Delete", role: .destructive) { deleteEntry() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This can't be undone.")
        }
    }

    private func deleteEntry() {
        modelContext.delete(entry)
        try? modelContext.save()
        dismiss()
    }

    private func sourceCitation(headline: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Inspired by")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(Theme.accentDeep)
                .textCase(.uppercase)
            if let urlString = entry.sourceURL, let url = URL(string: urlString), !urlString.isEmpty {
                Link(destination: url) {
                    Text(headline)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(Theme.accentDeep)
                        .multilineTextAlignment(.leading)
                }
            } else {
                Text(headline)
                    .font(.system(size: 14))
                    .foregroundStyle(Theme.bodyText)
            }
            if let publisher = entry.sourcePublisher, !publisher.isEmpty {
                Text("via \(publisher)")
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Theme.accentSoft, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

/// Edits an entry's title and text. On save the text is re-segmented so the
/// per-sentence language tags stay accurate after an edit (e.g. fixing an
/// autocorrect mangle that changed which languages appear).
private struct EditEntrySheet: View {
    @Bindable var entry: JournalEntry
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext

    @State private var title: String
    @State private var text: String

    init(entry: JournalEntry) {
        self.entry = entry
        _title = State(initialValue: entry.title ?? "")
        _text = State(initialValue: entry.fullText)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                TextField("Title", text: $title, axis: .vertical)
                    .font(Theme.serif(24, weight: .semibold))
                    .foregroundStyle(Theme.heading)
                    .lineLimit(1...2)
                    .autocorrectionDisabled(true)
                    .padding(.horizontal)

                TextEditor(text: $text)
                    .font(.system(size: 16))
                    .autocorrectionDisabled(true)
                    .scrollContentBackground(.hidden)
                    .padding(.horizontal)
                    .frame(maxHeight: .infinity)

                Spacer(minLength: 0)
            }
            .padding(.top)
            .background(Theme.bg.ignoresSafeArea())
            .navigationTitle("Edit entry")
            .navigationBarTitleDisplayMode(.inline)
            .tint(Theme.accentDeep)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { save() }
                        .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
    }

    private func save() {
        let segments = LanguageSegmenter.segment(text)
        guard !segments.isEmpty else { return }
        entry.segments = segments
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        entry.title = trimmedTitle.isEmpty ? nil : trimmedTitle
        try? modelContext.save()
        dismiss()
    }
}
