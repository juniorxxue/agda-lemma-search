#!/usr/bin/env python3
"""
Agda Lemma Search - Multi-codebase Index Builder
Extracts lemmas from multiple Agda codebases and creates searchable indices
"""
import os
import re
import json
import subprocess
import sys
from pathlib import Path

def load_config():
    """Load configuration with multiple codebases"""
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        print("❌ Error: config.json not found!")
        print("Please create config.json with your Agda codebase paths.")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    if 'codebases' not in config or not config['codebases']:
        print("❌ Error: No codebases configured in config.json")
        sys.exit(1)
    
    return config

def collect_lemma_signatures(root_dir):
    """Extract lemmas from Agda files"""
    lemma_pattern = re.compile(r'^\s*(\S+)\s*:\s*(.*)$')
    data_where_pattern = re.compile(r'^\s*data\b.*\bwhere\b')
    data_pattern = re.compile(r'^\s*data\s+\S+')
    record_pattern = re.compile(r'^\s*record\s+\S+')
    lemmas = []
    lemma_id = 0

    print(f"Scanning {root_dir} for .agda files...")
    
    for root, _, files in os.walk(root_dir):
        for filename in files:
            if filename.endswith(".agda"):
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, root_dir)
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except UnicodeDecodeError:
                    print(f"Warning: Could not read {file_path} (encoding issue)")
                    continue

                reading_lemma = False
                start_line = None
                current_lemma_lines = []
                data_block = False
                record_block = False
                block_indent_level = 0

                for i, line in enumerate(lines, start=1):
                    stripped_line = line.strip()
                    line_indent = len(line) - len(line.lstrip())

                    if stripped_line.startswith("--"):
                        continue

                    # Check for end of data/record blocks
                    if (data_block or record_block) and line_indent <= block_indent_level and stripped_line:
                        data_block = False
                        record_block = False
                        block_indent_level = 0

                    if not data_block and not record_block:
                        # Check for start of data blocks
                        if data_where_pattern.search(line) or data_pattern.search(line):
                            data_block = True
                            block_indent_level = line_indent
                            if reading_lemma and current_lemma_lines:
                                lemma_text = "\n".join(current_lemma_lines).strip()
                                lemma_name = extract_lemma_name(lemma_text)
                                if lemma_name:
                                    lemmas.append({
                                        "id": lemma_id,
                                        "name": lemma_name,
                                        "signature": lemma_text,
                                        "file": rel_path,
                                        "line": start_line
                                    })
                                    lemma_id += 1
                            reading_lemma = False
                            current_lemma_lines = []
                            continue
                        
                        # Check for record blocks
                        if record_pattern.search(line):
                            record_block = True
                            block_indent_level = line_indent
                            if reading_lemma and current_lemma_lines:
                                lemma_text = "\n".join(current_lemma_lines).strip()
                                lemma_name = extract_lemma_name(lemma_text)
                                if lemma_name:
                                    lemmas.append({
                                        "id": lemma_id,
                                        "name": lemma_name,
                                        "signature": lemma_text,
                                        "file": rel_path,
                                        "line": start_line
                                    })
                                    lemma_id += 1
                            reading_lemma = False
                            current_lemma_lines = []
                            continue
                    else:
                        # Inside data/record block - skip constructor/field definitions
                        if reading_lemma and current_lemma_lines:
                            lemma_text = "\n".join(current_lemma_lines).strip()
                            lemma_name = extract_lemma_name(lemma_text)
                            if lemma_name:
                                lemmas.append({
                                    "id": lemma_id,
                                    "name": lemma_name,
                                    "signature": lemma_text,
                                    "file": rel_path,
                                    "line": start_line
                                })
                                lemma_id += 1
                        reading_lemma = False
                        current_lemma_lines = []
                        continue

                    # Check for proof start patterns
                    proof_started = False
                    
                    # Lines with ' = ' mark the start of a proof
                    if " = " in line:
                        proof_started = True
                    
                    # Pattern matching and proof patterns 
                    elif reading_lemma and current_lemma_lines:
                        first_line = current_lemma_lines[0]
                        first_line_indent = len(first_line) - len(first_line.lstrip())
                        
                        # Extract lemma name for detection
                        lemma_name_match = re.match(r'^\s*(\S+)\s*:', first_line)
                        lemma_name = lemma_name_match.group(1) if lemma_name_match else ""
                        
                        # Check for proof patterns at lemma level (same indentation as lemma name)
                        if line_indent == first_line_indent:
                            if (stripped_line.startswith('(') or      # Pattern matching with parentheses  
                                ' with ' in line or                   # with clauses
                                stripped_line.startswith('where ') or # where clauses
                                stripped_line.startswith('...')):     # ellipsis patterns
                                proof_started = True
                            
                            # Check if line starts with lemma name followed by patterns (proof implementation)
                            elif lemma_name and stripped_line.startswith(lemma_name + ' '):
                                remaining = stripped_line[len(lemma_name):].strip()
                                if remaining.startswith('(') or ' with ' in remaining:
                                    proof_started = True
                        
                        # Also check for proof patterns that start immediately after type signature
                        # These often appear on lines that continue the signature but are actually proof
                        elif (stripped_line.startswith('(') and 
                              not stripped_line.endswith(':') and
                              not any('→' in l or '⟹' in l or ':' in l.split()[-1] if l.strip() else False 
                                     for l in current_lemma_lines[-3:] if l.strip())):
                            # This looks like pattern matching, not part of type signature
                            proof_started = True
                    
                    if proof_started:
                        if reading_lemma and current_lemma_lines:
                            lemma_text = "\n".join(current_lemma_lines).strip()
                            lemma_name = extract_lemma_name(lemma_text)
                            if lemma_name:
                                lemmas.append({
                                    "id": lemma_id,
                                    "name": lemma_name,
                                    "signature": lemma_text,
                                    "file": rel_path,
                                    "line": start_line
                                })
                                lemma_id += 1
                        reading_lemma = False
                        current_lemma_lines = []
                        continue

                    if reading_lemma:
                        if lemma_pattern.match(line):
                            # finalize old
                            lemma_text = "\n".join(current_lemma_lines).strip()
                            lemma_name = extract_lemma_name(lemma_text)
                            if lemma_name:
                                lemmas.append({
                                    "id": lemma_id,
                                    "name": lemma_name,
                                    "signature": lemma_text,
                                    "file": rel_path,
                                    "line": start_line
                                })
                                lemma_id += 1
                            # start new
                            reading_lemma = True
                            start_line = i
                            current_lemma_lines = [line.rstrip("\n")]
                        else:
                            current_lemma_lines.append(line.rstrip("\n"))
                    else:
                        if lemma_pattern.match(line):
                            reading_lemma = True
                            start_line = i
                            current_lemma_lines = [line.rstrip("\n")]

                if reading_lemma and current_lemma_lines:
                    lemma_text = "\n".join(current_lemma_lines).strip()
                    lemma_name = extract_lemma_name(lemma_text)
                    if lemma_name:
                        lemmas.append({
                            "id": lemma_id,
                            "name": lemma_name,
                            "signature": lemma_text,
                            "file": rel_path,
                            "line": start_line
                        })
                        lemma_id += 1

    return lemmas

