# Pygame Screen Reader Chunk Reader Source Evidence

## 1. Architectural Role & File Location
This document records source code evidence from `docs/manifesto_reader.py`. Engineered during the 24-hour documentation sprint, this custom Pygame tool bypassed crushed IDEs and memory-locked screen readers to read a 317,000-line monolithic markdown file in 100-line chunks with synchronized speech timing.

---

## 2. 100-Line Chunk Loading Evidence
Rather than buffering tens of megabytes into memory, `manifesto_reader.py` streams strict 100-line slices:

```python
# docs/manifesto_reader.py: Lines 10-27
FILE_PATH = "DEVELOPERS_MANIFESTO.md"
CHUNK_SIZE = 100  # Load 100 lines at a time to prevent memory/lag issues

def load_chunk(filepath, start_line, chunk_size):
    """Loads a specific chunk of lines from the massive file."""
    lines = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i >= start_line and i < start_line + chunk_size:
                    clean_line = line.strip()
                    if clean_line:
                        lines.append((i, clean_line))
                if i >= start_line + chunk_size:
                    break
    except Exception as e:
        return [(0, f"Error loading file: {e}")]
    return lines
```

---

## 3. Screen Reader WPM Reading Time Estimation Evidence
To enable automatic scrolling that matches the rapid speech of blind developers, the script dynamically calculates delay based on Words-Per-Minute (WPM):

```python
# docs/manifesto_reader.py: WPM latency calculation
def estimate_reading_time(text, wpm):
    """Estimates how long a screen reader takes to read a line, tailored to fast screen reader speeds."""
    words = max(1, len(text.split())) # At least 1 word
    # Calculate exact seconds based on the current Words Per Minute
    seconds_per_word = 60.0 / wpm
    return words * seconds_per_word
```

---

## 4. Pygame Event Loop & Fast Search Evidence
The reader uses Pygame to trap keystrokes without IDE interference and integrates a Tkinter dialog for instant string searches:

```python
# docs/manifesto_reader.py: Pygame event handling & search
def search_file(filepath, query):
    """Searches the entire file for the query and returns the absolute line index."""
    query = query.lower()
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if query in line.lower():
                    return i, line.strip()
    except Exception as e:
        print(e)
    return -1, None

# Inside the main Pygame event loop:
if event.key == pygame.K_f and (event.mod & pygame.KMOD_CTRL):
    # Open minimalist search dialog without crashing GUI
    root = tk.Tk()
    root.withdraw()
    query = simpledialog.askstring("Search", "Enter search text:")
    root.destroy()
    if query:
        line_idx, found_text = search_file(FILE_PATH, query)
        if line_idx != -1:
            current_line = line_idx
            lines = load_chunk(FILE_PATH, current_line, CHUNK_SIZE)
            screenreader_speak(f"Found on line {line_idx}: {found_text}")
```

---

## 5. Why Order Matters in Chunk Reading
1. **Withdraw Tkinter Root Before Dialog**: Hiding the main Tkinter root window (`root.withdraw()`) prevents an empty window from lingering and stealing OS focus from Pygame.
2. **Read Line Slices Sequentially**: Slicing the file by enumerating lines up to `start_line + CHUNK_SIZE` avoids loading subsequent lines into memory.
3. **Speak New Line Before Incrementing Index**: Triggering `screenreader_speak()` immediately upon index change ensures auditory output synchronizes with visual display coordinates.

---

## 6. Beginner Coder Q&A
**Q: Why use Pygame to read text?**  
A: Pygame provides raw, low-level keyboard event handling that ignores desktop shortcuts, allowing the developer to build custom auto-read controls without IDE conflicts.

**Q: What does `errors='ignore'` do in `open()`?**  
A: If the file contains non-UTF-8 characters or binary artifacts from scrapers, Python ignores the bad bytes instead of throwing a fatal `UnicodeDecodeError`.

**Q: How does `root.destroy()` prevent memory leaks?**  
A: It explicitly destroys the Tkinter search dialog process resources once the user presses Enter, returning complete control to Pygame.
