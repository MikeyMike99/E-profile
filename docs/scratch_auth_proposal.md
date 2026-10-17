# Authentication Architecture

If we deploy DevCore as a standalone product on a new platform, you are absolutely right: users need a way to bring their own AI credentials, because we can't bundle your personal `.env` keys.

We have two main paths we can build:

### Option 1: The "Bring Your Own Key" (BYOK) Modal
- **How it works:** We build a "Settings ⚙️" button in the agent UI. When clicked, it pops up a modal asking the user to paste their `GEMINI_API_KEY`.
- **Backend:** The web interface saves the key securely in their browser (`localStorage`) and sends it over the WebSocket whenever they type a prompt. The backend then temporarily injects it into the environment just for that request.
- **Pros:** Takes 10 minutes to build. Zero infrastructure or cloud configuration needed.
- **Cons:** Users have to go to Google AI Studio, generate a key manually, and paste it.

### Option 2: True "Log In with Google" (OAuth 2.0)
- **How it works:** We build a "Sign in with Google" button. It redirects them to a Google consent screen where they grant permission.
- **Backend:** We intercept the OAuth Token and use it to authenticate API requests dynamically.
- **Pros:** Looks extremely professional. One-click frictionless onboarding.
- **Cons:** Requires setting up a Google Cloud Project, configuring OAuth Consent Screens, managing Client Secrets, and adding extensive OAuth routing logic to the Python backend.

