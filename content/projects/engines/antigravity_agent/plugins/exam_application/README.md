# Siraugga Exam Application Plugin Guide

## Overview
The Siraugga Exam Application is a powerful, interactive testing module that lives directly inside your chat environment. It is designed to instantly convert any source material—no matter how large or complex—into a personalized, fully accessible assessment complete with multiple question types, anti-cheat mechanics, and detailed explanations.

## How to Create and Start an Exam
You have two ways to generate an exam: using the traditional chat prompt or using the new visual dashboard.

### Method 1: The Visual Exam Builder (Recommended)
You do not need to manually write prompts! Simply ask the Assistant to **"Open the Exam Builder."** 

This will launch a dedicated visual dashboard where you can:
- **Select Question Types:** Choose from Multiple Choice, Multi-Select (Checkboxes), Fill-in-the-blank (Text Boxes or Dropdowns), Comparison Tables (Matching), and Terminal Commands.
- **Manage Content Directly:** You can use a dropdown to select existing files from your `plugins/exam_application/content/` folder, or **upload new files directly through the UI** without ever leaving the dashboard.
- **Configure Settings:** Set precise timers (hours/minutes), toggle Anti-Cheat security, enable weighted scoring, and request media integration (images/audio) all via checkboxes.

### Method 2: Natural Language Generation
If you prefer, you can ask the Assistant dynamically:
1. **Drop in Your Content:** Place your source material (PDFs, text files) into the `plugins/exam_application/content/` folder. 
2. **Request an Exam:** Ask the Assistant to "create a 15-minute exam based on the uploaded file with weighted scoring and terminal commands."
3. **Automatic Activation:** The Assistant will analyze your content, formulate accurate questions and distractors, and automatically embed the interactive exam directly into your chat window.

## Taking the Exam
Once the exam appears, it guides you through the assessment:
- **Rich Interactive Questions:** Answer using standard radio buttons, fully accessible multi-select checkboxes, text boxes, or dropdown lists.
- **Instant Feedback & Explanations:** When you submit an answer, the application reveals whether you were correct and provides a **detailed explanation** to help you understand the reasoning behind it.
- **Active Chat Window & Persistence:** The exam runs entirely within your active chat session. You can pause your session, and when you return, you can **continue exactly where you left off**.
- **Timers:** If a time limit is set, the exam will display a countdown.
- **Final Scoring:** A summary screen tracks your progress, handles partial credit for multi-select questions, and displays your final score.

## Customization & Security Features
The Exam Application offers powerful settings to tailor the assessment:
1. **Anti-Cheat Mechanics:** When enabled via the builder, the system actively blocks right-clicking, text selection, and copying/pasting. It also automatically injects a hidden system instruction into the chat prompt, directing the AI to withhold direct answers to exam questions during the active session. Additionally, it monitors your browser tab activity; if you switch tabs during an active exam, you are automatically penalized 5 points.
2. **Media Embeds:** Exams can embed relevant images, tutorial videos, or audio clips directly above questions.
3. **Interface Localization (UI Config):** All buttons, labels, and feedback messages are driven by a centralized configuration file, allowing seamless translation into different languages.

## Accessibility Features
Learning tools must be inclusive. The Exam Application is built from the ground up for complete accessibility:
- **Screen Reader Support:** Every action—including the custom ARIA multi-select checkboxes—is clearly announced to assistive software.
- **Keyboard Navigation:** You can take the entire test without a mouse using standard keys (`Tab`, `Space`, `Enter`, and Arrow keys).
- **Quick Shortcuts:** 
  - `Alt+N` to instantly submit an answer and advance.
  - `Alt+T` to announce the remaining time on the exam.
  - `Alt+H` to access the global help menu at any time.
- **Heading Navigation & Media Bypass:** Use the `H` key to jump between the Exam Title (`H1`) and the Current Question (`H2`). If a video or audio file is embedded, you can quickly bypass it by pressing `H` again to jump straight to the hidden "Question Prompt" (`H3`) and "Answer Options" (`H3`) landmarks.
- **High Contrast Design:** The interface uses distinct visual indicators to ensure high readability for visually impaired users.

