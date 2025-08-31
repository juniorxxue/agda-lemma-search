# Agda Lemma Search - Multi-codebase

A fast, intelligent search tool for Agda lemmas with fuzzy matching, smart ranking, and support for multiple codebases.

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
   This opens http://localhost:8002/search.html in your browser.

4. **Search lemmas:**
   - Select codebase from dropdown
   - Single term: `strengthen`
   - Multiple terms: `regular =⟹` (finds lemmas containing both)
   - First term gets higher weight in ranking

## Files

- **`config.json`** - Configuration with codebase paths and nicknames
- **`search.html`** - Multi-codebase web search interface
- **`serve.py`** - HTTP server to launch the search  
- **`build-index.py`** - Script to build indices for all codebases
- **`codebases.json`** - Generated metadata about available codebases
- **`lemma_index_*.json`** - Individual indices for each codebase

## Adding New Codebases

1. Edit `config.json` to add new entries:
   ```json
   {
     "codebases": [
       {
         "nickname": "New Project",
         "path": "/path/to/new/agda/project",
         "description": "Description of the project"
       }
     ]
   }
   ```

2. Rebuild indices:
   ```bash
   python3 build-index.py
   ```

3. Refresh the search interface - new codebase will appear in dropdown

## Features

- **Multi-codebase Support**: Switch between different Agda projects instantly
- **Smart Ranking**: Lemma names weighted higher than signatures
- **Multi-term Search**: Space-separated terms (all must match)
- **Position-based Scoring**: Earlier matches in names rank higher
- **Constructor Filtering**: Excludes data constructors and record fields
- **Real-time Search**: Instant results as you type
- **Unicode Support**: Handles Agda symbols (⊢, ∀, →, etc.)

## Search Tips

- Use the dropdown to switch between codebases
- Search "sub" to find substitution lemmas
- Search "regular =" to find regularity lemmas with equality
- First keyword gets higher priority in ranking
- Use specific terms for better results
