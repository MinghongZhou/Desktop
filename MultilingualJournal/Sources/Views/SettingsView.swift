import SwiftUI
import Speech

/// The "Settings" tab, in the warm design language. Runs as a tab root, so it
/// has no NavigationStack/Done of its own (RootView provides the stack).
struct SettingsView: View {
    @AppStorage(AppSettings.targetLanguageCodeKey) private var targetLanguageCode: String = ""
    @AppStorage(AppSettings.autoSpeakRepliesKey) private var autoSpeakReplies: Bool = true
    @AppStorage(AppSettings.dailyReminderEnabledKey) private var dailyReminderEnabled: Bool = false
    @AppStorage(AppSettings.dailyReminderMinutesKey) private var reminderMinutes: Int = AppSettings.defaultReminderMinutes
    @AppStorage(AppSettings.newsTopicsEnabledKey) private var newsTopicsEnabled: Bool = true
    @AppStorage(AppSettings.lastRecordingLocaleKey) private var recordingLocaleID: String = ""
    @State private var reminderPermissionDenied = false

    /// Full recognizer locales (e.g. "en-US") for the recording-language picker.
    private var availableRecordingLocales: [Locale] {
        SFSpeechRecognizer.supportedLocales().sorted {
            (Locale.current.localizedString(forIdentifier: $0.identifier) ?? $0.identifier) <
            (Locale.current.localizedString(forIdentifier: $1.identifier) ?? $1.identifier)
        }
    }

    private var resolvedRecordingID: String {
        RecordingLocale.resolve(
            savedIdentifier: recordingLocaleID.isEmpty ? nil : recordingLocaleID,
            supported: availableRecordingLocales.map(\.identifier),
            deviceLanguageCode: Locale.current.language.languageCode?.identifier
        ) ?? Locale.current.identifier
    }

    private var recordingLanguageName: String {
        Locale.current.localizedString(forIdentifier: resolvedRecordingID) ?? resolvedRecordingID
    }

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

    private var availableLanguages: [(code: String, name: String)] {
        let codes = Set(SFSpeechRecognizer.supportedLocales().compactMap { $0.language.languageCode?.identifier })
        return codes
            .map { code in (code: code, name: Locale.current.localizedString(forLanguageCode: code) ?? code) }
            .sorted { $0.name < $1.name }
    }

    private var targetLanguageName: String {
        targetLanguageCode.isEmpty
            ? "Not set"
            : (Locale.current.localizedString(forLanguageCode: targetLanguageCode) ?? targetLanguageCode)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("Settings")
                    .font(Theme.serif(28))
                    .foregroundStyle(Theme.heading)
                    .padding(.top, 8)
                    .padding(.bottom, 4)

                Text("Language I'm learning")
                    .sectionLabel()
                card {
                    HStack {
                        Text("Language I'm learning")
                            .font(.system(size: 15))
                            .foregroundStyle(Theme.bodyText)
                        Spacer()
                        Menu {
                            Picker("Language I'm learning", selection: $targetLanguageCode) {
                                Text("Not set").tag("")
                                ForEach(availableLanguages, id: \.code) { language in
                                    Text(language.name).tag(language.code)
                                }
                            }
                        } label: {
                            HStack(spacing: 4) {
                                Text(targetLanguageName)
                                    .font(.system(size: 14, weight: .semibold))
                                Image(systemName: "chevron.up.chevron.down").font(.system(size: 11))
                            }
                            .foregroundStyle(Theme.accentDeep)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 7)
                            .background(Theme.accentSoft, in: Capsule())
                        }
                    }
                }
                footnote("Gentle corrections only look at sentences detected in this language.")

                Text("Recording language")
                    .sectionLabel()
                    .padding(.top, 6)
                card {
                    HStack {
                        Text("Speak in")
                            .font(.system(size: 15))
                            .foregroundStyle(Theme.bodyText)
                        Spacer()
                        Menu {
                            Picker("Recording language", selection: $recordingLocaleID) {
                                ForEach(availableRecordingLocales, id: \.identifier) { locale in
                                    Text(Locale.current.localizedString(forIdentifier: locale.identifier) ?? locale.identifier)
                                        .tag(locale.identifier)
                                }
                            }
                        } label: {
                            HStack(spacing: 4) {
                                Text(recordingLanguageName)
                                    .font(.system(size: 14, weight: .semibold))
                                Image(systemName: "chevron.up.chevron.down").font(.system(size: 11))
                            }
                            .foregroundStyle(Theme.accentDeep)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 7)
                            .background(Theme.accentSoft, in: Capsule())
                        }
                    }
                }
                footnote("The language voice recordings are transcribed in. Apple's recognizer can't switch languages mid-recording, so set this to match what you'll speak.")

                Text("Topics")
                    .sectionLabel()
                    .padding(.top, 6)
                card {
                    Toggle("News topics", isOn: $newsTopicsEnabled)
                        .font(.system(size: 15))
                        .tint(Theme.accent)
                }
                footnote("Turns current news into journaling prompts in your target language. This is the only feature that fetches from the internet — your journal entries always stay on this device. With it off, Topics shows timeless prompts instead.")

                Text("Companion")
                    .sectionLabel()
                    .padding(.top, 6)
                card {
                    Toggle("Speak replies aloud", isOn: $autoSpeakReplies)
                        .font(.system(size: 15))
                        .tint(Theme.accent)
                }
                footnote("Uses the device's built-in voices, matched to each reply's language. You can still tap any reply to hear it again, even with this off.")

                Text("Practice")
                    .sectionLabel()
                    .padding(.top, 6)
                card {
                    VStack(spacing: 12) {
                        Toggle("Daily reminder", isOn: $dailyReminderEnabled)
                            .font(.system(size: 15))
                            .tint(Theme.accent)
                        if dailyReminderEnabled {
                            Divider()
                            DatePicker("Remind me at", selection: reminderTime, displayedComponents: .hourAndMinute)
                                .font(.system(size: 15))
                        }
                    }
                }
                if reminderPermissionDenied {
                    footnote("Notifications are turned off for this app. Enable them in iOS Settings to get a daily nudge.", isError: true)
                } else {
                    footnote("A single gentle nudge each day. Scheduled on this device only — nothing is sent anywhere.")
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 24)
            .tint(Theme.accentDeep)
            .onChange(of: dailyReminderEnabled) { _, isOn in
                Task { await updateReminder(enabled: isOn) }
            }
        }
        .background(Theme.bg.ignoresSafeArea())
        .scrollContentBackground(.hidden)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar(.hidden, for: .navigationBar)
    }

    private func card<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        content()
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .warmCard(cornerRadius: 16)
    }

    private func footnote(_ text: String, isError: Bool = false) -> some View {
        Text(text)
            .font(.system(size: 13))
            .foregroundStyle(isError ? Color.red : Theme.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 4)
    }

    private func updateReminder(enabled: Bool) async {
        guard enabled else {
            ReminderService.cancel()
            reminderPermissionDenied = false
            return
        }
        let granted = await ReminderService.requestAuthorization()
        guard granted else {
            reminderPermissionDenied = true
            dailyReminderEnabled = false
            return
        }
        reminderPermissionDenied = false
        ReminderService.schedule(hour: reminderMinutes / 60, minute: reminderMinutes % 60)
    }
}

#Preview {
    NavigationStack { SettingsView() }
}
