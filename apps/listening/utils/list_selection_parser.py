import re
import json
import html
from bs4 import BeautifulSoup


class ListSelectionParser:
    """List Selection Parser for IELTS Listening - handles 'Choose TWO letters A-E' format"""
    
    def __init__(self):
        self.question_type = "list_selection"
        self.debug = True
    
    def log(self, message):
        """Debug logging"""
        if self.debug:
            print(f"[LIST_SELECTION] {message}")
    
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
    
    def is_list_selection_question(self, html_content, plain_text):
        """Detect if this is a list selection question"""
        clean_html = self.clean_text_for_analysis(html_content)
        clean_text = self.clean_text_for_analysis(plain_text).lower()
        
        self.log("🔍 Analyzing for list selection format...")
        
        # Strong indicators for list selection
        list_selection_indicators = [
            'choose two letters',
            'choose three letters', 
            'choose four letters',
            'choose five letters',
            'choose six letters',
            'choose seven letters',
            'choose eight letters',
            'choose nine letters',
            'choose two answers from the box',
            'choose three answers from the box',
            'choose four answers from the box',
            'choose five answers from the box',
            'choose six answers from the box',
            'choose seven answers from the box',
            'choose eight answers from the box',
            'choose nine answers from the box',
            'choose two',
            'choose three',
            'choose four',
            'choose five',
            'choose six',
            'select two letters',
            'select three letters',
            'write the correct letters in boxes',
            'write the correct letter in boxes'
        ]
        
        has_list_selection_context = any(indicator in clean_text for indicator in list_selection_indicators)
        
        # Check for A-I range (expanded from A-G to support A-I)
        has_ag_in_html = bool(re.search(r'[A-I]', clean_html))
        has_ag_in_text = bool(re.search(r'letters?\s*[A-I]', clean_text, re.IGNORECASE)) or bool(re.search(r'[A-I]', clean_text, re.IGNORECASE))
        has_ag_range = has_ag_in_html and has_ag_in_text
        
        # Check for "Questions X-Y" format (range format)
        has_questions_range_format = bool(re.search(r'[Qq]uestions?\s+\d+[-–]\d+', clean_text))
        
        # Check for "Questions X and Y" format
        has_questions_and_format = bool(re.search(r'[Qq]uestions?\s+\d+\s+and\s+\d+', clean_text))
        
        # Check for multiple options (A, B, C, D, E, F, G, H, I)
        # Including nested spans format and <br /> format
        option_patterns = [
            # Pattern 0: <br /> format: "A &nbsp; &nbsp;altitude<br />" 
            # Must be: letter + spaces/nbsp + lowercase letter (option text starts with lowercase)
            # Use word boundary to avoid matching "e THREE" or "h THREE"
            r'\b([A-I])(?:\s|&nbsp;){1,}([a-z][a-z][^<]*?)<br',
            # Pattern 0b: After <br /> split: "A &nbsp; &nbsp;altitude" (no <br> at end)
            r'\b([A-I])(?:\s|&nbsp;){1,}([a-z][a-z][^<]*?)(?:<br|</p>|$)',
            # Pattern 1: Nested spans format: <p><span...><span...><strong>A </strong></span></span></span></p>
            r'<p[^>]*>(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\s*[A-I]\s*(?:&nbsp;)*\s*</strong>(?:</span>)*(?:</span>)*(?:</span>)*(?:</p>)',
            # Pattern 2: Standard format
            r'<strong>\s*[A-I]\s*</strong>',
            r'<em>[^<]*<strong>\s*[A-I]\s*</strong>',
            r'<strong>\s*[A-I][^>]*</strong>',
            # Pattern 3: Plain text format: "A    altitude" or "A &nbsp; altitude" (at least 2 lowercase letters)
            r'\b([A-I])(?:\s|&nbsp;){2,}([a-z][a-z])',
        ]
        
        option_count = 0
        for pattern in option_patterns:
            matches = re.findall(pattern, clean_html, re.IGNORECASE)
            option_count += len(matches)
            if matches:
                self.log(f"  Pattern matched {len(matches)} options: {pattern[:50]}...")
        
        # Lower threshold for <br /> format - if we have "choose three letters A-F", we need at least 3 options
        # But also check if we have A-F range explicitly mentioned
        has_af_range = bool(re.search(r'letters?\s*[A-F]', clean_text, re.IGNORECASE) or re.search(r'[A-F]', clean_text, re.IGNORECASE))
        has_choose_letters = bool(re.search(r'choose\s+(two|three|four|five)\s+letters', clean_text, re.IGNORECASE))
        # If we have "choose three letters A-F" and at least 1 option found, it's likely list selection
        has_multiple_options = option_count >= 3 or (has_af_range and option_count >= 1) or (has_choose_letters and option_count >= 1)
        
        # Exclusions - should NOT be other question types
        exclusions = [
            'true, false or not given', 'yes, no or not given',
            'do the following statements agree', 'matching headings',
            'which paragraph contains', 'complete the summary',
            'list of phrases', 'list of words'
        ]
        
        has_exclusions = any(exclusion in clean_text for exclusion in exclusions)
        
        result = (has_list_selection_context and has_ag_range and (has_questions_range_format or has_questions_and_format) and has_multiple_options and not has_exclusions)
        
        self.log(f"  List selection context: {has_list_selection_context}")
        self.log(f"  A-I range: {has_ag_range}")
        self.log(f"  Questions range format: {has_questions_range_format}")
        self.log(f"  Questions and format: {has_questions_and_format}")
        self.log(f"  Multiple options: {has_multiple_options} ({option_count})")
        self.log(f"  Exclusions: {has_exclusions}")
        self.log(f"🎯 Result: {result}")
        
        return result
    
    def extract_question_range(self, html_content, plain_text):
        """Extract question range from 'Questions X and Y' or 'Questions X-Y' format"""
        clean_html = self.clean_text_for_analysis(html_content)
        clean_text = self.clean_text_for_analysis(plain_text)
        
        # Look for "Questions X-Y" pattern (range format) - handle &ndash; entity
        questions_range_match = re.search(r'[Qq]uestions?\s+(\d+)[-–&ndash;](\d+)', clean_text)
        if questions_range_match:
            start_q = int(questions_range_match.group(1))
            end_q = int(questions_range_match.group(2))
            self.log(f"✅ Found question range: {start_q}-{end_q}")
            return start_q, end_q
        
        # Also check HTML for "Questions X&ndash;Y" format
        questions_range_html = re.search(r'<strong>Questions?\s+(\d+)&ndash;(\d+)</strong>', html_content, re.IGNORECASE)
        if questions_range_html:
            start_q = int(questions_range_html.group(1))
            end_q = int(questions_range_html.group(2))
            self.log(f"✅ Found question range from HTML: {start_q}-{end_q}")
            return start_q, end_q
        
        # Look for "Questions X and Y" pattern
        questions_and_match = re.search(r'[Qq]uestions?\s+(\d+)\s+and\s+(\d+)', clean_text)
        if questions_and_match:
            start_q = int(questions_and_match.group(1))
            end_q = int(questions_and_match.group(2))
            self.log(f"✅ Found question range: {start_q} and {end_q}")
            return start_q, end_q
        
        # Fallback: look for individual question numbers
        numbers = []
        for match in re.finditer(r'<strong>\s*(\d+)\.?\s*</strong>', clean_html):
            num = int(match.group(1))
            if 1 <= num <= 50:
                numbers.append(num)
        
        if len(numbers) >= 2:
            unique = sorted(set(numbers))
            start_q, end_q = min(unique), max(unique)
            self.log(f"✅ Inferred question range: {start_q}-{end_q}")
            return start_q, end_q
        
        return None, None
    
    def extract_options_from_content(self, html_content):
        """Extract options A-I from HTML content"""
        options = []
        options_map = {}  # Use dict to track by letter value
        
        # First, detect expected letter range from instruction (A-I, A-G, A-E, etc.)
        expected_range = None
        range_match = re.search(r'letters?[,\s]+([A-I])', html_content, re.IGNORECASE)
        if range_match:
            last_letter = range_match.group(1).upper()
            expected_range = (ord('A'), ord(last_letter))
        
        # Pattern to match options like <strong>A&nbsp;&nbsp;</strong>&nbsp;what their function is
        # Including nested spans format and various &nbsp; patterns
        option_patterns = [
            # Pattern 0: <br /> format: "A &nbsp; &nbsp;altitude<br />" or "A    altitude<br />"
            r'([A-I])(?:\s|&nbsp;){1,}([a-z][^<]*?)(?:<br|</p>|$)',
            # Pattern 1: Nested spans format: <p><span...><span...><strong>A </strong></span></span></span><span...> Option text</span></span></span></p>
            r'<p[^>]*>(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\s*([A-I])\s*(?:&nbsp;)*\s*</strong>(?:</span>)*(?:</span>)*(?:</span>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:\s|&nbsp;)*([^<]+?)(?:</span>)*(?:</span>)*(?:</span>)*(?:</p>)',
            # Pattern 2: Standard format: <strong>A&nbsp;&nbsp;</strong>&nbsp;what their function is
            r'<strong>\s*([A-I])\s*&nbsp;&nbsp;</strong>&nbsp;([^<]+?)(?=<strong>|<p>|</p>|$)',
            # Pattern 2b: <strong>A</strong>&nbsp;&nbsp;text (single &nbsp; after letter)
            r'<strong>\s*([A-I])\s*</strong>&nbsp;&nbsp;([^<]+?)(?=<strong>|<p>|</p>|$)',
            # Pattern 2c: <p><strong>A</strong>&nbsp;&nbsp;text</p>
            r'<p><strong>\s*([A-I])\s*</strong>&nbsp;&nbsp;([^<]+?)</p>',
            r'<strong>\s*([A-I])\s*</strong>[^<]*?([^<]+?)(?=<strong>|<p>|</p>|$)',
            r'<strong>\s*([A-I])\s*</strong>\s*([^<]+?)(?=<strong>|<p>|</p>|$)',
            r'<strong>\s*([A-I])\s*</strong>([^<]+?)(?=<strong>|<p>|</p>|$)',
            r'<p><strong>\s*([A-I])\s*&nbsp;&nbsp;</strong>&nbsp;([^<]+?)</p>',
            r'<p><strong>\s*([A-I])\s*</strong>[^<]*?([^<]+?)</p>',
            # Pattern 3: <p><strong>A&nbsp;&nbsp;</strong>&nbsp;text</p> (for format like "A&nbsp;&nbsp;&nbsp;providing entertainment")
            r'<p><strong>\s*([A-I])\s*&nbsp;&nbsp;</strong>&nbsp;([^<]+?)</p>',
        ]
        
        for pattern in option_patterns:
            matches = list(re.finditer(pattern, html_content, re.DOTALL))
            
            for match in matches:
                letter = match.group(1).strip().upper()
                text = match.group(2).strip()
                
                # Clean the text
                text = re.sub(r'&nbsp;', ' ', text)
                text = re.sub(r'\s+', ' ', text)
                text = text.strip()
                
                if text and len(text) >= 2:  # Avoid extremely short noise but allow short labels like "IT"
                    # Store in map to avoid duplicates and allow updates
                    if letter not in options_map or len(text) > len(options_map[letter]['label']):
                        options_map[letter] = {
                            'value': letter,
                            'label': text
                        }
        
        # Always try paragraph-based extraction as secondary pass to catch missing options
        soup = BeautifulSoup(html_content, 'html.parser')
        paragraphs = soup.find_all('p')
        
        for p in paragraphs:
            p_text = p.get_text(strip=True)
            p_html = str(p)
            
            # Skip instruction paragraphs and question paragraphs
            if any(keyword in p_text.lower() for keyword in ['choose', 'write', 'correct', 'letters', 'boxes', 'answer', 'sheet', 'questions', 'area of voluntary work']):
                continue
            
            # If paragraph has <br /> tags, split and process each line
            if re.search(r'<br\s*/?>', p_html, re.IGNORECASE):
                lines = re.split(r'<br\s*/?>', p_html, flags=re.IGNORECASE)
                for line in lines:
                    # Clean line: remove \r\n and strip
                    line = line.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Try to match pattern in original HTML first (before cleaning)
                    # Pattern: "A &nbsp; &nbsp;altitude" or "A    altitude"
                    opt_match = re.search(r'([A-I])(?:\s|&nbsp;)+([a-z][^<]*?)(?:<br|</p>|$)', line, re.IGNORECASE)
                    if opt_match:
                        letter = opt_match.group(1).upper()
                        text = opt_match.group(2).strip()
                        # Clean HTML tags and entities
                        text = re.sub(r'<[^>]+>', '', text)
                        text = re.sub(r'&nbsp;', ' ', text)
                        text = re.sub(r'\s+', ' ', text).strip()
                        
                        if text and len(text) >= 2:
                            # Skip if text contains question-like phrases - MORE STRICT
                            question_indicators = ['does the speaker', 'talk about', 'of the following', 'which three', 'which two', 'which four', 'which five', 'which six', 'features of', 'area in', 'speaker talk', 'following features', 'area in spain']
                            text_lower = text.lower()
                            # Check if text starts with question-like words or contains long question phrases
                            starts_with_question = text_lower.strip().startswith(('which', 'what', 'how', 'where', 'when', 'why', 'does', 'do', 'is', 'are'))
                            contains_long_question = any(len(indicator) > 15 and indicator in text_lower for indicator in question_indicators)
                            
                            if not any(indicator in text_lower for indicator in question_indicators) and not starts_with_question and not contains_long_question:
                                # Additional check: if text is too long (>100 chars) and contains "?", likely question text
                                if len(text) > 100 and '?' in text:
                                    self.log(f"  ⏭️ Skipped option {letter} (too long and contains ?): {text[:40]}...")
                                else:
                                    if letter not in options_map or len(text) > len(options_map[letter]['label']):
                                        options_map[letter] = {
                                            'value': letter,
                                            'label': text
                                        }
                                        self.log(f"  ✅ Extracted option {letter}: {text}")
                            else:
                                self.log(f"  ⏭️ Skipped option {letter} (contains question text): {text[:40]}...")
                    else:
                        # Fallback: Remove HTML tags and try again
                        line_text = re.sub(r'<[^>]+>', '', line)
                        line_text = re.sub(r'&nbsp;', ' ', line_text)
                        line_text = re.sub(r'\s+', ' ', line_text).strip()
                        
                        # Look for pattern: "A altitude" or "A    altitude"
                        option_match = re.match(r'^([A-I])\s+(.+)$', line_text, re.IGNORECASE)
                        if option_match:
                            letter = option_match.group(1).upper()
                            text = option_match.group(2).strip()
                            
                            if text and len(text) >= 2:
                                # Skip if text contains question-like phrases
                                question_indicators = ['does the speaker', 'talk about', 'of the following', 'which three', 'which two', 'which four', 'which five', 'which six', 'features of', 'area in']
                                text_lower = text.lower()
                                if not any(indicator in text_lower for indicator in question_indicators):
                                    if letter not in options_map or len(text) > len(options_map[letter]['label']):
                                        options_map[letter] = {
                                            'value': letter,
                                            'label': text
                                        }
                                        self.log(f"  ✅ Extracted option {letter}: {text}")
                                else:
                                    self.log(f"  ⏭️ Skipped option {letter} (contains question text): {text[:40]}...")
            else:
                # Look for patterns like "A what their function is" or "Awhat their function is"
                option_match = re.match(r'^([A-I])\s*(.+)$', p_text, re.IGNORECASE)
                if option_match:
                    letter = option_match.group(1).upper()
                    text = option_match.group(2).strip()
                    
                    if text and len(text) >= 2 and not any(skip_word in text.lower() for skip_word in ['area of voluntary work', 'fundraising', 'litter collection', 'playmates', 'story club', 'first aid']):
                        # Add or update in map
                        if letter not in options_map or len(text) > len(options_map[letter]['label']):
                            options_map[letter] = {
                                'value': letter,
                                'label': text
                            }
        
        # Convert map to sorted list
        options = sorted(options_map.values(), key=lambda x: x['value'])
        
        # If we have an expected range, ensure all letters in range are present
        if expected_range and options:
            start_ord, end_ord = expected_range
            found_letters = {opt['value'] for opt in options}
            
            # Check if we're missing any letters in the expected range
            for letter_ord in range(start_ord, end_ord + 1):
                letter = chr(letter_ord)
                if letter not in found_letters:
                    self.log(f"⚠️ Missing option {letter} in expected range, attempting to find it...")
                    # Try multiple lenient patterns to find the missing option
                    lenient_patterns = [
                        rf'<strong>\s*{letter}\s*[^<]*</strong>\s*([^<]+?)(?=<strong>|<p>|</p>|$)',
                        rf'<p><strong>\s*{letter}\s*[^<]*</strong>\s*([^<]+?)</p>',
                        rf'<strong>\s*{letter}\s*&nbsp;&nbsp;</strong>\s*([^<]+?)(?=<strong>|<p>|</p>|$)',
                        rf'<p><strong>\s*{letter}\s*&nbsp;&nbsp;</strong>\s*([^<]+?)</p>',
                    ]
                    
                    for lenient_pattern in lenient_patterns:
                        match = re.search(lenient_pattern, html_content, re.IGNORECASE | re.DOTALL)
                        if match:
                            text = match.group(1).strip()
                            text = re.sub(r'&nbsp;', ' ', text)
                            text = re.sub(r'\s+', ' ', text).strip()
                            if text and len(text) >= 2:
                                options_map[letter] = {'value': letter, 'label': text}
                                self.log(f"✅ Found missing option {letter}: {text}")
                                break
                    
                    # If still not found, try BeautifulSoup approach for this specific letter
                    if letter not in options_map:
                        for p in paragraphs:
                            p_text = p.get_text(strip=True)
                            if p_text.upper().startswith(letter + ' ') or p_text.upper().startswith(letter):
                                # Skip instruction paragraphs
                                if not any(keyword in p_text.lower() for keyword in ['choose', 'write', 'correct', 'letters', 'boxes', 'answer', 'sheet', 'questions']):
                                    text = p_text[len(letter):].strip()
                                    if text and len(text) >= 2:
                                        options_map[letter] = {'value': letter, 'label': text}
                                        self.log(f"✅ Found missing option {letter} via BeautifulSoup: {text}")
                                        break
            
            # Re-sort after potential additions
            options = sorted(options_map.values(), key=lambda x: x['value'])
        
        self.log(f"🔍 Extracted {len(options)} options: {[opt['value'] for opt in options]}")
        return options
    
    def extract_question_text_from_content(self, html_content):
        """Extract the main question text from HTML content"""
        self.log(f"🔍 Extracting question text from: {html_content[:200]}...")
        
        # First try: Extract from HTML directly with improved pattern
        # Pattern: "Which THREE of the following..." followed by question text ending with ?
        question_pattern = r'which\s+(?:two|three|four|five|six|seven|eight|nine|ten)\s+of\s+the\s+following[^<]*?(?:does|do|is|are|features|things|factors|reasons|options|aspects)[^<]*?\?'
        question_match = re.search(question_pattern, html_content, re.IGNORECASE | re.DOTALL)
        if question_match:
            main_question = question_match.group(0).strip()
            # Clean up HTML tags
            main_question = re.sub(r'<[^>]+>', '', main_question)
            main_question = re.sub(r'&nbsp;', ' ', main_question)
            main_question = re.sub(r'\s+', ' ', main_question).strip()
            # Ensure it ends with question mark
            if main_question and not main_question.endswith('?'):
                main_question = main_question.rstrip('.').strip()
                if main_question:
                    main_question += '?'
            if main_question and len(main_question) > 15:
                self.log(f"🔍 Extracted question text (direct): {main_question[:50]}...")
                return main_question
        
        # Second try: Use BeautifulSoup to parse HTML and find question text
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all paragraphs
        paragraphs = soup.find_all('p')
        
        for p in paragraphs:
            text = p.get_text(strip=True)
            
            # Skip if it's an option, instruction, or question header
            if (re.match(r'^[A-G]\s', text) or 
                'Choose' in text or 
                'Write the correct' in text or
                'Questions' in text):
                continue
            
            # Check if it contains question words and "following" (typical list selection pattern)
            if any(word in text.lower() for word in ['which', 'what']) and 'following' in text.lower():
                # Clean the text but preserve spaces
                text = re.sub(r'&nbsp;', ' ', text)
                text = re.sub(r'\s+', ' ', text)
                text = text.strip()
                
                # Universal IELTS question text formatting fixes
                # Fix "WhichTWO" -> "Which TWO" pattern
                text = re.sub(r'WhichTWO', 'Which TWO', text, flags=re.IGNORECASE)
                text = re.sub(r'WhichTHREE', 'Which THREE', text, flags=re.IGNORECASE)
                text = re.sub(r'WhichFOUR', 'Which FOUR', text, flags=re.IGNORECASE)
                text = re.sub(r'WhichFIVE', 'Which FIVE', text, flags=re.IGNORECASE)
                
                # Fix "TWOthings" -> "TWO things" pattern
                text = re.sub(r'TWOthings', 'TWO things', text, flags=re.IGNORECASE)
                text = re.sub(r'THREEthings', 'THREE things', text, flags=re.IGNORECASE)
                text = re.sub(r'FOURthings', 'FOUR things', text, flags=re.IGNORECASE)
                text = re.sub(r'FIVEthings', 'FIVE things', text, flags=re.IGNORECASE)
                
                # Universal pattern: NUMBER + WORD -> NUMBER + space + WORD
                # This covers all cases like TWOopinions, THREEfactors, FOURreasons, etc.
                text = re.sub(r'(TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)([A-Za-z])', r'\1 \2', text, flags=re.IGNORECASE)
                
                # Additional common IELTS patterns
                text = re.sub(r'(ONE|TWO|THREE|FOUR|FIVE)([A-Za-z]+)', r'\1 \2', text, flags=re.IGNORECASE)
                
                # Ensure it ends with question mark
                if text and not text.endswith('?'):
                    text = text.rstrip('.').strip()
                    if text:
                        text += '?'
                
                if text and len(text) > 15:  # Must be substantial
                    self.log(f"🔍 Extracted question text (paragraph): {text[:50]}...")
                    return text
        
        # Fallback: return a generic question text
        return "Which TWO options are correct?"
    
    def extract_choose_number(self, html_content):
        """Extract the number (TWO, THREE, etc.) from 'Choose X letters' instruction"""
        if not html_content:
            return "TWO"
        
        # Look for patterns like "Choose THREE letters" or "Choose TWO letters"
        patterns = [
            r'Choose\s+(TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)\s+letters?',
            r'choose\s+(TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)\s+letters?',
            r'<strong>(TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)</strong>',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                number = match.group(1).upper()
                self.log(f"🔍 Extracted choose number: {number}")
                return number
        
        # Default to TWO if not found
        return "TWO"
    
    def extract_letter_range(self, html_content):
        """Extract the letter range (A-G, A-E, A-F, etc.) from the original instruction"""
        if not html_content:
            return None
        
        # PRIORITY 1: Look for "A-F" format directly (most common)
        # Pattern: "A-F" or "A - F" or "letters, A-F"
        direct_range_patterns = [
            r'([A-I])\s*[-–]\s*([A-I])',  # "A-F" or "A - F" format
            r'[Aa]\s*[-–]\s*([A-I])',  # "A-F" where we only need last letter
        ]
        
        for pattern in direct_range_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                if match.lastindex >= 2:
                    last_letter = match.group(2).upper()
                else:
                    last_letter = match.group(1).upper()
                letter_range = f"A-{last_letter}"
                self.log(f"🔍 Extracted letter range (direct): {letter_range}")
                return letter_range
        
        # PRIORITY 2: Look for "letters, A-F" format
        letters_pattern = r'letters?[,\s]+([A-I])\s*[.,]'
        match = re.search(letters_pattern, html_content, re.IGNORECASE)
        if match:
            last_letter = match.group(1).upper()
            letter_range = f"A-{last_letter}"
            self.log(f"🔍 Extracted letter range (from 'letters'): {letter_range}")
            return letter_range
        
        # PRIORITY 3: Look for single letter after "letters," or at end of instruction
        single_letter_patterns = [
            r'letters?[,\s]+([A-I])',  # "letters, F"
            r'([A-I])\s*[.,]\s*$',  # "F." at end
            r'<strong>([A-I])</strong>',  # <strong>F</strong>
        ]
        
        for pattern in single_letter_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                last_letter = match.group(1).upper()
                letter_range = f"A-{last_letter}"
                self.log(f"🔍 Extracted letter range (single letter): {letter_range}")
                return letter_range
        
        return None
    
    def extract_original_instruction(self, html_content):
        """Extract the original instruction text exactly as it appears"""
        if not html_content:
            return None
        
        # Look for the instruction paragraph - try multiple patterns
        soup = BeautifulSoup(html_content, 'html.parser')
        paragraphs = soup.find_all('p')
        
        for p in paragraphs:
            text = p.get_text(strip=True)
            # Check if it's an instruction (contains "Choose" and "letters")
            if 'Choose' in text and 'letters' in text.lower():
                # Get the HTML content of this paragraph to preserve formatting
                instruction_html = str(p)
                # Remove outer <p> tags but keep inner formatting
                instruction_html = re.sub(r'^<p>', '', instruction_html)
                instruction_html = re.sub(r'</p>$', '', instruction_html)
                # Preserve &nbsp; and other entities
                self.log(f"🔍 Extracted original instruction: {text[:50]}...")
                return instruction_html
        
        # Also try to find it in the raw HTML with regex as fallback
        # Pattern: <p><em>Choose ... letters, A-G</em></p>
        pattern = r'<p><em>Choose[^<]*letters?[^<]*[A-G][^<]*</em></p>'
        match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            instruction_html = match.group(0)
            instruction_html = re.sub(r'^<p>', '', instruction_html)
            instruction_html = re.sub(r'</p>$', '', instruction_html)
            self.log(f"🔍 Extracted original instruction via regex: {instruction_html[:50]}...")
            return instruction_html
        
        return None
    
    def extract_question_text_for_number(self, html_content, question_number):
        """Extract the specific text for a question number (e.g., 'Fundraising' for Q16)"""
        if not html_content:
            return ""
        
        try:
            # Look for the pattern: <strong>16&nbsp;</strong>&nbsp;&nbsp;text&nbsp;&nbsp; &hellip;
            pattern = rf'<strong>{question_number}&nbsp;</strong>&nbsp;&nbsp;([^<]+?)&nbsp;&nbsp; &hellip;'
            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
            
            if match:
                text = match.group(1).strip()
                # Clean up the text
                text = re.sub(r'\s+', ' ', text)  # Normalize spaces
                text = re.sub(r'&nbsp;+', ' ', text)  # Replace &nbsp; with spaces
                text = text.strip()
                self.log(f"🔍 Found text for Q{question_number}: '{text}'")
                return text
            
            # Fallback: look for any text after the question number before &hellip;
            pattern = rf'<strong>{question_number}&nbsp;</strong>&nbsp;&nbsp;([^<]+?)&nbsp;&nbsp;'
            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
            
            if match:
                text = match.group(1).strip()
                text = re.sub(r'\s+', ' ', text)
                text = re.sub(r'&nbsp;+', ' ', text)
                text = text.strip()
                self.log(f"🔍 Found fallback text for Q{question_number}: '{text}'")
                return text
            
            # Another fallback: look for text in paragraph with question number
            pattern = rf'<p><strong>{question_number}&nbsp;</strong>&nbsp;&nbsp;([^<]+?)</p>'
            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
            
            if match:
                text = match.group(1).strip()
                text = re.sub(r'\s+', ' ', text)
                text = re.sub(r'&nbsp;+', ' ', text)
                text = text.strip()
                self.log(f"🔍 Found paragraph text for Q{question_number}: '{text}'")
                return text
            
            self.log(f"❌ No text found for Q{question_number}")
            return ""
            
        except Exception as e:
            self.log(f"❌ Error extracting text for Q{question_number}: {e}")
            return ""
    
    def should_use_drag_drop_format(self, html_content, question_text):
        """Determine if we should use drag-drop format or list-selection format"""
        clean_text = self.clean_text_for_analysis(html_content).lower()
        question_lower = question_text.lower() if question_text else ""
        
        # Check for drag-drop indicators
        drag_drop_indicators = [
            "choose five answers from the box and write the correct letter",
            "choose four answers from the box and write the correct letter", 
            "choose three answers from the box and write the correct letter",
            "choose two answers from the box and write the correct letter"
        ]
        
        has_drag_drop_context = any(indicator in clean_text for indicator in drag_drop_indicators)
        
        # Check for list-selection indicators (old format)
        list_selection_indicators = [
            "which two issues",
            "which three issues", 
            "which four issues",
            "which five issues"
        ]
        
        # Check for Questions X and Y format separately (more specific)
        has_questions_and_format = bool(re.search(r'questions?\s+\d+\s+and\s+\d+', clean_text, re.IGNORECASE))
        
        # Check for shared question text format (e.g., "Which THREE things can students have...")
        # This is a list-selection format where all questions share the same question text
        has_shared_question_text = bool(re.search(r'which\s+(two|three|four|five|six)\s+', question_lower))
        
        has_list_selection_context = any(indicator in clean_text for indicator in list_selection_indicators)
        
        # If we have drag-drop context, use drag-drop format
        if has_drag_drop_context:
            self.log("🎯 Using drag-drop format (Choose X answers from the box detected)")
            return True
        # If we have shared question text (e.g., "Which THREE things..."), use list-selection format
        elif has_shared_question_text:
            self.log("🎯 Using list-selection format (Shared question text detected)")
            return False
        # If we have list-selection context, use old format
        elif has_list_selection_context or has_questions_and_format:
            self.log("🎯 Using list-selection format (Which X issues or Questions X and Y detected)")
            return False
        # Default to drag-drop for new patterns
        else:
            self.log("🎯 Using drag-drop format (default)")
            return True

    def build_list_selection_format(self, start_q, end_q, options, question_text, html_content):
        """Build format based on content type - drag-drop or list-selection"""
        self.log(f"🏗️ Building format for Q{start_q}-{end_q}...")
        
        if not options:
            self.log("❌ No options found")
            return '<div></div>'
        
        # Convert options to JSON
        options_json = json.dumps(options, ensure_ascii=False, separators=(',', ':'))
        
        # FORCE list-selection-tegs format - ignore drag-drop
        use_drag_drop = False  # ALWAYS use list-selection-tegs format
        
        if use_drag_drop:
            # DRAG-DROP FORMAT
            self.log("🏗️ Building drag-drop format...")
            
            # Extract original instruction text - PRESERVE IT EXACTLY
            original_instruction = self.extract_original_instruction(html_content)
            
            # Determine questions header format
            if end_q - start_q + 1 == 2:
                questions_header = f"Questions {start_q} and {end_q}"
            else:
                questions_header = f"Questions {start_q}-{end_q}"
            
            # Use original instruction if found, otherwise construct it
            if original_instruction:
                instruction_text = original_instruction
                self.log("✅ Using original instruction text")
            else:
                # Fallback: construct instruction
                choose_number = self.extract_choose_number(html_content)
                letter_range = self.extract_letter_range(html_content)
                if not letter_range:
                    letter_range = f"A-{options[-1]['value']}"
                
                if end_q - start_q + 1 == 2:
                    instruction_text = f"Choose {choose_number} letters, {letter_range} . Write the correct letters in boxes {start_q} and {end_q} on your answer sheet."
                else:
                    instruction_text = f"Choose {choose_number} answers from the box and write the correct letter, {letter_range}, next to Questions {start_q}-{end_q}."
            
            # Build question inputs for each question with their text
            question_inputs = []
            shared_question_text_used = False
            for q_num in range(start_q, end_q + 1):
                # Extract question text for this specific question
                individual_text = self.extract_question_text_for_number(html_content, q_num)
                
                # If no individual text found, use the shared question text
                if not individual_text:
                    if not shared_question_text_used:
                        # Use the shared question text for the first question
                        individual_text = question_text
                        shared_question_text_used = True
                    else:
                        # For subsequent questions, use empty or repeat shared text
                        individual_text = ""
                
                if individual_text:
                    question_inputs.append(f'<strong>{q_num}</strong> {individual_text} <drag-drop-sentence-input data-question-number="{q_num}" data-question-type="matching_headings">…</drag-drop-sentence-input>')
                else:
                    question_inputs.append(f'<strong>{q_num}</strong> <drag-drop-sentence-input data-question-number="{q_num}" data-question-type="matching_headings">…</drag-drop-sentence-input>')
            
            # Build the final format with drag-drop-matching-sentence-endings
            result = f"""<p><div><drag-drop-matching-sentence-endings data-options='{options_json}' data-question-type="matching_headings" data-repeat="false"> <h3><em><strong>{questions_header}</strong></em></h3> <p><em>{instruction_text}</em></p> {question_text} <br> {'<br/>'.join(question_inputs)} </drag-drop-matching-sentence-endings></div>"""
            
            self.log(f"✅ Drag-drop format complete for {end_q - start_q + 1} questions")
            return result
            
        else:
            # LIST-SELECTION FORMAT (old logic)
            self.log("🏗️ Building list-selection format...")
            
            # Create question numbers list for the range
            question_numbers_list = [str(q) for q in range(start_q, end_q + 1)]
            question_numbers_json = json.dumps(question_numbers_list, separators=(',', ':'))
            
            # Extract original instruction text - PRESERVE IT EXACTLY
            original_instruction = self.extract_original_instruction(html_content)
            
            # Determine questions header format
            if end_q - start_q + 1 == 2:
                questions_header = f"Questions {start_q} and {end_q}"
            else:
                questions_header = f"Questions {start_q}-{end_q}"
            
            # Use original instruction if found, otherwise construct it
            if original_instruction:
                instruction_text = original_instruction
                self.log("✅ Using original instruction text")
            else:
                # Fallback: construct instruction
                choose_number = self.extract_choose_number(html_content)
                letter_range = self.extract_letter_range(html_content)
                # IMPORTANT: If letter_range is None, extract from options
                if not letter_range and options:
                    letter_range = f"A-{options[-1]['value']}"
                elif not letter_range:
                    letter_range = "A-F"  # Default fallback
                
                if end_q - start_q + 1 == 2:
                    instruction_text = f"Choose {choose_number} letters, {letter_range}. Write the correct letters in boxes {start_q} and {end_q} on your answer sheet."
                else:
                    instruction_text = f"Choose {choose_number} letters, {letter_range}."
            
            # Build perfect list-selection-tegs format matching user's desired output
            question_numbers_list = [str(q) for q in range(start_q, end_q + 1)]
            question_numbers_json = json.dumps(question_numbers_list, separators=(',', ':'))
            
            # Extract and clean question text if available
            main_question = question_text if question_text else ""
            if main_question:
                # Clean up the question text - remove HTML tags
                main_question = re.sub(r'<[^>]+>', '', main_question)
                main_question = re.sub(r'&nbsp;', ' ', main_question)
                main_question = re.sub(r'\s+', ' ', main_question).strip()
                # Ensure it ends with question mark
                if main_question and not main_question.endswith('?'):
                    main_question = main_question.rstrip('.').strip()
                    if main_question:
                        main_question += '?'
            
            # Build result preserving original text structure EXACTLY
            result_html = '<p><br />\n'
            result_html += f'{questions_header}</p>\n'
            result_html += f'<p><br />\n{instruction_text}</p>\n'
            if main_question:
                result_html += f'<p>{main_question}</p>\n'
            result_html += f'<list-selection-tegs data-options=\'{options_json}\' question_numbers=\'{question_numbers_json}\' question_type="list_selection"></list-selection-tegs>\n'
            result_html += '<p>&nbsp;</p>'
            
            self.log(f"✅ Perfect list-selection-tegs format complete for {end_q - start_q + 1} questions")
            self.log(f"   Header: {questions_header}")
            self.log(f"   Instruction: {instruction_text}")
            self.log(f"   Question text: {main_question[:50] if main_question else 'None'}...")
            return result_html
    
    def parse_and_insert_inputs(self, html_content):
        """Main parsing function for list selection questions"""
        self.log("🎯 ========== LIST SELECTION PARSING ==========")
        
        if not html_content:
            return html_content
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            plain_text = soup.get_text(separator=' ', strip=True)
            
            # Validate
            if not self.is_list_selection_question(html_content, plain_text):
                self.log("❌ Not a list selection question")
                return html_content
            
            self.log("✅ Confirmed list selection format")
            
            # Extract question range
            start_q, end_q = self.extract_question_range(html_content, plain_text)
            if start_q is None or end_q is None:
                self.log("❌ Could not determine question range")
                return html_content
            
            # Extract options
            options = self.extract_options_from_content(html_content)
            if not options:
                self.log("❌ No options found")
                return html_content
            
            # Extract question text
            question_text = self.extract_question_text_from_content(html_content)
            
            # Build the format
            result_html = self.build_list_selection_format(start_q, end_q, options, question_text, html_content)
            
            self.log(f"🎯 List selection parsing complete for Q{start_q} and Q{end_q}")
            self.log("🎯 ========== LIST SELECTION PARSING COMPLETE ==========")
            
            return result_html
            
        except Exception as e:
            self.log(f"❌ ERROR: {e}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
            return html_content


# Function for models.py integration
def parse_list_selection(html_content):
    """List Selection parser for listening questions"""
    parser = ListSelectionParser()
    return parser.parse_and_insert_inputs(html_content)