## Compatibility with Institutional AI Frameworks (e.g., Copilot)
Many academic and corporate institutions strictly mandate the use of integrated enterprise AI frameworks, such as Microsoft 365 Copilot, for data security reasons. However, it is fundamentally impossible to simply swap out the underlying AI engine of this application for a "headless Copilot agent" to achieve the same results and instantly comply with those policies. 

Systems like Copilot are fundamentally designed as user-facing assistants bound to specific applications (like Word, Excel, or Teams) within a graphical user interface. They do not operate natively as raw, headless system-level agents capable of parsing complex files and dynamically generating sophisticated JSON structures for external applications.

Currently, this application utilizes the Google Gemini API (via the Antigravity architecture) as its primary engine. However, its design is modular; the underlying AI can theoretically be swapped out for other models in the future, provided they support headless system-level integration.

## Fair Use and Institutional Accessibility
When utilizing this plugin in academic or professional environments, questions of policy, copyright, or data security may arise. It is important to understand the fundamental purpose of this application: it is an **assistive technology tool**.

By using this application to generate quizzes based on provided coursework, students with visual impairments or specific learning needs are not violating intellectual property or leaking proprietary secrets. The AI acts as an intermediary, processing information and adapting it from a static document into an interactive, screen-reader-friendly assessment. This empowers students to independently evaluate their knowledge in the format that works best for them, aligning perfectly with the core mission of any inclusive educational institution.

**Disclaimer & User Rights:**
Always enquire with your institution's administration or IT department before using this tool. An institution may rightfully deny your request if the materials contain highly sensitive data or proprietary secrets. However, if a document contains no sensitive information, you have a right to leverage assistive technologies to facilitate your studies. In the event an institution denies the use of this AI tool for accessibility purposes, they bear the responsibility of providing you with equally accessible alternative materials.

## Local Privacy Broker for Sensitive Content & OneDrive Sync Roots (`sensitive: true`)
To protect confidential coursework, internal training manuals, and PII-heavy documents placed inside `plugins/exam_application/content/` or any synced **Microsoft OneDrive** directory, this plugin uses the **Raugus Sensitive Vault & Local Brain Broker**:
- **Zero Raw Cloud Exposure & Automatic OneDrive Detection**:
  - The `plugins/exam_application/content/` directory and all automatically discovered OneDrive folders (`external.onedrive.*`) are flagged with `"sensitive": true` in `security/raugus_map.json`.
  - **Works Regardless of Folder Name**: `security/raugus_resolver.py` automatically detects any OneDrive folder—even if renamed—by checking Microsoft OneDrive's hidden sync-root GUID marker (`.849C9593-D756-4E56-8D6E-42412F2A707B`), `desktop.ini` (`OneDrive.exe`), and ancestor path segments across both Windows (`C:\Users\...`) and WSL (`/mnt/c/Users/...`) paths.
  - The `PreToolUse` interceptor (`.agents/raugus_hook.py`) blocks the Main Cloud Brain from directly reading, searching, or running shell commands on files in these folders.
- **Ephemeral Local Model (`Qwen2.5-1.5B-Instruct`) & Offline `.docx`/`.pdf` Parsing**:
  - `security/local_brain_broker.py` extracts text 100% offline from `.docx`, `.pdf`, `.md`, `.txt`, `.json`, and `.csv` study documents.
  - It wakes up a local CPU-optimized `Qwen2.5-1.5B-Instruct` (`Q4_K_M`) model via `llama.cpp`, loading into RAM only for the few seconds needed to summarize topics or generate practice questions, then immediately unloading back to **0 MB idle RAM**.
- **South African POPIA & Identifiable Information Scrubbing**:
  - All inputs and generated outputs pass through `offline_scrub_pii()` (deterministic regex + local Microsoft Presidio `spaCy` NLP) to redact **South African 13-digit ID numbers** (`<REDACTED_SA_ID>`), **labeled student/learner/passport/tax numbers** (`<REDACTED_ID_NUMBER>`), **SA `+27`/local cellphone and landline numbers** (`<REDACTED_PHONE>`), **bank/card numbers** (`<REDACTED_FINANCIAL_ID>`), **street addresses** (`<REDACTED_ADDRESS>`), **POPIA Section 26 medical/disability records** (`<REDACTED_MEDICAL_INFO>`), **person names** (`<PERSON>`), **emails**, **IPs**, and **API keys/secrets** before being handed to the Main Brain for `format_exam.py` validation and UI rendering.

