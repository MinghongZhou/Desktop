import SwiftUI
import Speech

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @AppStorage(AppSettings.targetLanguageCodeKey) private var targetLanguageCode: String = ""
    @AppStorage(AppSettings.autoSpeakRepliesKey) private var autoSpeakReplies: Bool = true
    @AppStorage(AppSettings.dailyReminderEnabledKey) private var dailyReminderEnabled: Bool = false
    @AppStorage(AppSettings.dailyReminderMinutesKey) private var reminderMinutes: Int = AppSettings.defaultReminderMinutes
    @State private var reminderPermissionDenied = false

    /// Bridges the stored minutes-past-midnight value to a `DatePicker`.
    private var reminderTime: Binding<Date> {
        Binding(
            get: {
                let start = Calendar.current.startOfDay(for: .now)
                return Calendar.current.date(byAdding: .minute, value: reminderMinutes, to: start) ?? start
            },
            set: { newValue in
                let parts = Calendar.current.dateComponents([.hour, .minute], from: newValue)
                reminderMinutes = (parts.hour ?? 0) * 60 + (parts.minute ?? 0)
                if dailyReminderEnabled {
                    ReminderService.schedule(hour: parts.hour ?? 0, minute: parts.minute ?? 0)
                }
            }
        )
    }

    /// Deduped language codes (not full locales) from the same supported-locale
    /// list used for recording, so "language you're learning" lines up with
    /// what the app can actually detect segments as.
    private var availableLanguages: [(code: String, name: String)] {
        let codes = Set(SFSpeechRecognizer.supportedLocales().compactMap { $0.language.languageCode?.identifier })
        return codes
            .map { code in (code: code, name: Locale.current.localizedString(forLanguageCode: code) ?? code) }
            .sorted { $0.name < $1.name }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("Language I'm learning", selection: $targetLanguageCode) {
                        Text("Not set").tag("")
                        ForEach(availableLanguages, id: \.code) { language in
                            Text(language.name).tag(language.code)
                        }
                    }
                } footer: {
                    Text("Gentle corrections only look at sentences detected in this language.")
                }

                Section {
                    Toggle("Speak companion replies aloud", isOn: $autoSpeakReplies)
                } footer: {
                    Text("Uses the device's built-in voices, matched to each reply's language. You can still tap any reply to hear it again, or to stop, even with this off.")
                }

                Section {
                    Toggle("Daily reminder", isOn: $dailyReminderEnabled)
                    if dailyReminderEnabled {
                        DatePicker("Remind me at", selection: reminderTime, displayedComponents: .hourAndMinute)
                    }
                } footer: {
                    if reminderPermissionDenied {
                        Text("Notifications are turned off for this app. Enable them in iOS Settings to get a daily nudge.")
                            .foregroundStyle(.red)
                    } else {
                        Text("A single gentle nudge each day. Scheduled on this device only — nothing is sent anywhere.")
                    }
                }
            }
            .onChange(of: dailyReminderEnabled) { _, isOn in
                Task { await updateReminder(enabled: isOn) }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private func updateReminder(enabled: Bool) async {
        guard enabled else {
            ReminderService.cancel()
            reminderPermissionDenied = false
            return
        }

        let granted = await ReminderService.requestAuthorization()
        guard granted else {
            // Reflect reality: the toggle can't stay on without permission.
            reminderPermissionDenied = true
            dailyReminderEnabled = false
            return
        }

        reminderPermissionDenied = false
        ReminderService.schedule(hour: reminderMinutes / 60, minute: reminderMinutes % 60)
    }
}

#Preview {
    SettingsView()
}
