# Agda Lemma Search

A simple agda tool to search your lemmas.

## Disclamer

* It's all AI-written, please do not trust the code too much.

* The parsing logic is very ad-hoc, based on heuristics of my Agda coding style.

* Unicode picker is only tailored by my own habit, will make it smarter later.

* It's very useful for my case, I have a big agda project to work on with 1000+ lemmas I cannot remember all their names and shapes.

## Quick Start

1. **Configure your codebases:**
   Edit `config.json` to add your Agda project paths:
   ```json
   {
     "codebases": [
       {
         "nickname": "Main Project",
         "path": "/path/to/your/agda/files",
         "description": "Main development"
       },
       {
         "nickname": "Experiments",
         "path": "/path/to/experimental/agda",
         "description": "Experimental features"
       }
     ]
   }
   ```

2. **Build indices for all codebases:**
   ```bash
   python3 build-index.py
   ```

3. **Launch the search interface:**
   ```bash
   python3 serve.py
   ```
   This opens http://localhost:8002/index.html in your browser.

4. **Search lemmas:**
   - Select codebase from dropdown
   - Single term: `strengthen`
   - Multiple terms: `regular ⟹` (finds lemmas containing both)
   - First term gets higher weight in ranking

## Files

- **`config.json`** - Configuration with codebase paths and nicknames
- **`index.html`** - Multi-codebase web search interface
- **`serve.py`** - HTTP server to launch the search  
- **`build-index.py`** - Script to build indices for all codebases
- **`codebases.json`** - Generated metadata about available codebases
- **`lemma_index_*.json`** - Individual indices for each codebase