import SwiftUI
import SwiftData

@main
struct MultilingualJournalApp: App {
    var body: some Scene {
        WindowGroup {
            EntryListView()
        }
        .modelContainer(for: JournalEntry.self)
    }
}
