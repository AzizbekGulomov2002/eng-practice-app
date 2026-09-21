import re
import json
import html
from bs4 import BeautifulSoup


class ListSelectionParser:
    """List Selection Parser for IELTS Reading - handles 'Choose TWO letters A-E' format"""
    
    def __init__(self):
        self.question_type = "list_selection"
        self.debug = True
    
    def log(self, message):
        """Debug logging"""
        if self.debug:
            print(f"[READING_LIST_SELECTION] {message}")
    
    def escape_json_for_html(self, json_string):
        """Escape JSON string for safe HTML attribute usage using single quotes"""
        if not json_string:
            return json_string
        
        # No escaping needed - we use single quotes for attributes
        # JSON can contain double quotes safely
        return json_string
    
    def clean_text_for_analysis(self, text):
        """Clean text for better analysis"""
        if not text:
            return ""
        
        # Remove HTML entities
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&rsquo;', "'", text)
        text = re.sub(r'&hellip;', '...', text)
        text = re.sub(r'&[a-zA-Z]+;', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def remove_duplicate_options(self, html_content):
        """Remove ALL duplicate option paragraphs after every list-selection component"""
        if not html_content or '<list-selection-tegs' not in html_content:
            return html_content
        
        pattern = re.compile(
            r'(<list-selection-tegs[^>]*></list-selection-tegs>)(?:\s*(?:<p[^>]*>\s*<strong>\s*[A-Z]\s*</strong>.*?</p>|<strong>\s*[A-Z]\s*</strong>.*?(?=<p|$)))+',
            re.IGNORECASE | re.DOTALL
        )
        cleaned_html, count = pattern.subn(r'\1', html_content)
        
        if count:
            self.log(f"✅ Removed duplicate option paragraphs after {count} list-selection components")
        return cleaned_html
    
    def remove_option_paragraphs(self, html_content):
        """Remove raw A-E option paragraphs from the HTML"""
        if not html_content:
            return html_content
        
        pattern = re.compile(
            r'<p[^>]*>\s*<strong>\s*([A-E])(?:\s|&nbsp;|&amp;nbsp;)*</strong>(?:\s|&nbsp;|&amp;nbsp;)*[^<]*</p>',
            re.IGNORECASE | re.DOTALL
        )
        cleaned_html, count = pattern.subn('', html_content)
        
        if count:
            self.log(f"✅ Removed {count} raw option paragraphs")
        return cleaned_html
    
    def clean_result_html(self, html):
        """Clean up the result HTML to fix formatting issues"""
        # Remove empty paragraphs
        html = re.sub(r'<p>\s*</p>', '', html)
        # Remove orphaned bold tags
        html = re.sub(r'<strong>A</p>', '', html)
        html = re.sub(r'<p><strong>A</p>', '', html)
        # Clean up extra whitespace
        html = re.sub(r'\n\s*\n\s*\n', '\n\n', html)
        # Remove extra spaces around tags
        html = re.sub(r'>\s+<', '><', html)
        return html
    
    def is_list_selection_question(self, html_content, plain_text):
        """Detect if this is a list selection question"""
        clean_html = self.clean_text_for_analysis(html_content)
        clean_text = self.clean_text_for_analysis(plain_text).lower()
        
        self.log("🔍 Analyzing for list selection format...")
        
        # Strong indicators for list selection
        list_selection_indicators = [
            "choose two letters",
            "choose three letters", 
            "choose four letters",
            "choose five letters",
            "choose six letters",
            "choose seven letters",
            "choose eight letters",
            "choose nine letters",
            "choose two answers from the box",
            "choose three answers from the box",
            "choose four answers from the box",
            "choose five answers from the box",
            "choose six answers from the box",
            "choose seven answers from the box",
            "choose eight answers from the box",
            "choose nine answers from the box",
            "choose two of the following",
            "choose three of the following",
            "choose four of the following",
            "choose five of the following",
            "choose six of the following",
            "which two",
            "which three",
            "which four", 
            "which five",
            "which six",
            "write the correct letters in boxes",
            "write the correct letter in boxes",
            "correct letters in boxes",
            "correct letter in boxes",
            "which two factors",
            "which two aspects",
            "which two points",
            "which two issues"
        ]
        
        has_list_selection = any(indicator in clean_text for indicator in list_selection_indicators)
        
        # Check for multiple choice options (A, B, C, D, E format) - handle HTML entities
        option_patterns = [
            r'<strong>\s*[A-Z]\s*</strong>',
            r'<strong>[A-Z]&nbsp;</strong>',
            r'<p><strong>[A-Z]&nbsp;</strong>',
            r'<p><strong>[A-Z]</strong>',
            r'<strong>[A-Z]&nbsp;&nbsp;</strong>'
        ]
        
        option_count = 0
        for pattern in option_patterns:
            option_count += len(re.findall(pattern, clean_html, re.IGNORECASE))
        
        has_options = option_count >= 2
        
        # Check for A-E pattern (handle HTML entities and different formats)
        has_letter_range = (
            bool(re.search(r'[A-Z]\s*[-–]\s*[A-Z]', clean_text)) or
            bool(re.search(r'[A-Z]&nbsp;[-–]&nbsp;[A-Z]', clean_html)) or
            bool(re.search(r'<strong>[A-Z]</strong>[-–]<strong>[A-Z]</strong>', clean_html)) or
            bool(re.search(r'[A-Z]&nbsp;[-–]&nbsp;[A-Z]', clean_text)) or
            bool(re.search(r'[A-Z]-[A-Z]', clean_text)) or
            bool(re.search(r'[A-Z]–[A-Z]', clean_text)) or
            bool(re.search(r'<strong>[A-Z]-[A-Z]</strong>', clean_html)) or
            bool(re.search(r'<strong>[A-Z]–[A-Z]</strong>', clean_html))
        )
        
        # If no explicit letter range but we have "write the correct letters in boxes" or "choose X answers from the box",
        # try to detect implicit range from options present (A-E, A-I, etc.)
        if not has_letter_range and has_list_selection and option_count >= 4:
            # Try to detect letter range from instruction text (A-I, A-G, etc.)
            range_match = re.search(r'letters?[,\s]+([A-Z])', clean_text, re.IGNORECASE)
            if range_match:
                last_letter = range_match.group(1).upper()
                # Check if we have options from A to last_letter
                expected_letters = [chr(ord('A') + i) for i in range(ord(last_letter) - ord('A') + 1)]
                found_options = []
                for letter in expected_letters:
                    patterns = [
                        rf'<strong>{letter} </strong>',
                        rf'<strong>{letter}</strong>',
                        rf'<strong>{letter}  </strong>',
                        rf'<p><strong>{letter} </strong>',
                        rf'<p><strong>{letter}</strong>',
                        rf'<strong>{letter}&nbsp;</strong>',
                        rf'<p><strong>{letter}&nbsp;</strong>'
                    ]
                    for pattern in patterns:
                        if re.search(pattern, clean_html):
                            found_options.append(letter)
                            break
                
                if len(found_options) >= len(expected_letters) * 0.7:  # At least 70% of expected options
                    has_letter_range = True
                    self.log(f"   Implicit {expected_letters[0]}-{expected_letters[-1]} range detected from instruction and options")
            
            # Fallback: Check if we have options A, B, C, D, E (in sequence) - original logic
            if not has_letter_range:
                has_sequential_options = all(
                    re.search(rf'<strong>{letter}&nbsp;</strong>', clean_html) or 
                    re.search(rf'<strong>{letter}</strong>', clean_html)
                    for letter in ['A', 'B', 'C', 'D', 'E']
                )
                if has_sequential_options:
                    has_letter_range = True
                    self.log("   Implicit A-E range detected from sequential options")
                else:
                    # Check what options we actually have
                    found_options = []
                    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                        patterns = [
                            rf'<strong>{letter} </strong>',
                            rf'<strong>{letter}</strong>',
                            rf'<strong>{letter}  </strong>',
                            rf'<p><strong>{letter} </strong>',
                            rf'<p><strong>{letter}</strong>',
                            rf'<strong>{letter}&nbsp;</strong>',
                            rf'<p><strong>{letter}&nbsp;</strong>'
                        ]
                        for pattern in patterns:
                            if re.search(pattern, clean_html):
                                found_options.append(letter)
                                break
                    self.log(f"   Found options: {found_options}")
                    # If we have at least 4 options in sequence, consider it valid
                    if len(found_options) >= 4:
                        # Check if they form a range
                        if found_options and ord(found_options[-1]) - ord(found_options[0]) + 1 == len(found_options):
                            has_letter_range = True
                            self.log(f"   Implicit {found_options[0]}-{found_options[-1]} range detected from sequential options")
        
        self.log(f"   List selection indicators: {has_list_selection}")
        self.log(f"   Letter range pattern: {has_letter_range}")
        self.log(f"   Options found: {option_count}")
        
        is_list_selection = has_list_selection and has_letter_range and has_options
        
        if is_list_selection:
            self.log("✅ Confirmed list selection format")
        else:
            self.log("❌ Not a list selection format")
            
        return is_list_selection
    
    def extract_question_range(self, html_content, plain_text):
        """Extract question range from content"""
        clean_text = self.clean_text_for_analysis(plain_text)
        
        # Look for "Write the correct letters in boxes X and Y" pattern first (most specific)
        boxes_match = re.search(r'write the correct letters in boxes\s+(\d+)\s+and\s+(\d+)', clean_text, re.IGNORECASE)
        if boxes_match:
            start_q = int(boxes_match.group(1))
            end_q = int(boxes_match.group(2))
            self.log(f"📊 Found question range from boxes instruction: {start_q}-{end_q}")
            return start_q, end_q
        
        # Look for "Questions X and Y" pattern
        and_match = re.search(r'questions?\s+(\d+)\s+and\s+(\d+)', clean_text, re.IGNORECASE)
        if and_match:
            start_q = int(and_match.group(1))
            end_q = int(and_match.group(2))
            self.log(f"📊 Found question range: {start_q}-{end_q}")
            return start_q, end_q
        
        # Look for "Questions X-Y" pattern (handle &ndash; entity and various dash types)
        range_match = re.search(r'questions?\s+(\d+)[-–&ndash;](\d+)', clean_text, re.IGNORECASE)
        if range_match:
            start_q = int(range_match.group(1))
            end_q = int(range_match.group(2))
            self.log(f"📊 Found question range: {start_q}-{end_q}")
            return start_q, end_q
        
        # Also check HTML for "Questions X&ndash;Y" format
        range_match_html = re.search(r'<strong>Questions?\s+(\d+)&ndash;(\d+)</strong>', html_content, re.IGNORECASE)
        if range_match_html:
            start_q = int(range_match_html.group(1))
            end_q = int(range_match_html.group(2))
            self.log(f"📊 Found question range from HTML: {start_q}-{end_q}")
            return start_q, end_q
        
        # Look for individual question numbers
        numbers = []
        for match in re.finditer(r'<strong>\s*(\d+)\.?\s*</strong>', html_content):
            num = int(match.group(1))
            if 1 <= num <= 50:
                numbers.append(num)
        
        if numbers:
            unique = sorted(set(numbers))
            if len(unique) >= 2:
                start_q = min(unique)
                end_q = max(unique)
                self.log(f"📊 Inferred question range: {start_q}-{end_q}")
                return start_q, end_q
        
        self.log("❌ Could not determine question range")
        return None, None
    
    def extract_options(self, html_content):
        """Extract options from HTML content"""
        self.log("🔍 Extracting options...")
        
        options = []
        
        # Multiple patterns to match different option formats (support A-Z, not just A-E)
        # Handle &nbsp; entities and various spacing patterns
        option_patterns = [
            # General flexible pattern: <p><strong>A</strong> text</p> (allow spaces instead of &nbsp;)
            r'<p[^>]*>\s*<strong>\s*([A-Z])\s*</strong>\s*([^<]+?)</p>',
            # Pattern 1: <strong>A</strong>&nbsp;&nbsp;text
            r'<strong>([A-Z])</strong>&nbsp;&nbsp;([^<]+?)(?=<strong>|</p>|$)',
            # Pattern 1b: <strong>A</strong>&nbsp; text (single &nbsp;)
            r'<strong>([A-Z])</strong>&nbsp;\s*([^<]+?)(?=<strong>|</p>|$)',
            # Pattern 2: <p><strong>A&nbsp;</strong>&nbsp;&nbsp;text</p>
            r'<p><strong>([A-Z])&nbsp;</strong>&nbsp;&nbsp;([^<]+?)</p>',
            # Pattern 3: <strong>A&nbsp;</strong>&nbsp;&nbsp;text
            r'<strong>([A-Z])&nbsp;</strong>&nbsp;&nbsp;([^<]+?)(?=<strong>|</p>|$)',
            # Pattern 4: <p><strong>A</strong>&nbsp;&nbsp;text</p>
            r'<p><strong>([A-Z])</strong>&nbsp;&nbsp;([^<]+?)</p>',
            # Pattern 5: <p><strong>E&nbsp;</strong>&nbsp;text</p> (for option E with single &nbsp;)
            r'<p><strong>([A-Z])&nbsp;</strong>&nbsp;([^<]+?)</p>',
            # Pattern 6: <p><strong>A&nbsp;&nbsp;</strong>&nbsp;text</p> (for option E)
            r'<p><strong>([A-Z])&nbsp;&nbsp;</strong>&nbsp;([^<]+?)</p>',
            # Pattern 7: <p><strong>A&nbsp;&nbsp;</strong>text</p> (for option E without extra space)
            r'<p><strong>([A-Z])&nbsp;&nbsp;</strong>([^<]+?)</p>',
            # Pattern 8: <p><strong>A&nbsp;</strong>text</p> (single &nbsp;)
            r'<p><strong>([A-Z])&nbsp;</strong>([^<]+?)</p>',
            # Pattern 9: <strong>A&nbsp;</strong>text (single &nbsp;)
            r'<strong>([A-Z])&nbsp;</strong>([^<]+?)(?=<strong>|</p>|$)',
            # Pattern 10: <p><strong>A </strong>text</p> (space after letter)
            r'<p[^>]*>\s*<strong>\s*([A-Z])\s+</strong>\s*([^<]+?)</p>',
            # Pattern 11: <p><strong>A&nbsp;&nbsp;</strong>&nbsp;text</p> (for format like "A&nbsp;&nbsp;&nbsp;providing entertainment")
            r'<p><strong>([A-Z])&nbsp;&nbsp;</strong>&nbsp;([^<]+?)</p>',
            # Pattern 12: <strong>A&nbsp;&nbsp;</strong>&nbsp;text (without <p> wrapper)
            r'<strong>([A-Z])&nbsp;&nbsp;</strong>&nbsp;([^<]+?)(?=<strong>|</p>|$)'
        ]
        
        # Deduplicate adjacent whitespace entities before matching
        normalized_html = re.sub(r'&nbsp;|\xa0', ' ', html_content)
        normalized_html = re.sub(r'\s+', ' ', normalized_html)
        
        for i, pattern in enumerate(option_patterns):
            self.log(f"   Trying pattern {i+1}: {pattern[:50]}...")
            matches = re.finditer(pattern, normalized_html, re.DOTALL | re.IGNORECASE)
            
            pattern_options = []
            for match in matches:
                letter = match.group(1).upper()
                text = match.group(2).strip()
                
                # Clean up the text
                text = re.sub(r'&nbsp;+', ' ', text)
                text = re.sub(r'\s+', ' ', text)
                text = text.strip()
                
                if text:
                    pattern_options.append({
                        'value': letter,
                        'label': text
                    })
                    self.log(f"   ✅ Option {letter}: {text[:50]}...")
            
            if pattern_options:
                self.log(f"   ✅ Found {len(pattern_options)} options with pattern {i+1}")
                # Add to main options list, avoiding duplicates
                for opt in pattern_options:
                    if not any(existing['value'] == opt['value'] for existing in options):
                        options.append(opt)
        
        self.log(f"📊 Total options extracted: {len(options)}")
        return options
    
    def build_list_selection_format(self, html_content, question_range, options):
        """Build the list selection HTML format"""
        start_q, end_q = question_range
        
        if not options:
            self.log("❌ No options available for list selection")
            return html_content
        
        # Create question numbers list
        question_numbers = [str(q) for q in range(start_q, end_q + 1)]
        
        # Convert to JSON
        options_json = json.dumps(options, ensure_ascii=False, separators=(',', ':'))
        question_numbers_json = json.dumps(question_numbers, ensure_ascii=False, separators=(',', ':'))
        
        # Escape for HTML attributes
        options_json_escaped = self.escape_json_for_html(options_json)
        question_numbers_json_escaped = self.escape_json_for_html(question_numbers_json)
        
        # Build the list selection tag
        list_selection_tag = f'''<list-selection-tegs data-options='{options_json_escaped}' question_numbers='{question_numbers_json_escaped}' question_type="list_selection"></list-selection-tegs>'''
        
        self.log(f"🎯 Built list selection tag for questions {start_q}-{end_q}")
        self.log(f"   Options: {len(options)} items")
        self.log(f"   Question numbers: {question_numbers}")
        
        return list_selection_tag
    
    def process_single_block(self, html_content):
        """Process a single list selection block, return new HTML or None if not processed"""
        # If component already exists, just clean up any lingering option paragraphs
        if '<list-selection-tegs' in html_content:
            self.log("ℹ️ Existing list-selection component detected, cleaning block")
            cleaned = self.remove_option_paragraphs(html_content)
            cleaned = self.remove_duplicate_options(cleaned)
            cleaned = self.clean_result_html(cleaned)
            if cleaned != html_content:
                self.log("✅ Cleaned existing list-selection block")
                return cleaned
            return None
        soup = BeautifulSoup(html_content, 'html.parser')
        plain_text = soup.get_text()
        
        if not self.is_list_selection_question(html_content, plain_text):
            self.log("❌ Not a list selection question, skipping block")
            return None
        
        question_range = self.extract_question_range(html_content, plain_text)
        if not question_range[0]:
            self.log("❌ Could not extract question range")
            return None
        
        options = self.extract_options(html_content)
        if not options:
            self.log("❌ Could not extract options")
            return None
        
        list_selection_tag = self.build_list_selection_format(html_content, question_range, options)
        start_q, end_q = question_range
        
        start_patterns = [
            rf'<p><strong>Questions?\s+{start_q}\s+and\s+{end_q}</strong></p>',
            rf'<p><em><strong>Questions?\s+{start_q}\s+and\s+{end_q}</strong></em></p>',
            rf'<h3><em><strong>Questions?\s+{start_q}\s+and\s+{end_q}</strong></em></h3>',
            rf'<p><strong>Questions?\s+{start_q}-{end_q}</strong></p>',
            rf'<p><em>Write the correct letters in boxes\s+{start_q}\s+and\s+{end_q}\s+on your answer sheet\.</em></p>',
            rf'Write the correct letters in boxes\s+{start_q}\s+and\s+{end_q}\s+on your answer sheet'
        ]
        
        start_match = None
        for pattern in start_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                start_match = match
                self.log(f"   Found start pattern: {pattern}")
                break
        
        if start_match:
            start_pos = start_match.start()
            
            # Find where the question text ends (before the options start)
            # Multiple patterns to handle different question text formats
            question_end_patterns = [
                r'<p>Which.*?</p>\s*<p>&nbsp;</p>',
                r'<p>According to.*?</p>\s*<p>&nbsp;</p>',
                r'<p>Which.*?</p>\s*<p>\s*<br\s*/>\s*&nbsp;</p>',
                r'<p>Which.*?</p>\s*<p>\s*</p>',
                r'<p>Which.*?<br\s*/>\s*&nbsp;</p>',
                r'<p>Which.*?</p>\s*<p><strong>[A-Z]',  # Direct transition to options
                r'<p>Which.*?</p>\s*<p>\s*<strong>[A-Z]',  # With whitespace
                r'<p>Which.*?</p>\s*<p>\s*&nbsp;\s*<strong>[A-Z]',  # With &nbsp;
                r'<p><em>According to.*?</em></p>\s*<p><strong>[A-Z]',  # Italic question text
                r'<p><em>According to.*?</em></p>\s*<p>\s*<strong>[A-Z]',  # Italic with whitespace
                r'<p><em>According to.*?</em></p>\s*<p>\s*&nbsp;\s*<strong>[A-Z]',  # Italic with &nbsp;
                r'<p><em>According to.*?</em></p>\s*<p>&nbsp;</p>',  # Italic with empty paragraph
                r'<p><em>According to.*?</em></p>\s*<p>\s*</p>'  # Italic with empty paragraph
            ]
            
            question_end_match = None
            for pattern in question_end_patterns:
                match = re.search(pattern, html_content[start_pos:], re.DOTALL)
                if match:
                    question_end_match = match
                    break
            
            if question_end_match:
                # Keep the question header, instruction, AND the question text (like "Which TWO advantages...")
                # The question_end_match includes the question text and empty paragraph
                # We need to include the question text in the kept section, but NOT the old options
                # The question_end_match.end() includes the question text, so we use that
                question_section = html_content[start_pos:start_pos + question_end_match.end()]
                
                # Find where options start - look for first option A
                option_start_patterns = [
                    r'<p><strong>A&nbsp;</strong>&nbsp;&nbsp;',
                    r'<p><strong>A&nbsp;&nbsp;</strong>&nbsp;',
                    r'<p><strong>A</strong>&nbsp;&nbsp;',
                    r'<strong>A&nbsp;</strong>&nbsp;&nbsp;',
                    r'<strong>A&nbsp;&nbsp;</strong>&nbsp;',
                    r'<strong>A</strong>&nbsp;&nbsp;',
                    r'<p><strong>A</strong>\s+',
                    r'<strong>A</strong>\s+'
                ]
                
                option_start_pos = None
                for pattern in option_start_patterns:
                    match = re.search(pattern, html_content[start_pos + question_end_match.end():], re.IGNORECASE)
                    if match:
                        option_start_pos = start_pos + question_end_match.end() + match.start()
                        break
                
                if option_start_pos:
                    # Find where options end - look for last option E
                    option_end_patterns = [
                        r'<p><strong>E&nbsp;&nbsp;</strong>&nbsp;.*?</p>',
                        r'<p><strong>E&nbsp;</strong>&nbsp;&nbsp;.*?</p>',
                        r'<p><strong>E</strong>&nbsp;&nbsp;.*?</p>',
                        r'<strong>E&nbsp;&nbsp;</strong>&nbsp;.*?</p>',
                        r'<strong>E&nbsp;</strong>&nbsp;&nbsp;.*?</p>',
                        r'<strong>E</strong>&nbsp;&nbsp;.*?</p>',
                        r'<p><strong>E&nbsp;</strong>.*?</p>',
                        r'<p><strong>E</strong>.*?</p>',
                        r'<strong>E&nbsp;</strong>.*?</p>',
                        r'<strong>E</strong>.*?</p>'
                    ]
                    
                    option_end_pos = None
                    for pattern in option_end_patterns:
                        matches = list(re.finditer(pattern, html_content, re.DOTALL | re.IGNORECASE))
                        if matches:
                            # Get the last match (last option E)
                            option_end_pos = matches[-1].end()
                            break
                    
                    if option_end_pos:
                        # Replace: keep everything before options, add component, keep everything after options
                        before = html_content[:option_start_pos]
                        after = html_content[option_end_pos:]
                        
                        # Also remove trailing empty paragraphs
                        after = re.sub(r'^\s*<p>\s*</p>\s*', '', after)
                        after = re.sub(r'^\s*<p>\s*&nbsp;\s*</p>\s*', '', after)
                        
                        result = before + "\n\n<p>\n\n" + list_selection_tag + "\n\n</p>\n\n" + after
                        
                        # Clean up the result HTML
                        result = self.clean_result_html(result)
                        result = self.remove_option_paragraphs(result)
                        result = self.remove_duplicate_options(result)
                        
                        self.log("✅ Successfully replaced options section with list selection tag (removed old options)")
                        return result
                
                # Fallback: if we couldn't find option positions, use the old method
                # But make sure we remove options
                before = html_content[:start_pos]
                after = html_content[start_pos + question_end_match.end():]
                
                # Remove all option paragraphs from 'after'
                after = self.remove_option_paragraphs(after)
                
                # Remove empty paragraphs
                after = re.sub(r'<p>\s*</p>', '', after)
                after = re.sub(r'<p>\s*&nbsp;\s*</p>', '', after)
                
                result = before + question_section + "\n\n<p>\n\n" + list_selection_tag + "\n\n</p>\n\n" + after
                
                # Clean up the result HTML
                result = self.clean_result_html(result)
                result = self.remove_option_paragraphs(result)
                result = self.remove_duplicate_options(result)
                
                self.log("✅ Successfully replaced content with list selection tag (removed old options)")
                return result
            else:
                self.log("❌ Could not find question end pattern")
        
        # Fallback: try to find and replace the options section
        self.log("⚠️ Using fallback: trying to replace options section")
        
        # Look for the start of options (first <strong>A pattern) - try multiple patterns
        option_start_patterns = [
            r'<p><strong>A&nbsp;</strong>&nbsp;&nbsp;',
            r'<p><strong>A&nbsp;</strong>&nbsp;',
            r'<strong>A&nbsp;</strong>&nbsp;&nbsp;',
            r'<strong>A&nbsp;</strong>&nbsp;',
            r'<p><strong>A</strong>&nbsp;&nbsp;',
            r'<p><strong>A</strong>\s+',
            r'<strong>A</strong>\s+'
        ]
        
        option_start_match = None
        option_start_pos = None
        for pattern in option_start_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                option_start_match = match
                option_start_pos = match.start()
                self.log(f"   Found option start with pattern: {pattern}")
                break
        
        if option_start_pos is not None:
            # Find where options end - look for last option E
            option_end_patterns = [
                r'<p><strong>E&nbsp;&nbsp;</strong>&nbsp;.*?</p>',
                r'<p><strong>E&nbsp;</strong>&nbsp;&nbsp;.*?</p>',
                r'<p><strong>E</strong>&nbsp;&nbsp;.*?</p>',
                r'<strong>E&nbsp;&nbsp;</strong>&nbsp;.*?</p>',
                r'<strong>E&nbsp;</strong>&nbsp;&nbsp;.*?</p>',
                r'<strong>E</strong>&nbsp;&nbsp;.*?</p>',
                r'<p><strong>E&nbsp;</strong>.*?</p>',
                r'<p><strong>E</strong>.*?</p>',
                r'<strong>E&nbsp;</strong>.*?</p>',
                r'<strong>E</strong>.*?</p>'
            ]
            
            option_end_match = None
            option_end_pos = None
            for pattern in option_end_patterns:
                matches = list(re.finditer(pattern, html_content, re.DOTALL | re.IGNORECASE))
                if matches:
                    # Get the last match (last option E)
                    option_end_match = matches[-1]
                    option_end_pos = option_end_match.end()
                    break
            
            if option_end_pos is not None:
                # Replace: keep everything before options, add component, keep everything after options
                before = html_content[:option_start_pos]
                after = html_content[option_end_pos:]
                
                # Remove trailing empty paragraphs
                after = re.sub(r'^\s*<p>\s*</p>\s*', '', after)
                after = re.sub(r'^\s*<p>\s*&nbsp;\s*</p>\s*', '', after)
                
                result = before + "\n\n<p>\n\n" + list_selection_tag + "\n\n</p>\n\n" + after
                
                # Clean up the result HTML
                result = self.clean_result_html(result)
                result = self.remove_option_paragraphs(result)
                result = self.remove_duplicate_options(result)
                
                self.log("✅ Successfully replaced options section with list selection tag")
                return result
            else:
                self.log("   ❌ Could not find option end pattern")
        else:
            self.log("   ❌ Could not find option start pattern")
        
        # Final fallback: just append the tag and clean up
        self.log("⚠️ Using final fallback: appending list selection tag")
        cleaned_options_removed = self.remove_option_paragraphs(html_content)
        result = cleaned_options_removed + "\n\n<p>\n\n" + list_selection_tag + "\n\n</p>"
        result = self.clean_result_html(result)
        result = self.remove_option_paragraphs(result)
        result = self.remove_duplicate_options(result)
        return result
    
    def parse_and_insert_inputs(self, html_content):
        """Main parsing method (single block per section)"""
        self.log("🚀 Starting list selection parsing...")
        
        if not html_content:
            return html_content
        
        result = self.process_single_block(html_content)
        if result:
            result = self.remove_option_paragraphs(result)
            result = self.remove_duplicate_options(result)
            result = self.clean_result_html(result)
        return result if result else html_content


def parse_list_selection(html_content):
    """Main function to parse list selection questions"""
    parser = ListSelectionParser()
    return parser.parse_and_insert_inputs(html_content)
