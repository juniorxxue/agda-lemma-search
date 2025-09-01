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
                                stripped_line.startswith(lemma_name + ' ') or  # Lemma name with space
                                (lemma_name in stripped_line and '=' in line) or  # Lemma name with equals
                                stripped_line.startswith(lemma_name + '(') or   # Lemma name with parentheses
                                stripped_line.startswith('...')):    # Proof omission dots
                                proof_started = True

                    # If proof started and we have a current lemma, save it
                    if proof_started and reading_lemma and current_lemma_lines:
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

                    # Start reading a new lemma if line looks like a type signature
                    if lemma_pattern.match(line) and not reading_lemma:
                        reading_lemma = True
                        start_line = i
                        current_lemma_lines = [line.rstrip()]
                    elif reading_lemma:
                        # Continue reading the signature if indented properly
                        if line.strip() and (line.startswith(' ') or line.startswith('\t')):
                            current_lemma_lines.append(line.rstrip())
                        elif line.strip():
                            # Non-indented line that's not empty - might be a new definition
                            if lemma_pattern.match(line):
                                # Save current lemma if it exists
                                if current_lemma_lines:
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
                                
                                # Start new lemma
                                reading_lemma = True
                                start_line = i
                                current_lemma_lines = [line.rstrip()]
                            else:
                                reading_lemma = False
                                current_lemma_lines = []

                # Handle any remaining lemma at end of file
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
    """Extract lemma name from the signature text"""
    lines = lemma_text.split('\n')
    first_line = lines[0].strip()
    
    # Match pattern: lemma_name : type
    match = re.match(r'^\s*([^\s:]+)\s*:', first_line)
    if match:
        return match.group(1)
    return None

def create_multi_codebase_search_html(output_dir, combined_data):
    """Create the enhanced HTML search interface using existing search.html as template"""
    
    # Use the existing search.html as template
    template_path = output_dir / "search.html"
    
    # Check if template exists
    if not template_path.exists():
        print(f"❌ Error: Template file {template_path} not found!")
        print("Please ensure your updated search.html file exists before running the build script.")
        return None
    
    # Read the existing search.html
    with open(template_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Generate codebase options
    codebase_options = []
    for nickname, info in combined_data['codebases'].items():
        codebase_options.append(f'<option value="{nickname}">{nickname} ({info["count"]} lemmas)</option>')
    
    options_html = '\n                    '.join(codebase_options)
    
    # Find and replace the codebase options in the existing HTML
    # Look for the select element with id="codebaseSelect"
    import re
    
    # Pattern to match the select element and its options
    select_pattern = r'(<select id="codebaseSelect">)(.*?)(</select>)'
    
    def replace_options(match):
        opening_tag = match.group(1)
        closing_tag = match.group(3)
        return f"{opening_tag}\n                    {options_html}\n                {closing_tag}"
    
    # Replace the options
    updated_html = re.sub(select_pattern, replace_options, html_content, flags=re.DOTALL)
    
    # Create a backup of the original file if it's different
    backup_path = output_dir / "search.html.backup"
    if html_content != updated_html:
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"   • Backup created: {backup_path}")
    
    # Write the updated HTML
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(updated_html)
    
    return template_path

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
    
    # Update HTML search interface using existing template
    html_path = create_multi_codebase_search_html(output_dir, combined_data)
    if html_path:
        print(f"\n🌐 Updated search interface: {html_path}")
    else:
        print(f"\n❌ Failed to update search interface")
        return 1
    
    # Print summary
    total_lemmas = sum(data['count'] for data in all_indices.values())
    print(f"\n📊 Summary:")
    print(f"   • {len(all_indices)} codebases indexed")
    print(f"   • {total_lemmas} total lemmas")
    print(f"   • Search interface updated with current codebases")
    
    print("\n🎉 Setup complete! Run 'python3 serve.py' to start searching.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
