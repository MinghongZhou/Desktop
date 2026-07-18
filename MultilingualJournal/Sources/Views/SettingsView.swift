import SwiftUI

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var apiKey: String = KeychainService.read(account: CompanionService.apiKeyAccount) ?? ""
    @State private var didSave = false

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
