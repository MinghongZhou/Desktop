# UX Polish Handoff — Multilingual Journal (iOS)

**Author:** Live walkthrough on iPhone 17 simulator (iOS 26.5), viewing the app as a
senior iOS engineer + product designer.
**Date:** 2026-08-01
**Branch reviewed:** `new-brancj` @ `503bc90` ("Refine New Entry screen and connect Topics to their source")
**Purpose:** Concrete, implementable UX/design improvements for a future agent to pick
up. Each item has: what's wrong, where, why it matters, and a concrete fix. Findings
are ranked by severity. This is a **polish pass** — the app already works and looks
good; these close the gaps between "works" and "feels finished."

---

## How to run (verified working)

```bash
cd MultilingualJournal
xcodegen generate            # regenerates the .xcodeproj (needed after adding files)
```
Then build/run on an iOS 26 simulator. On this Mac, `sudo xcode-select -s
/Applications/Xcode.app/Contents/Developer` was required once for the simulator
tooling. **Foundation Models (Companion + Corrections) DO run on the iOS 26.5
simulator** — no physical device needed to test the AI features.

Two harmless build warnings exist (`SpeechSynthesisService.Delegate.onFinish`
mutable-Sendable; AppIntents metadata skipped). Not in scope but easy wins.

---

## P0 — Must fix (core journaling is incomplete without these)

### 1. You cannot edit, delete, or share an entry
- **Where:** `Sources/Views/EntryDetailView.swift` — the only action is "Talk about
  this entry." No edit, no delete, no share. No swipe-to-delete on the timeline
  (`EntryListView.swift`) either.
- **Why it matters:** This is the single biggest gap. During testing, iOS autocorrect
  turned my Spanish "Estoy muy contento" into "Early mug contents con mi progreso" —
  and there was **no way to fix it and no way to delete the entry.** A journal that
  can't be corrected or pruned feels broken. It also blocks recovery from the
  wrong-recording-language failure mode (see P1.1).
- **Fix:**
  - Add **swipe-to-delete** on timeline rows + a delete (trash) action in
    `EntryDetailView`'s toolbar, with a confirmation dialog. `modelContext.delete(entry)`.
  - Add an **Edit** path: re-open the entry text in an editor (reuse `NewEntryView`'s
    text editor), re-run `LanguageSegmenter.segment` on save so language tags update.
  - Add **Share** (`ShareLink`) to export an entry as text.
- **Consider:** let the user manually override a segment's detected language (tap a
  `LanguageBadge` → pick correct language) for when detection is wrong.

### 2. The "learning language" picker is a 40-item `Menu` with no search or scroll
- **Where:** `Sources/Views/SettingsView.swift` — `Picker` inside a `Menu`
  (both "Language I'm learning" and "Recording language").
- **Why it matters:** During testing I literally could not scroll to "Spanish" — the
  `Menu` popover doesn't scroll reliably and there's no search field. ~40 languages
  in a flat menu is a poor pattern; users learning less-common languages can't reach them.
- **Fix:** Replace with a pushed selection screen (`NavigationLink` → searchable
  `List`) using `.searchable`. Standard iOS settings pattern; scales to any list length.

---

## P1 — High impact (fixes real friction found in the flow)

### 1. Voice recording language is buried and mis-defaults
- **Where:** `NewEntryView.swift` (read-only "Recording in X · change in Settings"
  hint) + `SettingsView.swift` (the actual picker). Default resolved to **English
  (Australia)** on a US-style device while the learning language was **Chinese**.
- **Why it matters:** For a *multilingual* app, switching recording language per entry
  is a core action, but it now requires: leave entry → Settings tab → scroll → open a
  broken menu → pick → return → start over. Also, `en-AU` as the default for a
  Chinese learner is jarring and likely to cause mis-transcription (the app's #1 known
  failure mode). See `RecordingLocale.resolve` + `SettingsView.resolvedRecordingID`.
- **Fix:**
  - Put an inline, one-tap **language chip on the New Entry voice screen** (revert the
    read-only hint to an interactive control, or add a compact menu button) so users
    can switch right before recording — where the decision actually happens.
  - Make the default smarter: seed the recording locale from the **learning language**
    when the user hasn't chosen one, instead of alphabetical `en-AU`.

### 2. First-run permissions are cold (two system prompts, no priming)
- **Where:** `NewEntryView.toggleRecording()` → `SpeechRecognitionService.requestAuthorization()`.
- **Why it matters:** Tapping the mic fires **two back-to-back system dialogs**
  (Speech Recognition, then Microphone) with no in-app explanation first. A single
  cold "Don't Allow" permanently kills voice with no easy recovery. The Info.plist
  usage strings are good, but the sequencing invites denial.
