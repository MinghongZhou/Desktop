import SwiftUI

/// Bottom tab navigation from the design: Home (timeline), Trends (progress),
/// and Settings. Each tab is its own navigation stack. The warm theme is a
/// light-only look, so the whole app is pinned to a light color scheme.
struct RootView: View {
    var body: some View {
        TabView {
            EntryListView()
                .tabItem { Label("Home", systemImage: "house.fill") }

            NavigationStack {
                JournalProgressView()
            }
            .tabItem { Label("Trends", systemImage: "chart.bar.fill") }

            NavigationStack {
                SettingsView()
            }
            .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
        .tint(Theme.accentDeep)
        .preferredColorScheme(.light)
    }
}
