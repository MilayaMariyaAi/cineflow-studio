# CineFlow Production Invariants & Guardrails

This document specifies the core domain rules and invariants of the CineFlow filmmaking engine. Every agent (Cursor, Trae, Kimi Code, OpenCode, Codex) must strictly observe these invariants.

---

## 1. Rule A: The Bilingual Bridge (Language Separation)

- **User Communication, Screenplay, Dramaturgy:** User's native language (Russian, Chinese, English, etc.).
- **Visual Generation Prompts (`prompt`, `camera_motion`, `lighting`):** **STRICTLY CINEMATIC ENGLISH**.
  - Diffusion models (LTX-Video, FLUX, MiniMax H3, Wan 2.1) are trained primarily on English captions.
  - Never include Cyrillic, Chinese characters, or non-English phrases in visual diffusion prompts.
  - Never include Chinese quality tags (e.g. `杰作, 高画质`); translate literary descriptions into cinematic English terms: `cinematic 35mm anamorphic, slow tracking dolly-in, soft rim light, 8k photo-real, subtle grain`.

---

## 2. Rule B: Reference Slot Policy (`ref_policy.py`)

- Reference images attached to a shot are decided by the shot's structure:
  - Characters present -> Character turnaround sheets.
  - Scene environment -> Location plate.
  - Key props -> Prop cards.
- **Addressing Invariant:**
  - Every attached reference image **MUST be explicitly addressed** in the prompt as `<Subject 1>`, `<Subject 2>`, etc. (or `<Picture 1>`, `<Picture 2>`).
  - If a shot declares 3 references (2 characters + 1 location), the prompt must explicitly mention all three.
  - **No silent truncation:** Never add hardcoded `refs[:N]`. Truncating references silently leads to identity loss or diffusion hallucinations.
  - If an optional reference is unaddressed, it must be explicitly pruned and the remaining references renumbered `1..K`.

---

## 3. Rule C: Character Names: Source Name vs `render_name` Alias

- **The Distinction:**
  - `Character.name`: Authorial/source name (e.g. "Мартин", "Лиза").
  - `Character.render_name`: Prompt-facing alias assigned from `cineflow/characters/render_name_pool.py` (e.g. "Nadia", "Arthur").
- **CF-PROMPT-SUBTRACT:** The authorial name must NEVER reach an image/video generation prompt.
- **Identity Resolution:**
  - `character_by_name` dicts index a character under both `name` and `render_name`.
  - **Comparing names directly as raw strings is a critical bug!** (Issue #77).
  - The planner/shot-writer LLM writes `render_name` into `charactersPresent`, while dialogue line `speaker_character_id` resolves to `Character.name`. Comparing these raw strings misreads one person as two disjoint entities.
  - **Invariant:** Always resolve characters to `Character.id` before unioning, diffing, or deduping cast lists!

---

## 4. Rule D: Closed-Mouth Lip-Sync Guard (Issue #600)

- Video diffusion models (MiniMax H3, LTX-Video) attempt to animate lips whenever audio, dialogue, or speaking verbs are detected.
- If a clip is a **silent reaction shot**, **voiceover (off-camera narrator)**, or **pure ambient music**:
  - **FORBIDDEN TOKENS:** Never use speaking verbs: *"speaks, talks, murmurs, whispers, sings, mouths, delivers line"*.
  - **MANDATORY RESTRAINT TOKENS:** Always inject explicit mouth-restraint tokens:
    `"lips firmly closed, relaxed jaw, silent focused expression, listening quietly"`.
- Before rendering, verify the frame with `cineflow_vision_inspect(focus="closed_mouth")`.

---

## 5. Qwen Visual Observation Invariant

- Diagnostic output from Qwen 3.8 / Qwen 2.5-VL Vision CV (aesthetic scores, defect notes, visual summaries) is **ephemeral telemetry**.
- **STRICT INVARIANT:** Do NOT write visual Qwen observations back into canonical plan, character, costume, or location records in `project.json` or database tables.
- Visual observations may suggest edits to the user, but changes to canonical records require explicit human confirmation.
