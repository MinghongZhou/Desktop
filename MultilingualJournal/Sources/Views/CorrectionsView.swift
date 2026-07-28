import SwiftUI

/// Shown only when the user opts in via "See gentle corrections" — never
/// surfaced automatically, and each suggestion can be dismissed without
/// affecting the saved entry text itself.
struct CorrectionsView: View {
    @Bindable var entry: JournalEntry
    @Environment(\.dismiss) private var dismiss

    @State private var isLoading = false
    @State private var errorMessage: String?

    private var visibleCorrections: [Correction] {
        entry.corrections.filter { !$0.isDismissed }
    }

    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    ProgressView("Looking for a couple of gentle suggestions…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let errorMessage {
                    ContentUnavailableView("Couldn't load suggestions", systemImage: "exclamationmark.bubble", description: Text(errorMessage))
                } else if visibleCorrections.isEmpty {
                    ContentUnavailableView(
                        "Nothing to flag here",
                        systemImage: "checkmark.circle",
                        description: Text("This entry's target-language sentences already read naturally.")
                    )
                } else {
                    List {
                        ForEach(visibleCorrections) { correction in
                            VStack(alignment: .leading, spacing: 6) {
                                Text(correction.originalText)
                                    .strikethrough()
                                    .foregroundStyle(Theme.secondary)
                                Text(correction.suggestion)
                                    .font(Theme.serif(16))
                                    .foregroundStyle(Theme.heading)
                                Text(correction.note)
                                    .font(.footnote)
                                    .foregroundStyle(Theme.secondary)
                            }
                            .padding(.vertical, 4)
                            .listRowBackground(Theme.card)
                            .swipeActions {
                                Button("Dismiss", role: .destructive) {
                                    dismissCorrection(correction)
                                }
                            }
                        }
                    }
                    .scrollContentBackground(.hidden)
                }
            }
            .background(Theme.bg.ignoresSafeArea())
            .navigationTitle("Gentle corrections")
            .navigationBarTitleDisplayMode(.inline)
            .tint(Theme.accentDeep)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button("Refresh") { Task { await load(force: true) } }
                        .disabled(isLoading)
                }
            }
            .task {
                if entry.correctionsFetchedAt == nil {
                    await load(force: false)
                }
            }
        }
    }

    private func dismissCorrection(_ correction: Correction) {
        guard let index = entry.corrections.firstIndex(where: { $0.id == correction.id }) else { return }
        entry.corrections[index].isDismissed = true
    }

    private func load(force: Bool) async {
        isLoading = true
        errorMessage = nil
        do {
            let fetched = try await CorrectionsService.fetchCorrections(for: entry)
            entry.corrections = fetched
            entry.correctionsFetchedAt = .now
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

#Preview {
    CorrectionsView(entry: JournalEntry(segments: [EntrySegment(text: "Yo tiene un perro.", languageCode: "es", order: 0)], source: .text))
}
