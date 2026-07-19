# Multilingual Journal (iOS)

Voice/text journaling app that preserves code-switching: speak or type in
whatever language(s) feel natural, and the app detects and tags each
sentence's language rather than flattening the entry to one.

## Status: Phase 0 + Phase 1 (capture) + Phase 2 (companion chat) + Phase 3 (corrections)

- Record a voice entry (on-device `SFSpeechRecognizer`, live partial
  transcription) or type one.
- Transcript is split into sentence-level segments and each is tagged with a
  detected language (`NaturalLanguage` framework).
- Entries persist locally via SwiftData and show in a timeline.
- On-demand companion chat per entry (Claude API): opens with a reflection
  on what you wrote, replies in your entry's language(s), asks at most one
  gentle follow-up. User-supplied API key stored in Keychain via Settings.
- Optional, dismissible gentle corrections for sentences in your configured
  "language I'm learning" — up to 2 suggestions per entry, warm tone, never
  auto-shown.

Not yet built: voice-back (TTS), search, streaks. See the roadmap discussed
in chat for the phase order.

### Gentle corrections — how it works

- Set "Language I'm learning" in Settings first — corrections only look at
  segments detected as that language, and the button on an entry only
  appears once at least one segment matches.
- Fully opt-in: nothing runs until you tap "See gentle corrections," and
  each suggestion can be swiped away without touching the saved entry text.
- The model is instructed to flag at most 2 sentences per entry and skip
  anything already natural — the goal is occasional, useful nudges, not an
  error-checker. This is a prompt-level constraint, not a guarantee; keep an
  eye on tone as you use it for real.

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
  Models/     JournalEntry (SwiftData model), EntrySegment, CompanionMessage, Correction
  Services/   SpeechRecognitionService (recording + live transcription),
              LanguageSegmenter (sentence-level language tagging),
              CompanionService (companion chat via Claude API),
              CorrectionsService (gentle corrections via Claude API),
              KeychainService (API key storage), AppSettings (target language)
  Views/      EntryListView (timeline), NewEntryView (record/type + save),
              EntryDetailView, CompanionChatView, CorrectionsView, SettingsView,
              LanguageBadge
Tests/
  MultilingualJournalTests/  Unit tests for the pure logic (LanguageSegmenter,
                              JournalEntry computed properties, CorrectionsService
                              JSON parsing) — no network, mic, or simulator UI
                              interaction needed to run these.
```

## CI

`.github/workflows/multilingual-journal-ios-ci.yml` (repo root) runs on push
to this branch and on PRs touching `MultilingualJournal/`: `xcodegen
generate`, then `xcodebuild build` and `xcodebuild test` on a macOS GitHub
Actions runner (this project needs Xcode to build at all — there's no
Linux/CI-agnostic path). It only checks compilation and the unit tests
above; it can't exercise mic input, real speech, or actual UI/UX, so
on-device testing is still necessary before trusting a change.

## Setup: enabling the companion and corrections

1. Get an API key from console.anthropic.com.
2. In the app, tap the gear icon on the timeline → paste the key.
3. In the same screen, set "Language I'm learning" if you want corrections.
4. Tap Done. Open any entry → "Talk about this entry" or "See gentle corrections."

## Next steps

- Test recording + language tagging against real code-switched speech to see
  how much the locale-lock limitation actually hurts, before deciding on a
  cloud STT fallback.
- Phase 4: voice-back via `AVSpeechSynthesizer`.
