# Dynamic Exam UI Architecture

To support a fully dynamic, highly accessible exam system, the `exam_application.html` template will be rewritten to act as a **Universal Assessment Renderer**. It will read a `type` field from the JSON and dynamically mount the correct accessible interface.

## 1. Supported Question Types & Accessibility Protocols

### A. Multiple Choice (`type: "multiple_choice"`)
- **UI:** Standard radio button list.
- **Accessibility:** `role="radiogroup"`, navigable via Up/Down arrow keys.

### B. Text Response / Fill-in-the-Blank (`type: "text_response"`)
- **UI:** A standard `<textarea>` or `<input type="text">`.
- **Accessibility:** Native focus management. Screen readers will read the prompt and focus the input field.

### C. Dropdown Completion (`type: "dropdown_blank"`)
- **UI:** A sentence with an inline `<select>` dropdown (e.g., "The capital of France is [Dropdown: Paris, London, Rome]").
- **Accessibility:** Native `<select>` elements are naturally accessible and easily navigable via keyboard.

### D. Match the Columns / Drag-and-Drop (`type: "match_columns"`)
- **UI:** Two columns of items to match.
- **Accessibility Challenge:** Standard drag-and-drop is hostile to screen readers and keyboard users.
- **Accessible Solution:** We will implement a "Click-to-Select, Click-to-Drop" keyboard flow. 
  - User tabs to an item on the left and presses `Enter`.
  - The Announcer says *"Selected Item A. Choose a target from the right column."*
  - User tabs to an item on the right and presses `Enter`.
  - The Announcer says *"Matched Item A with Item 2."*
  - This satisfies both visual mouse users (click-click) and screen reader users (Enter-Enter) perfectly.

## 2. Universal Media Embedder
Any question object can include an optional `media` payload.
```json
"media": {
  "type": "video", // or "audio", "image"
  "url": "/plugin/media?v=video_id",
  "alt_text": "Description of the visual content for screen readers"
}
```
- **Images:** Rendered as `<img src="..." alt="...">` with high contrast borders.
- **Audio:** Rendered as `<audio controls>` (native keyboard accessible).
- **Video:** Rendered as an `<iframe>` pointing to the existing Accessible Video Player plugin, ensuring the video controls are already screen-reader optimized.

## 3. Global Exam Timer
- If the AI includes `"timer_seconds": 600` at the root of the JSON, a persistent countdown clock is mounted at the top of the screen.
- **Accessibility:** The clock will NOT constantly announce the time (which drives screen reader users crazy). Instead, users can press a shortcut (e.g., `Alt+T`) to have the Announcer read the remaining time, and the system will automatically announce critical warnings ("5 minutes remaining", "Time is up").

## 4. Evaluation Engine
The `handleSubmitOrNext()` javascript function will be upgraded from checking a simple `correct_index` to calling specific evaluation logic based on the `q.type`. It will then inject the `q.explanation` into the feedback container just like before.
