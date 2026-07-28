import SwiftUI
import SwiftData

@main
struct MultilingualJournalApp: App {
    var body: some Scene {
        WindowGroup {
            RootView()
        }
        .modelContainer(for: JournalEntry.self)
    }
}
