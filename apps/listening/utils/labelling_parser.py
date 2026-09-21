"""
Labelling Parser - Universal parser for "Label the plan/map/diagram" questions
Works for both Reading and Listening modules
Similar to matching_headings with drag-drop functionality
"""

import re
from html import unescape
from bs4 import BeautifulSoup
import json
import logging

logger = logging.getLogger(__name__)


class LabellingParser:
    """Parser for labelling questions (Label the plan/map/diagram)"""
    
    def __init__(self, question_type='matching_headings'):
        self.question_type = question_type
    
    def log(self, message):
        """Helper for consistent logging"""
        logger.info(f"[LABELLING_PARSER] {message}")
        print(f"[LABELLING_PARSER] {message}")
    
    def detect_labelling(self, html_content):
        """
        UNIVERSAL DETECTION for matching_headings and labelling questions
        Handles:
        - List of Headings (with roman numerals: i, ii, iii, etc.)
        - Label the plan/map/diagram (with letters: A, B, C, etc.)
        - Questions that match paragraphs to headings
        - Content with images before/after the text
        """
        content_lower = html_content.lower()
        
        # Remove images to analyze text content
        soup = BeautifulSoup(html_content, 'html.parser')
        for img in soup.find_all('img'):
            img.decompose()
        text_content = str(soup)
        text_lower = text_content.lower()
        
        # Check for labelling instructions
        has_label_instruction = any([
            'label the plan' in text_lower,
            'label the map' in text_lower,
            'label the diagram' in text_lower,
            'label the' in text_lower and ('plan' in text_lower or 'map' in text_lower or 'diagram' in text_lower)
        ])
        
        # Check for "List of Headings" or matching headings patterns
        has_matching_headings = any([
            'list of headings' in text_lower,
            'list of heading' in text_lower,
            'choose the correct heading' in text_lower,
            'match the heading' in text_lower,
            'paragraph' in text_lower and 'heading' in text_lower
        ])
        
        # Check for letter options (A, B, C, etc.)
        has_letter_options = bool(re.search(r'<strong[^>]*>\s*[A-Z]\s*</strong>', text_content))
        
        # Check for roman numerals (i, ii, iii, iv, v, vi, vii, viii, ix, x, etc.)
        roman_pattern = r'<strong[^>]*>\s*(i{1,3}|iv|v|vi{1,3}|viii?|ix|xi{0,3})\s*</strong>'
        has_roman_options = bool(re.search(roman_pattern, text_content, re.IGNORECASE))
        
        # Check for numbered questions
        has_numbered_questions = bool(re.search(r'<strong[^>]*>\s*\d+\s*</strong>', text_content))
        
        # Check for paragraph references (Paragraph A, Paragraph B, etc.)
        has_paragraph_refs = bool(re.search(r'paragraph\s+[A-Z]', text_lower, re.IGNORECASE))
        
        # Check for drag-drop components in data attributes
        has_data_options = 'data-options' in text_content or 'drag-drop' in text_content
        
        # DEBUG: Log what we found
        self.log(f"🔍 UNIVERSAL LABELLING DETECTION:")
        self.log(f"  - has_label_instruction: {has_label_instruction}")
        self.log(f"  - has_matching_headings: {has_matching_headings}")
        self.log(f"  - has_letter_options: {has_letter_options}")
        self.log(f"  - has_roman_options: {has_roman_options}")
        self.log(f"  - has_numbered_questions: {has_numbered_questions}")
        self.log(f"  - has_paragraph_refs: {has_paragraph_refs}")
        self.log(f"  - has_data_options: {has_data_options}")
        self.log(f"  - Content length: {len(html_content)}")
        
        # PRIORITY 1: Matching Headings pattern (roman numerals + numbered questions + paragraph refs)
        if has_matching_headings and has_roman_options and (has_numbered_questions or has_paragraph_refs):
            self.log(f"✅ DETECTED as MATCHING HEADINGS (List of Headings)")
            return True
        
        # PRIORITY 2: Roman numerals + numbered questions (even without explicit "List of Headings")
        if has_roman_options and has_numbered_questions:
            self.log(f"✅ DETECTED via roman numerals + numbered questions")
            return True
        
        # PRIORITY 3: Letters (A, B, C) + numbered questions (labelling questions)
        if has_letter_options and has_numbered_questions:
            self.log(f"✅ DETECTED via letters (A, B, C) + numbered questions")
            return True
        
        # PRIORITY 4: Traditional labelling (label instruction + options + questions)
        if has_label_instruction and (has_letter_options or has_roman_options) and has_numbered_questions:
            self.log(f"✅ DETECTED via label instruction + options + questions")
            return True
        
        # PRIORITY 5: Already has data-options (already processed)
        if has_data_options:
            self.log(f"⚠️ Already processed (has data-options)")
            return False
        
        self.log(f"❌ NOT DETECTED as labelling/matching_headings")
        return False
    
    def extract_options(self, html_content):
        """
        UNIVERSAL OPTIONS EXTRACTOR for matching_headings and labelling questions
        FIXED VERSION: Properly extracts full label text from each <p> tag
        Handles:
        - Roman numerals: i, ii, iii, iv, v, vi, vii, viii, ix, x, xi, etc.
        - Letters: A, B, C, D, E, F, etc.
        Format: <p><strong>i</strong>&nbsp;&nbsp; Full label text here</p>
        Returns: list of dicts with {'value': 'i', 'label': 'Full label text here'}
        """
        # Remove images first to avoid confusion
        soup = BeautifulSoup(html_content, 'html.parser')
        for img in soup.find_all('img'):
            img.decompose()
        
        options = []
        seen_values = set()
        
        # Enhanced roman numeral pattern (supports i through xx)
        roman_pattern = r'^(i{1,3}|iv|v|vi{1,3}|viii?|ix|x|xi{1,3}|xii|xiii|xiv|xv|xvi{1,3}|xviii?|xix|xx)$'
        
        # Process each paragraph separately
        for p in soup.find_all('p'):
            # Get paragraph text to check if it's a question
            p_text = p.get_text(strip=True)
            
            # Skip question paragraphs (start with number like "14 Paragraph A")
            if re.search(r'^\d+\s', p_text):
                continue
            
            # Skip instruction paragraphs
            if any(keyword in p_text.lower() for keyword in [
                'choose the correct',
                'write the correct',
                'reading passage',
                'in boxes',
                'list of headings'
            ]):
                # But if it's ONLY "List of Headings", don't skip
                if p_text.strip().lower() != 'list of headings':
                    continue
            
            # Find the first strong tag
            strong = p.find('strong')
            if not strong:
                continue
            
            strong_text = strong.get_text(strip=True)
            
            # Check if it's a letter (A, B, C) or roman numeral (i, ii, iii)
            is_letter = len(strong_text) == 1 and strong_text.isalpha() and strong_text.isupper()
            is_roman = bool(re.match(roman_pattern, strong_text.lower(), re.IGNORECASE))
            
            if not (is_letter or is_roman):
                continue
            
            # Get the option value
            option_value = strong_text if is_letter else strong_text.lower()
            
            # Skip if already seen
            if option_value.lower() in seen_values:
                continue
            
            # Extract label: get full paragraph text and remove the option value
            full_text = p.get_text(separator=' ', strip=True)
            
            # Remove the option value from the start
            label = full_text
            if label.startswith(strong_text):
                label = label[len(strong_text):].strip()
            
            # Clean up &nbsp; and extra whitespace
            label = re.sub(r'&nbsp;', ' ', label)
            label = re.sub(r'\xa0', ' ', label)  # Non-breaking space
            label = re.sub(r'\s+', ' ', label)  # Normalize whitespace
            label = label.strip()
            
            # Remove leading/trailing punctuation and whitespace
            label = re.sub(r'^[\s\.,;:]+', '', label)
            label = re.sub(r'[\s\.,;:]+$', '', label)
            
            # Clean special characters for JSON safety
            label = label.replace('’', "'").replace('‘', "'")
            label = label.replace('“', '"').replace('”', '"')
            label = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', label)  # Control characters
            
            # Only add if there's meaningful label text (at least 5 chars)
            if label and len(label) >= 5:
                options.append({
                    'value': option_value,
                    'label': label
                })
                seen_values.add(option_value.lower())
                self.log(f"✅ Extracted option {option_value}: {label[:60]}{'...' if len(label) > 60 else ''}")
        
        self.log(f"📊 Total options extracted: {len(options)}")
        return options
    
    def extract_questions(self, html_content, start_q, end_q):
        """
        UNIVERSAL QUESTION EXTRACTOR for matching_headings and labelling questions
        Handles:
        - "14 Paragraph A" format (matching headings)
        - "11 Room 1" format (labelling)
        - Various HTML structures with images, spans, etc.
        Returns: list of dicts with {'number': 14, 'label': 'Paragraph A', 'html': '...'}
        """
        # Remove images first to avoid confusion
        soup = BeautifulSoup(html_content, 'html.parser')
        for img in soup.find_all('img'):
            img.decompose()
        html_content = str(soup)
        
        questions = []
        seen_questions = set()

        self.log(f"🔍 UNIVERSAL QUESTION EXTRACTION for range {start_q}-{end_q}")
        
        # PRIORITY 1: Matching Headings format (14 Paragraph A, 15 Paragraph B, etc.)
        # Handle multiple formats:
        # Format 1: <strong>14</strong> Paragraph A
        # Format 2: <strong>14</strong>&nbsp;&nbsp; Paragraph <strong>A</strong>
        # Format 3: <strong>14</strong> Paragraph <strong>A</strong>
        
        # Try to find questions with paragraph references including the letter inside strong tags
        paragraph_patterns = [
            # Pattern 1: Question number, then "Paragraph", then letter in strong tag
            r'<strong>\s*(\d+)\s*</strong>\s*(?:&nbsp;)*\s*Paragraph\s*(?:&nbsp;)*\s*<strong>\s*([A-Z])\s*</strong>',
            # Pattern 2: Question number, then "Paragraph X" where X is a letter (not in strong)
            r'<strong>\s*(\d+)\s*</strong>\s*(?:&nbsp;)*\s*(Paragraph\s+[A-Z])',
        ]
        
        for pattern_idx, paragraph_pattern in enumerate(paragraph_patterns):
            matches = list(re.finditer(paragraph_pattern, html_content, re.IGNORECASE))
            
            if matches:
                self.log(f"✅ Found {len(matches)} paragraph-style questions (pattern {pattern_idx + 1})")
                for match in matches:
                    q_num = match.group(1).strip()
                    
                    # Handle different group structures
                    if len(match.groups()) >= 2:
                        # If letter is in separate strong tag, combine "Paragraph" + letter
                        if pattern_idx == 0:
                            q_text = f"Paragraph {match.group(2).strip()}"
                        else:
                            q_text = match.group(2).strip()
                    else:
                        q_text = match.group(2).strip()
                    
                    try:
                        q_num_int = int(q_num)
                        if start_q <= q_num_int <= end_q and q_num not in seen_questions:
                            questions.append({
                                'number': q_num_int,
                                'label': q_text,
                                'html': match.group(0)
                            })
                            seen_questions.add(q_num)
                            self.log(f"✅ EXTRACTED Q{q_num}: {q_text}")
                    except ValueError:
                        continue
                
                # If we found matches, don't try other patterns
                if questions:
                    break

        # PRIORITY 2: Traditional labelling format (various patterns)
        if not questions:
            self.log(f"⚠️ No paragraph-style questions, trying traditional patterns...")
            
            # COMPREHENSIVE question patterns
            question_patterns = [
                # Pattern 0: number, label text, then trailing number inside <strong> (e.g., Room <strong>1</strong>)
                r'<strong>\s*(\d+)\s*</strong>\s*(?:&nbsp;|\s)*\s*([A-Za-z][^<]{1,200}?)\s*(?:&nbsp;|\s)*<strong>\s*(\d+)\s*</strong>',
                r'<strong>\s*(\d+)\s*</strong>\s*(?:&nbsp;)*\s*([^<\n]{3,200}?)(?=\s*<drag-drop|<br|</p|$)',
                r'<p><strong>\s*(\d+)\s*(?:&nbsp;)?\s*</strong>\s*(?:&nbsp;)*\s*([^<]{5,300}?)</p>',
                r'<strong>(\d+)&nbsp;</strong>&nbsp;&nbsp;([^<]{5,300}?)(?=<|$)',
                r'<strong>\s*(\d+)\s*</strong>[^a-zA-Z]*([a-zA-Z][^<]{3,300}?)(?=<|$)',
                r'<p><strong>(\d+)</strong>\s*(?:&nbsp;)*([^<]+?)</p>',
                r'<p><strong>(\d+)\.?\s*</strong>\s*([^<]+?)</p>',
                r'<strong>(\d+)\s*</strong>\s*([^<]+?)(?=<strong>|</p>|$)',
                r'(\d+)\.\s*([a-zA-Z][^<\n]{10,200}?)(?=\n|\d+\.|\s*</)',
            ]
            
            for i, pattern in enumerate(question_patterns):
                matches = list(re.finditer(pattern, html_content, re.DOTALL | re.IGNORECASE))
                self.log(f"Pattern {i+1} found {len(matches)} matches")

                for match in matches:
                    q_num = match.group(1).strip()
                    q_text = match.group(2).strip()
                    # If a trailing number (e.g., Room <strong>1</strong>) was captured, append it
                    if len(match.groups()) >= 3 and match.group(3) and match.group(3).strip().isdigit():
                        q_text = f"{q_text} {match.group(3).strip()}"
                    
                    # Clean up
                    q_text = re.sub(r'&nbsp;|&amp;nbsp;|\xa0', ' ', q_text)
                    # Preserve digits like "Room 1" exactly as authored
                    q_text = re.sub(r'\s+', ' ', q_text).strip()
                    
                    # Clean special characters for JSON safety
                    q_text = q_text.replace('’', "'").replace('‘', "'")
                    q_text = q_text.replace('“', '"').replace('”', '"')
                    q_text = q_text.replace('\u00a0', ' ')
                    q_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', q_text)
                    
                    # Check if question number is in our range
                    try:
                        q_num_int = int(q_num)
                        if start_q <= q_num_int <= end_q and q_num not in seen_questions and len(q_text) >= 3:
                            questions.append({
                                'number': q_num_int,
                                'label': q_text,
                                'html': match.group(0)
                            })
                            seen_questions.add(q_num)
                            self.log(f"✅ EXTRACTED Q{q_num}: {q_text}")
                    except ValueError:
                        continue

                if questions:  # Stop if we found questions
                    break

        # Fallback: HTML structure extraction
        if not questions:
            self.log(f"⚠️ No pattern matches, trying HTML structure extraction...")
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for elem in soup.find_all(['p', 'div', 'strong']):
                strong_tags = elem.find_all('strong') if elem.name != 'strong' else [elem]
                
                for strong_tag in strong_tags:
                    strong_text = strong_tag.get_text().strip()
                    if strong_text.isdigit():
                        q_num = strong_text
                        try:
                            q_num_int = int(q_num)
                            if start_q <= q_num_int <= end_q and q_num not in seen_questions:
                                # Extract text after the strong tag
                                label_text = ""
                                for sibling in strong_tag.next_siblings:
                                    if isinstance(sibling, str):
                                        label_text += sibling
                                    elif hasattr(sibling, 'get_text'):
                                        text = sibling.get_text()
                                        # Stop if we hit drag-drop or another question
                                        if 'drag-drop' in str(sibling) or re.search(r'<strong>\d+</strong>', str(sibling)):
                                            break
                                        label_text += text
                                
                                label_text = label_text.strip()
                                # Preserve exact authoring including numbers like "Room 1"
                                label_text = re.sub(r'\s+', ' ', label_text)
                                
                                # Clean special characters
                                label_text = label_text.replace('’', "'").replace('‘', "'")
                                label_text = label_text.replace('“', '"').replace('”', '"')
                                label_text = label_text.replace('\u00a0', ' ')
                                label_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', label_text)
                                
                                if label_text and len(label_text) >= 3:
                                    questions.append({
                                        'number': q_num_int,
                                        'label': label_text,
                                        'html': str(strong_tag)
                                    })
                                    seen_questions.add(q_num)
                                    self.log(f"✅ EXTRACTED (HTML) Q{q_num}: {label_text}")
                        except ValueError:
                            continue

        self.log(f"🎯 UNIVERSAL EXTRACTION COMPLETE: Found {len(questions)} questions")
        
        # Sort by question number
        questions.sort(key=lambda q: q['number'])
        return questions
    
    def extract_image(self, html_content):
        """
        Extract image tags from HTML content
        Returns: string with all <img> tags or empty string
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all('img')
        
        if images:
            image_html = ''.join([str(img) for img in images])
            self.log(f"✅ Found {len(images)} image(s)")
            return f"<p>{image_html}</p>"
        
        return ""
    
    def build_drag_drop_component(self, options, questions, question_range, instruction_html="", image_html=""):
        """
        UNIVERSAL DRAG-DROP COMPONENT BUILDER for matching_headings
        Returns: HTML string in the exact format shown in the example:
        
        <drag-drop-matching-sentence-endings data-options='[...]' data-question-type="matching_headings" data-repeat="false">
            <h3><em><strong>Questions 14-18</strong></em></h3>
            <p><em>Choose the correct heading...</em></p>
            <strong>14</strong> Paragraph A <drag-drop-sentence-input data-question-number="14" data-question-type="matching_headings">…</drag-drop-sentence-input><br/>
            <strong>15</strong> Paragraph B <drag-drop-sentence-input data-question-number="15" data-question-type="matching_headings">…</drag-drop-sentence-input><br/>
            ...
        </drag-drop-matching-sentence-endings>
        """
        # Build options JSON with proper formatting
        options_json = json.dumps(options, ensure_ascii=False, indent=None)
        # Escape for safe embedding inside single-quoted HTML attribute
        # Important: single quotes in labels (e.g., Children's) must be escaped
        options_attr = (
            options_json
            .replace('&', '&amp;')
            .replace("'", '&#39;')
        )
        # Note: keep only full objects in data-options per required structure
        
        # Build the main container
        html_parts = []
        
        # Start drag-drop component with data-question-type="matching_headings"
        html_parts.append(
            f'<drag-drop-matching-sentence-endings data-options=\'{options_attr}\' '
            f'data-question-type="{self.question_type}" data-repeat="false">'
        )
        html_parts.append(' ')
        
        # Add question range header
        html_parts.append(f'<h3><em><strong>{question_range}</strong></em></h3>')
        html_parts.append(' ')
        
        # Add instruction if provided
        if instruction_html:
            html_parts.append(instruction_html)
            html_parts.append(' ')
        
        # Add each question with drag-drop input
        # Format: <strong>14</strong> Paragraph A <drag-drop-sentence-input...>...<br/>
        for q in questions:
            q_num = q['number']
            q_label = q['label']
            
            html_parts.append(
                f'<strong>{q_num}</strong> {q_label} '
                f'<drag-drop-sentence-input data-question-number="{q_num}" data-question-type="{self.question_type}">…</drag-drop-sentence-input>'
                f'<br/>'
            )
        
        # Close drag-drop component
        html_parts.append('</drag-drop-matching-sentence-endings>')
        
        return ''.join(html_parts)
    
    def parse_and_insert_inputs(self, html_content, start_q, end_q, question_range=""):
        """
        UNIVERSAL PARSER for matching_headings and labelling questions
        Main parsing function that:
        1. Detects if this is a labelling/matching_headings question
        2. Extracts options (letters or roman numerals)
        3. Extracts questions (with paragraph references or labels)
        4. Builds drag-drop component
        5. Preserves images and instructions
        """
        self.log(f"🎯 Starting UNIVERSAL parser for questions {start_q}-{end_q}")
        
        # Check if already processed
        if 'data-question-type="matching_headings"' in html_content or 'drag-drop-matching' in html_content:
            self.log("⚠️ Already processed, skipping")
            return html_content, []
        
        # Detect if this is a labelling/matching_headings question
        if not self.detect_labelling(html_content):
            self.log("❌ Not detected as labelling/matching_headings question")
            return html_content, []
        
        self.log("✅ Detected as labelling/matching_headings question")
        # Decide behavior for instructions: prefer matching_headings when "List of Headings" or roman numerals exist
        has_list_of_headings = 'list of headings' in BeautifulSoup(html_content, 'html.parser').get_text(separator=' ', strip=True).lower()
        has_roman_like = bool(re.search(r'<strong[^>]*>\s*(i{1,3}|iv|v|vi{1,3}|viii?|ix|x|xi{0,3})\s*</strong>', html_content, re.IGNORECASE))
        room_pattern_present = bool(re.search(r'<strong>\s*\d+\s*</strong>[^<]*\bRoom\b[^<]*<strong>\s*\d+\s*</strong>', html_content, re.IGNORECASE))
        # Force matching_headings style when headings cues are present
        is_labelling = False if (has_list_of_headings or has_roman_like) else room_pattern_present
        # Always output matching_headings component type for this parser
        self.question_type = 'matching_headings'
        
        # Extract options (roman numerals or letters)
        options = self.extract_options(html_content)
        if not options:
            self.log("❌ No options found")
            return html_content, []
        # If options are letters (A, B, ...), convert to sequential roman numerals (i, ii, ...)
        if options and all(len(o['value']) == 1 and o['value'].isalpha() and o['value'].isupper() for o in options):
            roman_map = [
                'i','ii','iii','iv','v','vi','vii','viii','ix','x',
                'xi','xii','xiii','xiv','xv','xvi','xvii','xviii','xix','xx'
            ]
            converted = []
            for idx, opt in enumerate(options):
                roman_value = roman_map[idx] if idx < len(roman_map) else str(idx + 1)
                converted.append({'value': roman_value, 'label': opt['label']})
            options = converted
        self.log(f"✅ Found {len(options)} options: {[o['value'] for o in options]}")
        
        # Extract questions
        questions = self.extract_questions(html_content, start_q, end_q)
        if not questions:
            self.log("❌ No questions found")
            return html_content, []
        
        self.log(f"✅ Found {len(questions)} questions")
        # Sanitize extracted labels to avoid leftover HTML fragments like 'strong>'
        for q in questions:
            label = q['label']
            # Remove any HTML tags and stray 'strong>' fragments
            label = BeautifulSoup(label, 'html.parser').get_text(separator=' ', strip=True)
            label = unescape(label)
            label = label.replace('\xa0', ' ')
            label = re.sub(r'/?strong&gt;?', '', label, flags=re.IGNORECASE)
            label = re.sub(r'/?strong>', '', label, flags=re.IGNORECASE)
            label = re.sub(r'\s+', ' ', label).strip()
            q['label'] = label
        
        # Parse HTML to extract images and instructions
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract images (preserve them separately)
        images = soup.find_all('img')
        image_html = ''.join([str(img) for img in images]) if images else ""
        
        # Preserve original instruction HTML (before first question), but strip option lists and images
        instruction_html = ""
        try:
            first_q_match = re.search(rf'<strong>\s*{start_q}\s*</strong>', html_content, re.IGNORECASE)
            if first_q_match:
                header_chunk = html_content[:first_q_match.start()]
                header_soup = BeautifulSoup(header_chunk, 'html.parser')
                # Remove images
                for img in header_soup.find_all('img'):
                    img.decompose()
                # Helper predicates
                def is_option_paragraph(p_tag):
                    strong = p_tag.find('strong')
                    if not strong:
                        return False
                    s = strong.get_text(strip=True)
                    is_letter = len(s) == 1 and s.isalpha() and s.isupper()
                    is_roman = bool(re.match(r'^(i{1,3}|iv|v|vi{1,3}|viii?|ix|x|xi{1,3}|xii|xiii|xiv|xv|xvi{1,3}|xviii?|xix|xx)$', s.lower()))
                    return is_letter or is_roman
                def is_instruction_text(text):
                    tl = text.lower()
                    return (
                        'choose the correct heading' in tl or
                        'write the correct number' in tl or
                        'write the correct letter' in tl or
                        'label the' in tl or
                        ('choose' in tl and 'from the box' in tl)
                    )
                filtered_parts = []
                for elem in header_soup.find_all(['p', 'div', 'h3', 'h4', 'h5']):
                    text = elem.get_text(separator=' ', strip=True)
                    if not text:
                        continue
                    if elem.name == 'p' and is_option_paragraph(elem):
                        continue
                    if elem.name in ('h3', 'h4', 'h5') or is_instruction_text(text):
                        filtered_parts.append(str(elem))
                instruction_html = ''.join(filtered_parts)
        except Exception:
            # Fallback to previous heuristic if anything goes wrong
            instruction_parts = []
            for elem in soup.find_all(['p', 'div', 'h3', 'h4', 'h5']):
                text = elem.get_text(strip=True).lower()
                if not is_labelling:
                    if text == 'list of headings' or 'choose the correct heading' in text or 'write the correct number' in text:
                        instruction_parts.append(str(elem))
                else:
                    if 'label the' in text or 'choose' in text:
                        instruction_parts.append(str(elem))
            instruction_html = ''.join(instruction_parts) if instruction_parts else ""
        
        # Build question range if not provided
        if not question_range:
            # Use en dash
            question_range = f"Questions {start_q}–{end_q}"
        
        # Build drag-drop component
        drag_drop_component = self.build_drag_drop_component(
            options=options,
            questions=questions,
            question_range=question_range,
            instruction_html=instruction_html,
            image_html=""  # Images are preserved separately
        )
        
        # Build final HTML structure
        new_html_parts = []
        
        # Add images first (if any)
        if image_html:
            new_html_parts.append(f'<p>{image_html}</p>')
            new_html_parts.append('\n\n')
        
        # ONLY add drag-drop component wrapped in div
        # DO NOT duplicate options as plain text
        new_html_parts.append('<p><div>')
        new_html_parts.append(drag_drop_component)
        new_html_parts.append('</div></p>')
        
        new_html = ''.join(new_html_parts)
        
        # Return the new HTML and the list of processed question numbers
        processed_questions = [q['number'] for q in questions]
        
        self.log(f"🏆 SUCCESS: Created drag-drop component for questions {processed_questions}")
        
        return new_html, processed_questions


# Django integration function
def parse_labelling_questions(html_content, start_q, end_q, question_range=""):
    """
    Django-friendly function to parse labelling questions
    Usage in Django models:
        from apps.listening.utils.labelling_parser import parse_labelling_questions
        new_html, processed = parse_labelling_questions(section_html, 11, 15)
    """
    parser = LabellingParser()
    return parser.parse_and_insert_inputs(html_content, start_q, end_q, question_range)
