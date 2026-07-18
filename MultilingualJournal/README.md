# Multilingual Journal (iOS)

Voice/text journaling app that preserves code-switching: speak or type in
whatever language(s) feel natural, and the app detects and tags each
sentence's language rather than flattening the entry to one.

## Status: Phase 0 + Phase 1 (capture) + Phase 2 (companion chat)

- Record a voice entry (on-device `SFSpeechRecognizer`, live partial
  transcription) or type one.
- Transcript is split into sentence-level segments and each is tagged with a
  detected language (`NaturalLanguage` framework).
- Entries persist locally via SwiftData and show in a timeline.
- On-demand companion chat per entry (Claude API): opens with a reflection
  on what you wrote, replies in your entry's language(s), asks at most one
  gentle follow-up. User-supplied API key stored in Keychain via Settings.

Not yet built: gentle corrections, voice-back (TTS), search, streaks. See
the roadmap discussed in chat for the phase order.

### Companion chat — how it works, and its current limits

- **Bring-your-own-key**: the app calls `api.anthropic.com` directly from
  the device using a key you paste into Settings (Keychain-stored). This is
  fine for personal use / a small group of technical users, but is *not*
  how a real multi-user release should ship — a shipped app with a
  device-stored user key works, but a key baked into the app binary instead
  would be extractable. If this becomes a real product, add a thin backend
  proxy so the app never holds a long-lived secret and so usage/cost can be
  metered per user.
- **No streaming yet**: replies come back as a single response, not
  token-by-token — fine for short companion replies, but noticeable on
  slower connections. Worth revisiting if replies get longer.
- **No crisis-handling beyond a system-prompt instruction**: the companion
  is told to respond with care and point to a crisis line if self-harm
  language appears, but there's no dedicated detection/escalation path.
  Treat this as a baseline, not a safety feature to rely on.

## Known limitation to be aware of

`SFSpeechRecognizer` is locale-locked per recording session — it cannot
detect a language switch *while you're talking*. You pick a recognition
language before recording, and true code-switching detection only happens
afterward, at the sentence level, once the transcript exists. If someone
mixes languages within a single sentence, or switches to a language the
recognizer wasn't primed for, transcription quality will drop. A cloud STT
fallback (e.g. Whisper) is the likely fix if this turns out to matter in
practice — worth testing with real mixed-language speech before investing
there.

## Setup (macOS + Xcode required — this project was scaffolded outside Xcode)

1. Install [XcodeGen](https://github.com/yonaskolb/XcodeGen): `brew install xcodegen`
2. From this directory, run:
   ```
   xcodegen generate
   ```
   This produces `MultilingualJournal.xcodeproj` from `project.yml`.
3. Open `MultilingualJournal.xcodeproj` in Xcode.
4. Select a simulator or device (iOS 17+) and run.
5. On first launch, grant microphone and speech recognition permissions when
   prompted (voice entry won't work without both).

## Project layout

```
Sources/
  App/        App entry point, SwiftData container setup
  Models/     JournalEntry (SwiftData model), EntrySegment, CompanionMessage
  Services/   SpeechRecognitionService (recording + live transcription),
              LanguageSegmenter (sentence-level language tagging),
              CompanionService (Claude API calls), KeychainService (API key storage)
  Views/      EntryListView (timeline), NewEntryView (record/type + save),
              EntryDetailView, CompanionChatView, SettingsView, LanguageBadge
```

## Setup: enabling the companion

1. Get an API key from console.anthropic.com.
2. In the app, tap the gear icon on the timeline → paste the key → Done.
3. Open any entry → "Talk about this entry."

## Next steps

- Test recording + language tagging against real code-switched speech to see
  how much the locale-lock limitation actually hurts, before deciding on a
  cloud STT fallback.
- Phase 3: gentle post-entry corrections for target-language segments.
- Phase 4: voice-back via `AVSpeechSynthesizer`.
