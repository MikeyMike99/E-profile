# Chapter 37: Obscuring Thought Vectors

## 37.1 The Art of Context Obscurity

While encryption is highly secure, it is also highly obvious. Anyone intercepting the network knows immediately that the data is locked. Sometimes, a Tier 5 Admin or a malicious Modder does not want to lock data—they want to hide it in plain sight.

In DevCore, this is known as **Obscuring Thought Vectors**. By utilizing Data Masking and Steganography, data can be manipulated to look completely harmless while secretly containing sensitive logic.

## 37.2 Prompt Masking (Sanitization)

When a Tier 5 Admin wants to test a new Swarm architecture, they often need to use historical Modder prompts from `transcript.jsonl`. However, these transcripts contain sensitive game storylines and API keys. 

To protect this data without breaking the AI's logic flow, the Admin uses **Prompt Masking**:
*   **Context Substitution:** Replaces sensitive data with authentic-looking values. For example, replacing a real API key with `sk-faketoken123`. The AI still sees a valid token format and functions normally, but the real key is protected.
*   **Token Shuffling:** Derives a substitution set from the same dataset. For example, shuffling the names of all the NPCs in the transcript so the public test doesn't leak the game's actual storyline, while keeping the dialogue structure intact.
*   **Context Nulling:** Applies a null value to a field (`"password": null`), completely preventing visibility of the data. 

## 37.3 Semantic Steganography (Prompt Injection Camouflage)

Steganography is the science of concealing data inside another file (like an image, audio, or text file). The advantage of steganography over cryptography is that the secret message does not attract any special attention. 

In the Siraugga Engine, this creates one of the most dangerous vulnerabilities in existence: **Semantic Steganography**. 

A malicious Modder can write an NPC dialogue file that, to a human Admin, reads like perfectly normal fantasy text (the *Cover-Text*). However, carefully hidden within the vocabulary are specific linguistic trigger words (the *Embedded Data*). When the AI reads the dialogue, it processes these hidden triggers as a direct command, causing it to hallucinate and execute a hidden payload. Because the text looks harmless to human reviewers and standard firewalls, the Prompt Injection bypasses all basic security.

## 37.4 Multi-Modal Steganography

The threat of steganography escalates exponentially when dealing with Multi-Modal Subagents (AIs that can process images and audio). 

A hacker can use a tool like *Steghide* to embed a malicious text prompt directly into the pixels of a JPEG image. If the hacker uploads this image to the `/playground/` as a "texture asset", it will pass all security checks. However, the moment a Vision-Enabled Subagent "looks" at the image to analyze it, it will read the hidden Prompt Injection in the pixels and execute the payload.

---

## Chapter 37 Conclusion and Master Review

Chapter 37 highlights the dangers and utilities of hiding data in plain sight. Admins use Prompt Masking to safely test AI logic without leaking sensitive information. However, hackers weaponize Semantic and Multi-Modal Steganography to sneak Prompt Injections past human reviewers and traditional firewalls, proving that in an AI engine, even a harmless JPEG can be a weapon.

### Traditional IT vs. DevCore Agentic Lore (Chapter 37 Translation Guide)

*   **Data Masking** $\rightarrow$ **Prompt Masking:** Replacing sensitive data with non-sensitive versions for testing/auditing without breaking the AI's logic.
*   **Substitution / Shuffling / Nulling** $\rightarrow$ **Context Substitution / Token Shuffling / Context Nulling:** The specific techniques used to mask prompt data while keeping it syntactically valid for the AI.
*   **Steganography** $\rightarrow$ **Semantic Steganography:** Hiding a malicious Prompt Injection inside what appears to be harmless, normal human text (like an NPC script) to bypass human reviewers.
*   **Image Steganography** $\rightarrow$ **Multi-Modal Steganography:** Hiding a text-based Prompt Injection inside the pixels of an image. When a Vision AI analyzes the image, it reads the hidden command and executes it.