def extract_lemma_name(lemma_text):
    """Extract the lemma name from the first line, filtering out data constructors"""
    lines = lemma_text.splitlines()
    if not lines:
        return ""
    first_line = lines[0]
    m = re.match(r'^\s*(\S+)\s*:\s*(.*)$', first_line)
    if m:
        name = m.group(1)
        
        # Filter out common data constructor patterns
        if name in ['_', 'l', 'm', 'n', 'k', 'j', 'regΓ']:
            return ""
        
        # Filter out names starting with parentheses (parsing artifacts)
        if name.startswith('('):
            return ""
            
        # Filter out elaboration constructors
        if name.startswith('ela-'):
            return ""
            
        # Filter out signatures that look like constructor arguments
        signature = m.group(2)
        if signature.strip().startswith('(') and 'regΓ' in signature:
            return ""
        
        return name
    return ""

def create_multi_codebase_search_html(output_dir, combined_data):
    """Create the enhanced HTML search interface with codebase selection"""
    
    # Generate codebase options
    codebase_options = []
    for nickname, info in combined_data['codebases'].items():
        codebase_options.append(f'<option value="{nickname}">{nickname} ({info["count"]} lemmas)</option>')
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agda Lemma Search - Multi-codebase</title>
    <style>
        * {{ box-sizing: border-box; }}
        
        body {{
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', monospace;
            margin: 0; padding: 20px;
            background-color: #1e1e1e; color: #d4d4d4; line-height: 1.4;
        }}
        
        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        h1 {{ color: #569cd6; margin-bottom: 30px; text-align: center; }}
        
        .codebase-selector {{
            display: flex; align-items: center; gap: 10px; margin-bottom: 20px;
            padding: 15px; background-color: #252526; border-radius: 8px; border: 1px solid #404040;
        }}
        
        .codebase-selector label {{ color: #569cd6; font-weight: bold; }}
        
        #codebaseSelect {{
            flex: 1; padding: 8px 12px; font-size: 14px;
            border: 1px solid #404040; border-radius: 4px;
            background-color: #2d2d2d; color: #d4d4d4; font-family: inherit;
        }}
        
        .codebase-info {{ color: #808080; font-size: 14px; margin-top: 5px; }}
        
        .search-container {{
            position: sticky; top: 0; background-color: #1e1e1e; z-index: 100;
            padding: 20px 0; margin-bottom: 20px; border-bottom: 1px solid #404040;
        }}
        
        #searchInput {{
            width: 100%; padding: 12px 16px; font-size: 16px;
            border: 2px solid #404040; border-radius: 8px;
            background-color: #2d2d2d; color: #d4d4d4; font-family: inherit;
            outline: none; transition: border-color 0.2s;
        }}
        
        #searchInput:focus {{ border-color: #569cd6; }}
        
        .stats {{ margin: 10px 0; color: #808080; font-size: 14px; }}
        
        .results {{ display: grid; gap: 16px; }}
        
        .lemma-card {{
            background-color: #252526; border: 1px solid #404040; border-radius: 8px;
            padding: 16px; transition: border-color 0.2s, box-shadow 0.2s;
        }}
        
        .lemma-card:hover {{
            border-color: #569cd6; box-shadow: 0 2px 8px rgba(86, 156, 214, 0.1);
        }}
        
        .lemma-name {{ color: #dcdcaa; font-weight: bold; font-size: 18px; margin-bottom: 8px; }}
        
        .lemma-signature {{
            color: #d4d4d4; white-space: pre-wrap; margin-bottom: 12px;
            background-color: #1e1e1e; padding: 12px; border-radius: 4px;
            border-left: 3px solid #569cd6;
        }}
        
        .lemma-location {{ color: #808080; font-size: 14px; }}
        
        .no-results {{ text-align: center; color: #808080; font-style: italic; margin-top: 40px; }}
        .loading {{ text-align: center; color: #569cd6; margin-top: 40px; }}
        
        .highlight {{ background-color: #264f78; color: #fff; padding: 1px 2px; border-radius: 2px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Agda Lemma Search</h1>
        
        <div class="codebase-selector">
            <label for="codebaseSelect">Codebase:</label>
            <select id="codebaseSelect">
                {' '.join(codebase_options)}
            </select>
            <div class="codebase-info" id="codebaseInfo"></div>
        </div>
        
        <div class="search-container">
            <input type="text" id="searchInput" 
                   placeholder="Search lemmas... (use spaces for multiple terms, e.g., 'regular =⟹')"
                   autocomplete="off">
            <div class="stats" id="stats">Loading codebases...</div>
        </div>
        
        <div class="results" id="results">
            <div class="loading">Loading lemma indices...</div>
        </div>
    </div>

    <script>
        let currentLemmas = [];
        let codebaseData = {{}};
        let currentCodebase = null;
        
        async function loadCodebaseMetadata() {{
            try {{
                const response = await fetch('codebases.json');
                const data = await response.json();
                codebaseData = data.codebases;
                currentCodebase = data.default_codebase;
                
                // Set default selection
                document.getElementById('codebaseSelect').value = currentCodebase;
                
                // Load the default codebase
                await loadCodebase(currentCodebase);
                
            }} catch (error) {{
                console.error('Error loading codebase metadata:', error);
                document.getElementById('results').innerHTML = 
                    '<div class="no-results">Error loading codebase configuration.</div>';
            }}
        }}
        
        async function loadCodebase(nickname) {{
            try {{
                const info = codebaseData[nickname];
                if (!info) throw new Error(`Codebase '${{nickname}}' not found`);
                
                document.getElementById('stats').textContent = 'Loading...';
                document.getElementById('results').innerHTML = '<div class="loading">Loading lemmas...</div>';
                
                const response = await fetch(info.filename);
                if (!response.ok) throw new Error(`Failed to load ${{info.filename}}`);
                
                currentLemmas = await response.json();
                currentCodebase = nickname;
                
                // Update UI
                document.getElementById('codebaseInfo').textContent = info.description;
                document.getElementById('stats').textContent = `${{currentLemmas.length}} lemmas ready`;
                displayResults(currentLemmas);
                
                // Clear search when switching codebases
                document.getElementById('searchInput').value = '';
                
            }} catch (error) {{
                console.error('Error loading codebase:', error);
                document.getElementById('results').innerHTML = 
                    `<div class="no-results">Error loading codebase: ${{error.message}}</div>`;
            }}
        }}
        
        let searchTimeout;
        function performSearch() {{
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {{
                const query = document.getElementById('searchInput').value.trim();
                
                if (!query) {{
                    displayResults(currentLemmas);
                    document.getElementById('stats').textContent = `${{currentLemmas.length}} lemmas ready`;
                    return;
                }}
                
                // Split query into individual terms for fuzzy search
                const terms = query.toLowerCase().split(/\\s+/).filter(term => term.length > 0);
                
                if (terms.length === 0) {{
                    displayResults(currentLemmas);
                    return;
                }}
                
                // Score each lemma based on how well it matches
                const scoredResults = currentLemmas.map(lemma => {{
                    let score = 0;
                    const nameLower = lemma.name.toLowerCase();
                    const sigLower = lemma.signature.toLowerCase();
                    
                    // Check if ALL terms are matched first (required)
                    const allTermsMatched = terms.every(term => 
                        nameLower.includes(term) || sigLower.includes(term) || lemma.file.toLowerCase().includes(term)
                    );
                    
                    if (!allTermsMatched) return {{ lemma, score: 0 }};
                    
                    for (let i = 0; i < terms.length; i++) {{
                        const term = terms[i];
                        const isFirstTerm = i === 0;
                        const termWeight = isFirstTerm ? 3 : 1; // First term gets triple weight
                        
                        // Name matches (heavily weighted) - prioritize exact and prefix matches
                        if (nameLower.includes(term)) {{
                            if (nameLower === term) score += 200 * termWeight; // Exact name match
                            else if (nameLower.startsWith(term)) score += 100 * termWeight; // Name starts with term
                            else if (nameLower.indexOf(term) === 0) score += 80 * termWeight; // Name begins with term
                            else {{
                                // Check position in name - earlier is better
                                const position = nameLower.indexOf(term);
                                const positionBonus = Math.max(0, 20 - position); // Earlier = higher bonus
                                score += (15 + positionBonus) * termWeight; // Name contains term
                            }}
                        }}
                        
                        // Signature matches (lower weight)
                        if (sigLower.includes(term)) {{
                            score += 5 * termWeight;
                        }}
                        
                        // File path matches (lowest weight)
                        if (lemma.file.toLowerCase().includes(term)) {{
                            score += 1 * termWeight;
                        }}
                    }}
                    
                    // Bonus for matching all terms in name (strong preference)
                    const allTermsInName = terms.every(term => nameLower.includes(term));
                    const allTermsInSig = terms.every(term => sigLower.includes(term));
                    
                    if (allTermsInName) score += 50; // Strong bonus for all terms in name
                    else if (allTermsInSig) score += 20; // Medium bonus for all terms in signature
                    
                    return {{ lemma, score }};
                }}).filter(result => result.score > 0);
                
                // Sort by score (highest first)
                scoredResults.sort((a, b) => b.score - a.score);
                const resultLemmas = scoredResults.map(result => result.lemma);
                
                displayResults(resultLemmas, query);
                document.getElementById('stats').textContent = 
                    `${{resultLemmas.length}} of ${{currentLemmas.length}} lemmas match "${{terms.join(' ')}}"`;
                
            }}, 150);
        }}
        
        function displayResults(results, query = '') {{
            const resultsContainer = document.getElementById('results');
            
            if (results.length === 0) {{
                resultsContainer.innerHTML = '<div class="no-results">No lemmas found</div>';
                return;
            }}
            
            resultsContainer.innerHTML = results.slice(0, 50).map(lemma => {{
                const highlightedName = highlightText(lemma.name, query);
                const highlightedSignature = highlightText(lemma.signature, query);
                
                return `
                    <div class="lemma-card">
                        <div class="lemma-name">${{highlightedName}}</div>
                        <div class="lemma-signature">${{highlightedSignature}}</div>
                        <div class="lemma-location">📁 ${{lemma.file}}:${{lemma.line}}</div>
                    </div>
                `;
            }}).join('') + (results.length > 50 ? `<div class="stats">Showing first 50 of ${{results.length}} results</div>` : '');
        }}
        
        function highlightText(text, query) {{
            if (!query) return escapeHtml(text);
            const escapedText = escapeHtml(text);
            const words = query.toLowerCase().split(/\\s+/).filter(w => w.length > 0);
            let highlighted = escapedText;
            words.forEach(word => {{
                const regex = new RegExp(`(${{escapeRegExp(word)}})`, 'gi');
                highlighted = highlighted.replace(regex, '<span class="highlight">$1</span>');
            }});
            return highlighted;
        }}
        
        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}
        
        function escapeRegExp(string) {{
            return string.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
        }}
        
        // Event listeners
        document.getElementById('searchInput').addEventListener('input', performSearch);
        document.getElementById('searchInput').addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') {{
                this.value = ''; performSearch(); this.blur();
            }}
        }});
        
        document.getElementById('codebaseSelect').addEventListener('change', function(e) {{
            loadCodebase(e.target.value);
        }});
        
        // Initialize
        loadCodebaseMetadata();
    </script>
</body>
</html>'''
    
    html_path = output_dir / "search.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    return html_path
    """Create the HTML search interface"""
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agda Lemma Search</title>
    <script src="https://unpkg.com/lunr/lunr.js"></script>
    <style>
        * { box-sizing: border-box; }
        
        body {
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', monospace;
            margin: 0; padding: 20px;
            background-color: #1e1e1e; color: #d4d4d4; line-height: 1.4;
        }
        
        .container { max-width: 1200px; margin: 0 auto; }
        
        h1 { color: #569cd6; margin-bottom: 30px; text-align: center; }
        
        .search-container {
            position: sticky; top: 0; background-color: #1e1e1e; z-index: 100;
            padding: 20px 0; margin-bottom: 20px; border-bottom: 1px solid #404040;
        }
        
        #searchInput {
            width: 100%; padding: 12px 16px; font-size: 16px;
            border: 2px solid #404040; border-radius: 8px;
            background-color: #2d2d2d; color: #d4d4d4; font-family: inherit;
            outline: none; transition: border-color 0.2s;
        }
        
        #searchInput:focus { border-color: #569cd6; }
        
        .stats { margin: 10px 0; color: #808080; font-size: 14px; }
        
        .results { display: grid; gap: 16px; }
        
        .lemma-card {
            background-color: #252526; border: 1px solid #404040; border-radius: 8px;
            padding: 16px; transition: border-color 0.2s, box-shadow 0.2s;
        }
        
        .lemma-card:hover {
            border-color: #569cd6; box-shadow: 0 2px 8px rgba(86, 156, 214, 0.1);
        }
        
        .lemma-name { color: #dcdcaa; font-weight: bold; font-size: 18px; margin-bottom: 8px; }
        
        .lemma-signature {
            color: #d4d4d4; white-space: pre-wrap; margin-bottom: 12px;
            background-color: #1e1e1e; padding: 12px; border-radius: 4px;
            border-left: 3px solid #569cd6;
        }
        
        .lemma-location { color: #808080; font-size: 14px; }
        .lemma-location a { color: #4ec9b0; text-decoration: none; }
        .lemma-location a:hover { text-decoration: underline; }
        
        .no-results { text-align: center; color: #808080; font-style: italic; margin-top: 40px; }
        .loading { text-align: center; color: #569cd6; margin-top: 40px; }
        
        .highlight { background-color: #264f78; color: #fff; padding: 1px 2px; border-radius: 2px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Agda Lemma Search</h1>
        
        <div class="search-container">
            <input type="text" id="searchInput" 
                   placeholder="Search lemmas by name or signature... (fuzzy search enabled)"
                   autocomplete="off">
            <div class="stats" id="stats">Loading lemmas...</div>
        </div>
        
        <div class="results" id="results">
            <div class="loading">Loading lemma index...</div>
        </div>
    </div>

    <script>
        let lemmas = [];
        let searchIndex = null;
        
        async function loadLemmas() {
            try {
                const response = await fetch('lemma_index.json');
                lemmas = await response.json();
                
                searchIndex = lunr(function () {
                    this.ref('id');
                    this.field('name', { boost: 10 });
                    this.field('signature', { boost: 5 });
                    this.field('file');
                    
                    lemmas.forEach(lemma => this.add(lemma));
                });
                
                document.getElementById('stats').textContent = `${lemmas.length} lemmas indexed`;
                displayResults(lemmas);
                
            } catch (error) {
                document.getElementById('results').innerHTML = 
                    '<div class="no-results">Error loading lemma index. Make sure lemma_index.json exists.</div>';
                console.error('Error loading lemmas:', error);
            }
        }
        
        let searchTimeout;
        function performSearch() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                const query = document.getElementById('searchInput').value.trim();
                
                if (!query) {
                    displayResults(lemmas);
                    document.getElementById('stats').textContent = `${lemmas.length} lemmas indexed`;
                    return;
                }
                
                const searchResults = searchIndex.search(query + '~1');
                const resultLemmas = searchResults.map(result => 
                    lemmas.find(lemma => lemma.id === parseInt(result.ref))
                );
                
                displayResults(resultLemmas, query);
                document.getElementById('stats').textContent = 
                    `${resultLemmas.length} of ${lemmas.length} lemmas match "${query}"`;
                
            }, 150);
        }
        
        function displayResults(results, query = '') {
            const resultsContainer = document.getElementById('results');
            
            if (results.length === 0) {
                resultsContainer.innerHTML = '<div class="no-results">No lemmas found</div>';
                return;
            }
            
            resultsContainer.innerHTML = results.map(lemma => {
                const highlightedName = highlightText(lemma.name, query);
                const highlightedSignature = highlightText(lemma.signature, query);
                
                return `
                    <div class="lemma-card">
                        <div class="lemma-name">${highlightedName}</div>
                        <div class="lemma-signature">${highlightedSignature}</div>
                        <div class="lemma-location">
                            📁 ${lemma.file}:${lemma.line}
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function highlightText(text, query) {
            if (!query) return escapeHtml(text);
            
            const escapedText = escapeHtml(text);
            const words = query.toLowerCase().split(/\\s+/).filter(w => w.length > 0);
            
            let highlighted = escapedText;
            words.forEach(word => {
                const regex = new RegExp(`(${escapeRegExp(word)})`, 'gi');
                highlighted = highlighted.replace(regex, '<span class="highlight">$1</span>');
            });
            
            return highlighted;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function escapeRegExp(string) {
            return string.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
        }
        
        document.getElementById('searchInput').addEventListener('input', performSearch);
        document.getElementById('searchInput').addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                this.value = '';
                performSearch();
                this.blur();
            }
        });
        
        loadLemmas();
    </script>
</body>
</html>'''
    
    html_path = output_dir / "agda_lemma_search.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    return html_path

def main():
    print("🔍 Agda Lemma Search - Multi-codebase Builder")
    print("=" * 50)
    
    # Load configuration
    config = load_config()
    codebases = config['codebases']
    
    print(f"📚 Found {len(codebases)} codebase(s) to index:")
    for cb in codebases:
        print(f"   • {cb['nickname']}: {cb['path']}")
    
    # Set up output directory
    script_dir = Path(__file__).parent
    output_dir = script_dir
    
    # Build indices for all codebases
    all_indices = {}
    
    for codebase in codebases:
        nickname = codebase['nickname']
        path = codebase['path']
        description = codebase.get('description', '')
        
        print(f"\n🔍 Processing '{nickname}'...")
        print(f"📁 Path: {path}")
        
        if not os.path.exists(path):
            print(f"❌ Error: Directory {path} does not exist! Skipping.")
            continue
        
        # Extract lemmas for this codebase
        lemmas = collect_lemma_signatures(path)
        print(f"✅ Found {len(lemmas)} lemmas")
        
        if len(lemmas) == 0:
            print(f"⚠️  No lemmas found in {nickname}")
            continue
        
        # Store index for this codebase
        all_indices[nickname] = {
            'lemmas': lemmas,
            'description': description,
            'path': path,
            'count': len(lemmas)
        }
    
    if not all_indices:
        print("❌ No lemmas found in any codebase!")
        return 1
    
    # Save individual indices and create combined data
    print(f"\n💾 Saving indices...")
    
    # Save combined index with codebase metadata
    combined_data = {
        'codebases': {},
        'default_codebase': list(all_indices.keys())[0]  # First codebase as default
    }
    
    for nickname, data in all_indices.items():
        # Save individual index
        individual_path = output_dir / f"lemma_index_{nickname.lower().replace(' ', '_')}.json"
        with open(individual_path, 'w', encoding='utf-8') as f:
            json.dump(data['lemmas'], f, indent=2, ensure_ascii=False)
        print(f"   • {nickname}: {individual_path} ({data['count']} lemmas)")
        
        # Add to combined data
        combined_data['codebases'][nickname] = {
            'description': data['description'],
            'path': data['path'],
            'count': data['count'],
            'filename': individual_path.name
        }
    
    # Save combined metadata
    metadata_path = output_dir / "codebases.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)
    print(f"   • Metadata: {metadata_path}")
    
    # Create enhanced HTML search interface
    html_path = create_multi_codebase_search_html(output_dir, combined_data)
    print(f"\n🌐 Created search interface: {html_path}")
    
    # Print summary
    total_lemmas = sum(data['count'] for data in all_indices.values())
    print(f"\n📊 Summary:")
    print(f"   • {len(all_indices)} codebases indexed")
    print(f"   • {total_lemmas} total lemmas")
    print(f"   • Search interface ready")
    
    print("\\n🎉 Setup complete! Run 'python3 serve.py' to start searching.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
