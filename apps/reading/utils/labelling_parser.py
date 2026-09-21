"""
Labelling Parser - Universal parser for "Label the plan/map/diagram" questions
Works for both Reading and Listening modules
Similar to matching_headings with drag-drop functionality
"""

import re
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
        Detect if this is a labelling question
        Looks for phrases like:
        - "Label the plan/map/diagram"
        - Letter options (A, B, C, etc.)
        - Numbered questions with labels
        """
        content_lower = html_content.lower()
        
        # Check for labelling instructions
        has_label_instruction = any([
            'label the plan' in content_lower,
            'label the map' in content_lower,
            'label the diagram' in content_lower,
            'label the' in content_lower and ('plan' in content_lower or 'map' in content_lower or 'diagram' in content_lower)
        ])
        
        # Check for letter options (A, B, C, etc.) OR roman numerals (i, ii, iii, etc.)
        has_letter_options = bool(re.search(r'<p[^>]*>\s*<strong[^>]*>[A-Z]</strong>', html_content))
        has_roman_options = bool(re.search(r'<p[^>]*>\s*<strong[^>]*>(i{1,3}|iv|v|vi{1,3}|ix|x|xi{1,3})</strong>', html_content, re.IGNORECASE))
        
        # Check for numbered questions
        has_numbered_questions = bool(re.search(r'<p[^>]*>\s*<strong[^>]*>\d+</strong>', html_content))
        
        # If roman numerals + numbered questions, consider it labelling even without explicit "label the" instruction
        # This handles "List of Headings" style questions with roman numerals
        if has_roman_options and has_numbered_questions:
            return True
        
        # Otherwise, require label instruction + options + questions
        return has_label_instruction and (has_letter_options or has_roman_options) and has_numbered_questions
    
    def extract_options(self, html_content):
        """
        Extract lettered options (A, B, C, etc.) or roman numerals (i, ii, iii, etc.)
        Returns: list of dicts with {'value': 'A', 'label': 'Art collection'}
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        options = []
        
        # Pattern 1: <p><strong>A</strong> Art collection</p>
        # Pattern 2: <p><strong>i</strong> Art collection</p>
        # Pattern 3: <p><strong>A</strong>&nbsp;&nbsp; Art collection</p>
        for p in soup.find_all('p'):
            # Check if this paragraph contains options in strong tags
            strong_tags = p.find_all('strong')
            if strong_tags:
                # Get the first strong tag
                first_strong = strong_tags[0]
                strong_text = first_strong.get_text(strip=True)
                
                # Check if it's a single letter A-Z OR roman numeral
                is_letter = len(strong_text) == 1 and strong_text.isalpha() and strong_text.isupper()
                is_roman = bool(re.match(r'^(i{1,3}|iv|v|vi{0,3}|ix|x|xi{0,3})$', strong_text, re.IGNORECASE))
                
                if is_letter or is_roman:
                    option_value = strong_text
                    
                    # Get the full paragraph text
                    full_text = p.get_text(separator=' ', strip=True)
                    
                    # Remove the option value from the beginning
                    label = full_text[len(option_value):].strip()
                    
                    # Clean up the label (remove extra spaces, non-breaking spaces, etc.)
                    label = re.sub(r'\s+', ' ', label)
                    label = label.replace('&nbsp;', '').strip()
                    
                    # Remove leading/trailing punctuation
                    label = label.strip('.,;:')
                    
                    # Clean special characters for JSON safety
                    # Replace smart quotes and apostrophes with regular ones
                    label = label.replace(''', "'").replace(''', "'")
                    label = label.replace('"', '"').replace('"', '"')
                    # Remove any remaining problematic characters
                    label = label.replace('\u00a0', ' ')  # Non-breaking space
                    label = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', label)  # Control characters
                    
                    if label:  # Only add if there's actual label text
                        options.append({
                            'value': option_value,
                            'label': label
                        })
                        self.log(f"✅ Extracted option {option_value}: {label}")
        
        return options
    
    def extract_questions(self, html_content, start_q, end_q):
        """
        ROBUST question extraction with MULTIPLE patterns - COPIED FROM MATCHING_PARSER.PY
        Returns: list of dicts with {'number': 11, 'label': 'Room 1', 'html': '...'}
        """
        questions = []
        seen_questions = set()

        self.log(f"🔍 ROBUST QUESTION EXTRACTION START for range {start_q}-{end_q}")
        self.log(f"📄 HTML preview: {html_content[:300]}...")

        # COMPREHENSIVE question patterns from matching_parser.py
        question_patterns = [
            r'<p><strong>\s*(\d+)\s*(?:&nbsp;)?\s*</strong>\s*(?:&nbsp;)*\s*([^<]{5,300}?)</p>',
            r'<strong>(\d+)&nbsp;</strong>&nbsp;&nbsp;([^<]{5,300}?)(?=<|$)',
            r'<strong>\s*(\d+)\s*</strong>[^a-zA-Z]*([a-zA-Z][^<]{5,300}?)(?=<|$)',
            r'<p><strong>(\d+)</strong>\s*(?:&nbsp;)*([^<]+?)</p>',
            r'<p><strong>(\d+)\.?\s*</strong>\s*([^<]+?)</p>',
            r'<strong>(\d+)\s*</strong>\s*([^<]+?)(?=<strong>|</p>|$)',
            r'(\d+)\.\s*([a-zA-Z][^<\n]{10,200}?)(?=\n|\d+\.|\s*</)',
            r'\.(\d+)\s+([a-zA-Z][^<]{10,200}?)(?=<strong>|</p>|$)',
            r'\.(\d+)\s*([A-Z][^<]{10,200}?)(?=<strong>|</p>|$)',
            r'<p>([^<]*?)(\d+)\s+([A-Z][^<]{10,200}?)</p>',
        ]
        
        for i, pattern in enumerate(question_patterns):
            self.log(f"🔍 Trying pattern {i+1}...")
            matches = list(re.finditer(pattern, html_content, re.DOTALL | re.IGNORECASE))
            self.log(f"📊 Pattern {i+1} found {len(matches)} matches")

            for match in matches:
                # Handle patterns with 3 groups (NB text.7 Question text)
                if len(match.groups()) == 3:
                    q_num = match.group(2).strip()
                    q_text = match.group(3).strip()
                else:
                    q_num = match.group(1).strip()
                    q_text = match.group(2).strip()
                
                # Clean up
                q_text = re.sub(r'&nbsp;|&amp;nbsp;|\xa0', ' ', q_text)
                q_text = re.sub(r'\s+', ' ', q_text).strip()
                
                # Clean special characters for JSON safety
                q_text = q_text.replace(''', "'").replace(''', "'")
                q_text = q_text.replace('"', '"').replace('"', '"')
                q_text = q_text.replace('\u00a0', ' ')
                q_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', q_text)

                self.log(f"📝 Raw match - Q{q_num}: '{q_text[:50]}...'")

                # Check if question number is in our range
                try:
                    q_num_int = int(q_num)
                    if start_q <= q_num_int <= end_q and q_num not in seen_questions and len(q_text) >= 5:
                        questions.append({
                            'number': q_num_int,
                            'label': q_text,
                            'html': match.group(0)
                        })
                        seen_questions.add(q_num)
                        self.log(f"✅ EXTRACTED Q{q_num}: {q_text}")
                except ValueError:
                    continue

        # Fallback: plain text extraction
        if not questions:
            self.log(f"⚠️ No HTML matches, trying plain text extraction...")
            plain_text_content = BeautifulSoup(html_content, 'html.parser').get_text()

            text_patterns = [
                r'(\d+)\.\s*([a-z][^.]{15,200}(?:\.|$))',
                r'(\d+)\s+([a-z][^0-9]{15,200}?)(?=\d+\s|$)',
                r'\.(\d+)\s+([A-Z][^.]{15,200}?)(?=\.|$|\d)',
                r'nb[^.]*\.(\d+)\s+([A-Z][^.]{15,200}?)(?=\.|$|\d)',
            ]
            for pattern in text_patterns:
                matches = re.finditer(pattern, plain_text_content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    q_num = match.group(1).strip()
                    q_text = match.group(2).strip()
                    
                    # Clean up
                    q_text = q_text.replace(''', "'").replace(''', "'")
                    q_text = q_text.replace('"', '"').replace('"', '"')
                    q_text = q_text.replace('\u00a0', ' ')
                    q_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', q_text)
                    
                    try:
                        q_num_int = int(q_num)
                        if start_q <= q_num_int <= end_q and q_num not in seen_questions and len(q_text) >= 10:
                            questions.append({
                                'number': q_num_int,
                                'label': q_text,
                                'html': ''
                            })
                            seen_questions.add(q_num)
                            self.log(f"✅ EXTRACTED (Plain) Q{q_num}: {q_text}")
                    except ValueError:
                        continue

        # Last resort: create placeholder questions from HTML structure
        if not questions:
            self.log(f"⚠️ Still no questions, trying HTML structure extraction...")
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for p_tag in soup.find_all('p'):
                strong_tag = p_tag.find('strong')
                if strong_tag and strong_tag.get_text().strip().isdigit():
                    q_num = strong_tag.get_text().strip()
                    try:
                        q_num_int = int(q_num)
                        if start_q <= q_num_int <= end_q and q_num not in seen_questions:
                            question_text = p_tag.get_text().replace(q_num, '', 1).strip()
                            question_text = re.sub(r'^\s*[^\w]*', '', question_text)
                            
                            # Clean up
                            question_text = question_text.replace(''', "'").replace(''', "'")
                            question_text = question_text.replace('"', '"').replace('"', '"')
                            question_text = question_text.replace('\u00a0', ' ')
                            question_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', question_text)
                            
                            if len(question_text) >= 5:
                                questions.append({
                                    'number': q_num_int,
                                    'label': question_text,
                                    'html': str(p_tag)
                                })
                                seen_questions.add(q_num)
                                self.log(f"✅ EXTRACTED (HTML) Q{q_num}: {question_text}")
                    except ValueError:
                        continue

        self.log(f"🎯 ROBUST EXTRACTION COMPLETE: Found {len(questions)} questions")
        
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
        Build drag-drop component similar to matching_headings
        Returns: HTML string (matching the exact structure of matching_headings)
        """
        # Build options JSON with proper formatting
        options_json = json.dumps(options, ensure_ascii=False, indent=None)
        
        # Build the main container - EXACT structure like matching_headings
        html_parts = []
        
        # Start drag-drop component with data-question-type at the top level
        html_parts.append(
            f'<drag-drop-matching-sentence-endings data-options=\'{options_json}\' '
            f'data-question-type="{self.question_type}" data-repeat="false">'
        )
        html_parts.append(' ')
        
        # Add question range header (optional - only if we're not preserving content)
        if instruction_html or image_html:
            html_parts.append(f'<h3><em><strong>{question_range}</strong></em></h3> ')
        
        # Add instruction if provided (for backward compatibility)
        if instruction_html:
            html_parts.append(instruction_html)
            html_parts.append(' ')
        
        # Add image if provided (for backward compatibility)
        if image_html:
            html_parts.append(image_html)
            html_parts.append(' ')
        
        # Add each question with drag-drop input - NO <p> tags, just like the example
        for q in questions:
            q_num = q['number']
            q_label = q['label']
            
            html_parts.append(
                f'<strong>{q_num}</strong> {q_label}'
                f'<drag-drop-sentence-input data-question-number="{q_num}" data-question-type="{self.question_type}">…</drag-drop-sentence-input>'
                f'<br/>'
            )
        
        html_parts.append(' </drag-drop-matching-sentence-endings>')
        
        return ''.join(html_parts)
    
    def parse_and_insert_inputs(self, html_content, start_q, end_q, question_range=""):
        """
        Main parsing function - detects labelling questions and converts to drag-drop format
        """
        self.log(f"🎯 Starting labelling parser for questions {start_q}-{end_q}")
        
        # Check if already processed
        if 'data-question-type="matching_headings"' in html_content:
            self.log("⚠️ Already processed, skipping")
            return html_content, []
        
        # Detect if this is a labelling question
        if not self.detect_labelling(html_content):
            self.log("❌ Not detected as labelling question")
            return html_content, []
        
        self.log("✅ Detected as labelling question")
        
        # Extract options
        options = self.extract_options(html_content)
        if not options:
            self.log("❌ No options found")
            return html_content, []
        
        self.log(f"✅ Found {len(options)} options: {[o['value'] for o in options]}")
        
        # Extract questions
        questions = self.extract_questions(html_content, start_q, end_q)
        if not questions:
            self.log("❌ No questions found")
            return html_content, []
        
        self.log(f"✅ Found {len(questions)} questions")
        
        # Extract images
        image_html = self.extract_image(html_content)
        
        # Extract content: Keep everything including options, but stop at questions
        soup = BeautifulSoup(html_content, 'html.parser')
        content_before_questions = []
        
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            
            # Check if this is a numbered question - STOP HERE
            strong_tags = p.find_all('strong')
            if strong_tags:
                first_strong_text = strong_tags[0].get_text(strip=True)
                # Check if it's a numbered question
                try:
                    num = int(first_strong_text)
                    if start_q <= num <= end_q:
                        break  # This is a question paragraph - stop here
                except ValueError:
                    pass
            
            # Add this paragraph (including options A-I)
            p_str = str(p)
            if not p_str.endswith('</p>'):
                p_str += '</p>'
            content_before_questions.append(p_str)
        
        # Join all content before questions (this includes Activity, instructions, options, etc.)
        preserved_content = '\n'.join(content_before_questions) if content_before_questions else ''
        
        # CRITICAL: Close all open tags in preserved_content to prevent nesting issues
        if preserved_content:
            # Parse preserved content and ensure all tags are closed
            temp_soup = BeautifulSoup(preserved_content, 'html.parser')
            preserved_content = str(temp_soup)  # This ensures all tags are properly closed
        
        # Build drag-drop component
        if not question_range:
            question_range = f"Questions {start_q}–{end_q}"
        
        new_html_parts = []
        
        # Add all preserved content (Activity, instructions, options, etc.)
        if preserved_content:
            new_html_parts.append(preserved_content)
            # Add a new paragraph wrapper for drag-drop to separate it cleanly
            new_html_parts.append('\n\n<p>')
        
        # Add the drag-drop component inside a new paragraph
        drag_drop_component = self.build_drag_drop_component(
            options=options,
            questions=questions,
            question_range=question_range,
            instruction_html="",  # Don't include instructions in component
            image_html=""  # Don't include image in component
        )
        new_html_parts.append(drag_drop_component)
        new_html_parts.append('</p>')
        
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
        from apps.reading.utils.labelling_parser import parse_labelling_questions
        new_html, processed = parse_labelling_questions(section_html, 11, 15)
    """
    parser = LabellingParser()
    return parser.parse_and_insert_inputs(html_content, start_q, end_q, question_range)