- **Fix:** Add a lightweight **pre-permission priming sheet** ("To transcribe your
  voice on-device, the app needs the mic and speech recognition") with a single
  "Continue" that then triggers the system prompts. Standard conversion-protecting
  pattern.

### 3. Recording error reuses the "Permission needed" alert with a wrong title
- **Where:** `NewEntryView.toggleRecording()` catch-path sets `authorizationError` and
  shows the **"Permission needed"** alert — but the body I hit was *"Speech recognition
  isn't available for this language on this device right now"*, which is **not** a
  permission problem.
- **Why it matters:** Title/body mismatch is confusing, and the alert is a dead end —
  it offers no next step (switch to Text? change language? retry?).
- **Fix:** Separate "permission denied" from "recognizer/model unavailable" into
  distinct alerts with correct titles. For the unavailable case, offer a **"Switch to
  Text" action** and/or a suggestion to change recording language.

### 4. Text editor uses English autocorrect — hostile to multilingual writing
- **Where:** `NewEntryView.textEntry` (`TextEditor`).
- **Why it matters:** This is the app's core promise (write in any language), yet
  autocorrect mangled my Spanish into English nonsense as I typed. Deeply on-brand to fix.
- **Fix:** On the `TextEditor`, set `.autocorrectionDisabled(true)` (or relax it) and
  consider `.textInputAutocapitalization(.sentences)` only. At minimum, disable
  autocorrect so foreign-language input survives. (iOS won't auto-switch the keyboard
  language, but not corrupting input is the floor.)

### 5. Corrections entry point didn't appear for a valid target-language entry — verify
- **Where:** `EntryDetailView.hasTargetLanguageSegments` reads
  `AppSettings.targetLanguageCode` — a **plain static computed var over UserDefaults**,
  not an `@AppStorage`/observed value.
- **What I saw:** After setting the learning language to **English**, an entry with a
  segment badged **English** still did **not** show "See gentle corrections" (only the
  companion button). Trends simultaneously showed "ENGLISH VOCABULARY", confirming the
  setting was `en`.
- **Why it matters:** If reproducible, the gentle-corrections feature is silently
  unreachable in exactly the case it's meant for. Likely cause: the non-reactive read
  + view caching means visibility doesn't recompute when the target language changes.
- **Fix:** Drive `hasTargetLanguageSegments` off an `@AppStorage(targetLanguageCodeKey)`
  property so the view reacts. Then verify the button appears. Also double-check the
  code-comparison isn't tripped by region variants (`en` vs `en-US`).

---

## P2 — Polish (raises perceived quality)

### 1. Companion voice sounds robotic — pick a better voice tier ⭐ (user-reported)
- **Where:** `Sources/Services/SpeechSynthesisService.swift:31`
  ```swift
  utterance.voice = languageCode.flatMap(AVSpeechSynthesisVoice.init(language:))
  ```
- **Root cause:** `AVSpeechSynthesisVoice(language:)` returns the **default *compact***
  voice — the low-fi robotic tier. iOS also has **enhanced** and **premium** (neural)
  voices that sound far more human, but the app never requests them.
- **Fix (free, offline, biggest win):** enumerate `AVSpeechSynthesisVoice.speechVoices()`,
  filter to the reply's language prefix, and pick the highest `.quality`
  (`.premium` → `.enhanced` → `.default`). Sketch:
  ```swift
  func bestVoice(for language: String) -> AVSpeechSynthesisVoice? {
      let matches = AVSpeechSynthesisVoice.speechVoices()
          .filter { $0.language.hasPrefix(language.prefix(2)) }
      return matches.max { a, b in a.quality.rawValue < b.quality.rawValue }
          ?? AVSpeechSynthesisVoice(language: language)
  }
  ```
- **Then:** premium/enhanced voices must be **downloaded by the user** (Settings →
  Accessibility → Spoken Content → Voices). Detect when only a compact voice exists and
  show a one-time, gentle nudge with instructions. Optionally tune
  `utterance.rate`/`pitchMultiplier` slightly for warmth.
- **Ceiling / optional tier:** truly human, expressive voice needs **cloud neural TTS**
  (ElevenLabs / OpenAI / Google) — but that breaks the app's offline/private/no-key
  principle. If desired, add it as an **opt-in "high-quality voice"** toggle, framed
  like the existing on-device-vs-cloud tradeoffs in the README. Do NOT make it the default.

### 2. Companion emits raw markdown/roleplay tokens
- **What I saw:** A reply began literally with `*Hugs*` (rendered as raw asterisks).
- **Where:** `CompanionChatView.bubble(for:)` renders `message.text` as a plain `Text`.
- **Fix:** Either render as markdown (`Text(.init(message.text))`) so `*...*` becomes
  emphasis, or strip stray leading roleplay tokens / normalize asterisks. Add a light
  instruction to `CompanionService.systemPrompt` to avoid stage-direction asterisks.

### 3. Entry Detail is top-weighted with a large empty void
- **Where:** `EntryDetailView` — content sits at the top; the single CTA floats with a
  big blank lower half on a tall phone.
- **Fix:** Once edit/delete/share land (P0.1) the toolbar fills out. Also consider
  moving primary actions into a bottom action area, or surfacing entry metadata
  (source citation, languages, word count, "written by voice/text") to balance the layout.

### 4. Topic prompts are identical and redundant
- **Where:** `TopicPromptBuilder` / `Sources/Views/TopicsView.swift`.
- **What I saw:** Every card uses the exact scaffold *"In the news today: '{headline}'.
  What's your reaction? Does it connect to anything in your own life?"* — and it
  **re-quotes the headline that's already shown right above it.**
- **Why it matters:** Repetition makes the feature feel templated/robotic after 2-3 cards.
- **Fix:** Add a small pool of prompt templates per language and vary them
  (deterministically by headline hash so it's stable). Drop the verbatim headline
  re-quote from the prompt body since the headline is already displayed; ask the
  reflective question directly.

### 5. Practice-calendar heatmap is decorative, not legible
- **Where:** `JournalProgressView.calendar` (28-cell grid).
- **Why it matters:** No day-of-week labels, no month markers, no "today" indicator, no
  legend. Users can't read *when* they practiced (contrast GitHub's contribution graph).
- **Fix:** Add weekday column headers, mark today's cell (ring/outline), and a subtle
  date/month label. Optionally intensity-shade by entry count.

### 6. Vocabulary "new words" includes stopwords
- **Where:** `VocabularyAnalyzer` / `JournalProgressView`.
- **What I saw:** "Recently used for the first time: really, good, day, was" — function
  words padding the metric.
- **Why it matters:** "New words: was, day" doesn't feel like earned vocabulary growth;
  it undercuts the encouragement the screen is going for.
- **Fix:** Filter a per-language stopword list before counting "distinct/new words," or
  weight by word rarity. Keeps the number meaningful.

### 7. Redundant label + missing About section in Settings
- **Where:** `SettingsView` — section header "LANGUAGE I'M LEARNING" is immediately
  followed by a row whose label is *also* "Language I'm learning" (the "Recording
  language" section is cleaner with "Speak in"). No About/version/privacy row.
- **Fix:** Shorten the row label (e.g., "Language") since the section already names it.
  Add a small **About** section (version, a one-line privacy statement linking to the
  strong on-device story the README already tells).

### 8. Saving returns Home instead of opening the new entry
- **Where:** `NewEntryView.save()` → `dismiss()`.
- **Why it matters:** A just-written entry is the perfect moment to reflect/talk;
  bouncing to Home adds a step to do anything with it.
- **Fix (optional):** After save, navigate into the new entry's detail (or offer
  "Talk about this" inline). Low effort, nice momentum.

### 9. First-launch onboarding is absent
- **Where:** app entry (`RootView` / `EntryListView` empty state).
- **Why it matters:** A new user lands cold — no explanation of the code-switching
  superpower, the recording-language lock caveat, or setting a learning language.
- **Fix:** A 2-3 screen first-run intro (skippable) that (a) sells code-switching, (b)
  sets the learning language, (c) explains the recording-language-before-you-speak
  caveat. Ties together several items above.

### 10. Product name is inconsistent
- **What I saw:** Permission dialog title shows **"MultilingualJournal"** (no space)
  while the custom usage string says **"Multilingual Journal"** (with space).
- **Fix:** Set `CFBundleDisplayName` to "Multilingual Journal" in `project.yml` so the
  system-rendered app name matches the copy.

---

## What was verified working well (keep it)

- **Language segmentation is accurate** — a mixed EN/ES entry tagged both correctly.
- **The warm terracotta/cream design system is cohesive** and genuinely attractive;
  serif headings + `warmCard` shadows read as premium. Don't flatten it.
- **Companion AI works and is warm/on-brand** (short, one gentle follow-up).
- **Privacy messaging is excellent** throughout (on-device, entries never leave device).
- **Streak card correctly hides** when the streak is 0 and appears after an entry.
- **Topics with article images + source links** look great and reacted instantly to the
  language change.
- **Unavailable-state messaging for AI** (`CompanionService.message(for:)`) is specific
  and actionable — a model for the other error paths to follow.

---

## Suggested sequencing for the next session

1. **P0.1 edit/delete/share** — unblocks everything and is the biggest felt gap.
2. **P1.4 disable autocorrect** + **P1.3 fix the misleading alert** — tiny, high value.
3. **P2.1 better TTS voice** — user-requested, one function, big perceived-quality jump.
4. **P1.1 inline recording-language + smarter default** and **P0.2 searchable language
   picker** — together fix the multilingual-switching friction.
5. **P1.5 verify the corrections-button bug.**
6. Everything else in P2 as polish.
