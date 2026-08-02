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
            deviceLanguageCode: Locale.current.language.languageCode?.identifier,
            learningLanguageCode: targetLanguageCode.isEmpty ? nil : targetLanguageCode
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

    /// Options for the learning-language picker: "Not set" plus every language
    /// the recognizer supports, by localized name.
    private var learningOptions: [LanguagePickerScreen.Option] {
        [LanguagePickerScreen.Option(id: "", name: "Not set")]
            + availableLanguages.map { LanguagePickerScreen.Option(id: $0.code, name: $0.name) }
    }

    /// Options for the recording-language picker: full recognizer locales.
    private var recordingOptions: [LanguagePickerScreen.Option] {
        availableRecordingLocales.map {
            LanguagePickerScreen.Option(
                id: $0.identifier,
                name: Locale.current.localizedString(forIdentifier: $0.identifier) ?? $0.identifier
            )
        }
    }

    private var appVersion: String {
        let short = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        if let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String, !build.isEmpty {
            return "\(short) (\(build))"
        }
        return short
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
                    NavigationLink {
                        LanguagePickerScreen(
                            title: "Language",
                            options: learningOptions,
                            selection: $targetLanguageCode
                        )
                    } label: {
                        pickerRow(label: "Language", value: targetLanguageName)
                    }
                    .buttonStyle(.plain)
                }
                footnote("Gentle corrections only look at sentences detected in this language.")

                Text("Recording language")
                    .sectionLabel()
                    .padding(.top, 6)
                card {
                    NavigationLink {
                        LanguagePickerScreen(
                            title: "Recording language",
                            options: recordingOptions,
                            selection: $recordingLocaleID
                        )
                    } label: {
                        pickerRow(label: "Speak in", value: recordingLanguageName)
                    }
                    .buttonStyle(.plain)
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

                Text("About")
                    .sectionLabel()
                    .padding(.top, 6)
                card {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Text("Version")
                                .font(.system(size: 15))
                                .foregroundStyle(Theme.bodyText)
                            Spacer()
                            Text(appVersion)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(Theme.secondary)
                        }
                        Divider()
                        Text("Everything stays on this device. Your journal entries are never uploaded, and the companion and gentle corrections run fully on-device.")
                            .font(.system(size: 13))
                            .foregroundStyle(Theme.secondary)
                    }
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

    /// A tappable settings row showing a label and the current value with a
    /// disclosure chevron, styled to match the warm capsule value pills.
    private func pickerRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 15))
                .foregroundStyle(Theme.bodyText)
            Spacer()
            HStack(spacing: 4) {
                Text(value)
                    .font(.system(size: 14, weight: .semibold))
                Image(systemName: "chevron.right").font(.system(size: 11))
            }
            .foregroundStyle(Theme.accentDeep)
            .padding(.horizontal, 14)
            .padding(.vertical, 7)
            .background(Theme.accentSoft, in: Capsule())
        }
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

/// A reusable, searchable language-selection screen. Scales to the ~40+
/// recognizer languages far better than a flat `Menu`, and is shared by both
/// the learning-language and recording-language settings.
struct LanguagePickerScreen: View {
    struct Option: Identifiable, Hashable {
        /// The value written to the binding: a language code, a locale
        /// identifier, or "" for the "Not set" option.
        let id: String
        let name: String
    }

    let title: String
    let options: [Option]
    @Binding var selection: String

    @Environment(\.dismiss) private var dismiss
    @State private var query = ""

    private var filtered: [Option] {
        guard !query.isEmpty else { return options }
        return options.filter { $0.name.localizedCaseInsensitiveContains(query) }
    }

    var body: some View {
        List {
            ForEach(filtered) { option in
                Button {
                    selection = option.id
                    dismiss()
                } label: {
                    HStack {
                        Text(option.name)
                            .font(.system(size: 16))
                            .foregroundStyle(Theme.bodyText)
                        Spacer()
                        if option.id == selection {
                            Image(systemName: "checkmark")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(Theme.accentDeep)
                        }
                    }
                }
                .listRowBackground(Theme.card)
            }
        }
        .scrollContentBackground(.hidden)
        .background(Theme.bg.ignoresSafeArea())
        .searchable(text: $query, prompt: "Search languages")
        .autocorrectionDisabled(true)
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
        .tint(Theme.accentDeep)
    }
}

#Preview {
    NavigationStack { SettingsView() }
}
