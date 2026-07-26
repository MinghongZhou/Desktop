# Multilingual Journal (iOS)

Voice/text journaling app that preserves code-switching: speak or type in
whatever language(s) feel natural, and the app detects and tags each
sentence's language rather than flattening the entry to one.

## Status: Phases 0–5 (Phase 5 partial — see "not yet built" below)

- Record a voice entry (on-device `SFSpeechRecognizer`, live partial
  transcription) or type one.
- Transcript is split into sentence-level segments and each is tagged with a
  detected language (`NaturalLanguage` framework).
- Entries persist locally via SwiftData and show in a timeline.
- On-demand companion chat per entry (on-device Apple Intelligence): opens
  with a reflection on what you wrote, replies in your entry's language(s),
  asks at most one gentle follow-up. No API key or network required.
- Optional, dismissible gentle corrections for sentences in your configured
  "language I'm learning" — up to 2 suggestions per entry, warm tone, never
  auto-shown. Also on-device.
- Entries can be given an optional title (searchable; shown in the timeline).
- Companion replies are spoken aloud (`AVSpeechSynthesizer`), voice matched
  to each reply's detected language. On by default, toggleable in Settings;
  any reply can be replayed (or stopped) by tapping its speaker icon.
- Search across the timeline, case- and diacritic-insensitive, matching entry
  text or language name ("spanish" pulls up your Spanish entries).
- Journaling streaks (current + longest) and a Progress sheet, plus an
  optional daily reminder notification.
- Vocabulary growth for the language you're learning: distinct words used,
  how many are new in the last 30 days, and a sample of recent first-uses.

**Not yet built:** widget / Siri Shortcut entry point. That one needs a
separate app-extension target (App Intents + a new bundle in `project.yml`),
which is a structural change rather than another feature file, so it was
deliberately left out of Phase 5 rather than rushed in.

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

### Streaks, reminders, and vocabulary — how they work

- A streak counts *distinct calendar days* with at least one entry, so five
  entries in one evening is still one day. The current streak survives if the
  last entry was today **or yesterday** — that grace day exists so someone who
  journals at night doesn't see a zero every morning.
- The daily reminder is a local notification only; nothing is sent anywhere.
  Turning the toggle on requests notification permission, and the toggle
  flips back off if permission is denied rather than silently pretending to
  be on.
- Vocabulary counts words you have **used**, not words you know. It doesn't
  check correctness (that's what gentle corrections are for), and a typo or a
  misheard word counts the same as a real one. It only looks at segments
  already tagged as your target language, so its accuracy inherits whatever
  the language detection got right. Treat the numbers as encouragement, not
  as a proficiency measure.

### Companion chat & corrections — powered by on-device Apple Intelligence

- Both the companion (`CompanionService`) and gentle corrections
  (`CorrectionsService`) run on Apple's **Foundation Models** framework —
  the on-device LLM. No API key, no network call, nothing leaves the device.
  That's a deliberate fit for a private journal, and it removes the adoption
  friction of asking every user for their own paid API key.
- Corrections use **guided generation** (`@Generable`), so the structured
  result is produced by the framework rather than parsed out of free-text
  JSON — more reliable than the previous prompt-and-parse approach.
- **Requires iOS 26+ on an Apple-Intelligence-capable device** (iPhone 15 Pro
  or newer, with Apple Intelligence enabled). On anything older the AI
  features show a clear "needs a newer device" message and are otherwise
  inert — all journaling, capture, search, streaks, and vocabulary features
  still work everywhere, since the deployment target stays iOS 17.
- Quality is below a frontier cloud model like Claude; that's the trade for
  free, private, offline operation. If higher quality is ever needed, a
  hybrid (on-device default + optional cloud key) or a hosted proxy could be
  layered back in — the service types are the only thing that would change.
- **No crisis-handling beyond an instruction**: the companion is told to
  respond with care and point to a crisis line if self-harm language appears,
  but there's no dedicated detection/escalation path. Treat as a baseline,
  not a safety feature to rely on.

### Voice-back — how it works, and its current limits

- Each companion reply's language is detected independently (same
  `NLLanguageRecognizer` approach as entry segmentation) and used to pick a
  matching system voice via `AVSpeechSynthesisVoice(language:)`. If no voice
  matches, it falls back to the device's default voice — quality will vary
  a lot by language depending on which voices are installed.
  Settings → "Speak companion replies aloud" installs no new voices itself;
  better voices for a given language may need downloading in iOS Settings →
  Accessibility → Spoken Content → Voices.
