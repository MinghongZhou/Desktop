import SwiftUI
import Speech

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var apiKey: String = KeychainService.read(account: CompanionService.apiKeyAccount) ?? ""
    @AppStorage(AppSettings.targetLanguageCodeKey) private var targetLanguageCode: String = ""
    @AppStorage(AppSettings.autoSpeakRepliesKey) private var autoSpeakReplies: Bool = true

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
                    SecureField("sk-ant-...", text: $apiKey)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                } header: {
                    Text("Claude API key")
                } footer: {
                    Text("Your key is stored only on this device (Keychain) and is used to talk to the journaling companion. Get one at console.anthropic.com.")
                }

                if !apiKey.isEmpty {
                    Section {
                        Button("Remove key", role: .destructive) {
                            KeychainService.delete(account: CompanionService.apiKeyAccount)
                            apiKey = ""
                        }
                    }
                }

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
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        let trimmed = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
                        if trimmed.isEmpty {
                            KeychainService.delete(account: CompanionService.apiKeyAccount)
                        } else {
                            KeychainService.save(trimmed, account: CompanionService.apiKeyAccount)
                        }
                        dismiss()
                    }
                }
            }
        }
    }
}

#Preview {
    SettingsView()
}
