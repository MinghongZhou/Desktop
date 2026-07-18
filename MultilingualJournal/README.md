# Multilingual Journal (iOS)

Voice/text journaling app that preserves code-switching: speak or type in
whatever language(s) feel natural, and the app detects and tags each
sentence's language rather than flattening the entry to one.

## Status: Phase 0 + core Phase 1 capture loop

- Record a voice entry (on-device `SFSpeechRecognizer`, live partial
  transcription) or type one.
- Transcript is split into sentence-level segments and each is tagged with a
  detected language (`NaturalLanguage` framework).
- Entries persist locally via SwiftData and show in a timeline.

Not yet built: AI companion chat, gentle corrections, voice-back (TTS),
search, streaks. See the roadmap discussed in chat for the phase order.

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
  Models/     JournalEntry (SwiftData model), EntrySegment
  Services/   SpeechRecognitionService (recording + live transcription),
              LanguageSegmenter (sentence-level language tagging)
  Views/      EntryListView (timeline), NewEntryView (record/type + save),
              EntryDetailView, LanguageBadge
```

## Next steps

- Test recording + language tagging against real code-switched speech to see
  how much the locale-lock limitation actually hurts, before deciding on a
  cloud STT fallback.
- Phase 2: on-demand AI companion chat (Claude API) per entry.
- Phase 3: gentle post-entry corrections for target-language segments.
- Phase 4: voice-back via `AVSpeechSynthesizer`.