- Playback respects the mute switch / silent mode like any other app audio
  — there's no override to force sound in silent mode, which is standard
  behavior but worth knowing if voice-back seems to silently do nothing.
- No caching: replaying a message re-synthesizes it each time rather than
  storing audio. Fine at this reply length/frequency; would need revisiting
  if replies got long or replay became a heavily used interaction.

## Known limitation to be aware of

`SFSpeechRecognizer` is locale-locked per recording session — it **cannot
detect the spoken language or switch languages while you're talking**. You
choose the recording language *before* you start (via the "Speaking in"
selector on the record screen); if you speak a different language than the
one selected, it will mis-transcribe (e.g. Chinese speech coming out as
nonsense English). To make this less painful the app **remembers your last
chosen language** (`RecordingLocale` + persisted setting) so you're not
resetting it to English every time, and the selector is shown prominently
with a reminder to set it first.

Sentence-level language *tagging* still happens afterward, so an entry that
mixes languages across sentences is preserved and badged correctly — but
each recording chunk is only as good as the one language it was primed for.
True auto-detection / mid-sentence code-switching would require a cloud STT
model (e.g. Whisper), which auto-detects language and handles mixing far
better — at the cost of the on-device/offline/no-key properties. That's the
known trade-off if this limitation proves too constraining in real use.

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
              CompanionService (companion chat via on-device Foundation Models),
              CorrectionsService (gentle corrections via on-device Foundation Models),
              SpeechSynthesisService (voice-back via AVSpeechSynthesizer),
              EntrySearch (timeline filtering), StreakCalculator,
              VocabularyAnalyzer (word-use stats), ReminderService (local notifications),
              AppSettings (target language, auto-speak, reminder prefs)
  Views/      EntryListView (timeline + search + streak banner),
              NewEntryView (record/type + save), EntryDetailView,
              CompanionChatView, CorrectionsView, JournalProgressView,
              SettingsView, LanguageBadge
Tests/
  MultilingualJournalTests/  Unit tests for the pure logic (LanguageSegmenter,
                              JournalEntry computed properties, CorrectionsService
                              draft→Correction mapping, EntrySearch, StreakCalculator,
                              VocabularyAnalyzer) — no network, mic, model, or
                              simulator UI interaction needed to run these.
```

## CI

`.github/workflows/multilingual-journal-ios-ci.yml` (repo root) runs on push
to this branch and on PRs touching `MultilingualJournal/`: `xcodegen
generate`, then `xcodebuild build` and `xcodebuild test` on a macOS GitHub
Actions runner (this project needs Xcode to build at all — there's no
Linux/CI-agnostic path). It only checks compilation and the unit tests
above; it can't exercise mic input, real speech, or actual UI/UX, so
on-device testing is still necessary before trusting a change.

## Using the companion and corrections

No setup or API key needed — they run on the device's own Apple Intelligence
model. Requirements: iOS 26+ on an Apple-Intelligence device (iPhone 15 Pro or
newer) with Apple Intelligence enabled in iOS Settings. Then:

1. (For corrections) set "Language I'm learning" in the app's Settings.
2. Open any entry → "Talk about this entry" or "See gentle corrections."

On an unsupported device the features show a clear message and do nothing;
everything else in the app still works.

## Next steps

- Test recording + language tagging against real code-switched speech to see
  how much the locale-lock limitation actually hurts, before deciding on a
  cloud STT fallback.
- Search across entries, streaks/reminders, widget/Siri Shortcut entry point.
