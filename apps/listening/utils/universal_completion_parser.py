import re
from bs4 import BeautifulSoup


class UniversalSentenceCompletionParser:
    """
    Universal Sentence Completion Parser for IELTS Listening
    Handles multiple completion formats:
    - Sentence completion
    - Table completion  
    - Form completion
    - Note completion
    - Summary completion
    """
    
    def __init__(self):
        self.question_type = "sentence_completion"
        self.placeholder = ".............."
        
        # Comprehensive IELTS completion keywords
        self.completion_keywords = [
            # Word limits
            "no more than one word", "no more than two words", "no more than three words",
            "no more than four words", "no more than five words", "no more than six words",
            "one word only", "two words only", "three words only", "four words only",
            "one word and/or a number", "two words and/or a number", "three words and/or a number",
            "choose one word only", "write one word only",
            
            # Instructions
            "complete the sentences", "complete the summary", "complete the notes",
            "complete the table", "complete the form", "complete the flow chart",
            "answer the questions below", "fill in the gaps", "write your answers in boxes",
            "complete the sentences below", "complete the notes below",
            "write your answers in boxes", "fill in the blanks",
            
            # Listening specific
            "listen and complete", "complete while listening", "fill in while listening",
            "write down", "note down", "record your answers"
        ]
        
        # Gap patterns - ordered by priority
        self.gap_patterns = [
            # Pattern 0: Number followed by dots (e.g., "15 ........................" or "spare 15 ........................")
            # This pattern matches the number AND the dots together
            {'pattern': r'\d+(?:\s|&nbsp;)+\.{4,}', 'name': 'Number + dots', 'priority': 0},
            # Pattern 0b: Just dots (for cases where number is separate)
            {'pattern': r'\.{15,}', 'name': '15+ dots', 'priority': 0},
            
            # HTML entities - more comprehensive patterns
            {'pattern': r'&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;', 'name': '8+ hellip', 'priority': 1},
            {'pattern': r'&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;', 'name': '6+ hellip', 'priority': 2},
            {'pattern': r'&hellip;&hellip;&hellip;&hellip;&hellip;', 'name': '5+ hellip', 'priority': 3},
            {'pattern': r'&hellip;&hellip;&hellip;&hellip;', 'name': '4+ hellip', 'priority': 4},
            {'pattern': r'&hellip;&hellip;&hellip;', 'name': '3+ hellip', 'priority': 5},
            {'pattern': r'&hellip;&hellip;', 'name': '2+ hellip', 'priority': 6},
            {'pattern': r'&hellip;', 'name': '1 hellip', 'priority': 7},
            
            # Regular dots
            {'pattern': r'\.{15,}', 'name': '15+ dots', 'priority': 8},
            {'pattern': r'\.{12,}', 'name': '12+ dots', 'priority': 9},
            {'pattern': r'\.{10,}', 'name': '10+ dots', 'priority': 10},
            {'pattern': r'\.{8,}', 'name': '8+ dots', 'priority': 11},
            {'pattern': r'\.{6,}', 'name': '6+ dots', 'priority': 12},
            {'pattern': r'\.{4,}', 'name': '4+ dots', 'priority': 13},
            
            # Mixed patterns
            {'pattern': r'(?:\.|&hellip;){6,}', 'name': 'Mixed 6+', 'priority': 14},
            {'pattern': r'(?:\.|&hellip;){4,}', 'name': 'Mixed 4+', 'priority': 15},
            
            # Underscores
            {'pattern': r'_{6,}', 'name': '6+ underscores', 'priority': 16},
            {'pattern': r'_{4,}', 'name': '4+ underscores', 'priority': 17},
            
            # Spaced patterns
            {'pattern': r'(?:\.\s*){4,}', 'name': 'Spaced dots 4+', 'priority': 18},
            
            # Brackets and parentheses
            {'pattern': r'\[\.{4,}\]', 'name': 'Bracketed dots', 'priority': 19},
            {'pattern': r'\(\.{4,}\)', 'name': 'Parenthesized dots', 'priority': 20},
        ]
        
        # Question number patterns
        self.question_patterns = [
            r'<strong[^>]*>(\d+)</strong>',  # <strong>7</strong>
            r'<p[^>]*>.*?<strong[^>]*>(\d+)</strong>.*?</p>',  # In paragraph with strong
            r'\b(\d+)\.',  # 7. format
            r'<p[^>]*>.*?(\d+)\s*\..*?</p>',  # Number with dot in paragraph
            r'<td[^>]*>.*?<strong[^>]*>(\d+)</strong>.*?</td>',  # In table cell
            r'<tr[^>]*>.*?<strong[^>]*>(\d+)</strong>.*?</tr>',  # In table row
        ]

    def log(self, message):
        """Logging method"""
        print(f"[UniversalCompletion] {message}")

    def clean_html_content(self, html_content):
        """Clean HTML content while preserving structure"""
        if not html_content:
            return html_content

        self.log("🧹 Cleaning HTML content...")

        # Remove span tags with styling but keep content
        cleaned = re.sub(r'<span[^>]*>', '', html_content)
        cleaned = re.sub(r'</span>', '', cleaned)

        # Clean up extra spaces and normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = re.sub(r'\s*\n\s*', '\n', cleaned)

        return cleaned.strip()

    def detect_completion_context(self, html_content):
        """Detect if content contains completion keywords"""
        if not html_content:
            return False, []

        self.log("🔍 Detecting completion context...")

        # Extract plain text for keyword matching
        soup = BeautifulSoup(html_content, 'html.parser')
        plain_text = soup.get_text(separator=' ', strip=True).lower()

        found_keywords = []
        keyword_count = 0

        for keyword in self.completion_keywords:
            if keyword.lower() in plain_text:
                found_keywords.append(keyword)
                keyword_count += 1

        is_completion = keyword_count > 0

        if found_keywords:
            self.log(f"✅ Completion keywords found: {found_keywords}")

        self.log(f"📊 Context Analysis:")
        self.log(f"  🔍 Keywords matched: {keyword_count}")
        self.log(f"  🎯 Is completion context: {is_completion}")

        return is_completion, found_keywords

    def extract_question_numbers(self, html_content):
        """Extract question numbers from HTML content"""
        if not html_content:
            return []

        self.log("🔢 Extracting question numbers...")

        questions = []
        for pattern in self.question_patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                if match.isdigit():
                    num = int(match)
                    if 1 <= num <= 50 and num not in questions:
                        questions.append(num)

        questions.sort()
        self.log(f"📋 Found questions: {questions}")

        return questions

    def detect_completion_gaps(self, html_content):
        """Detect completion gaps using multiple patterns"""
        if not html_content:
            return []

        self.log("🔍 Detecting completion gaps...")

        # Sort patterns by priority
        sorted_patterns = sorted(self.gap_patterns, key=lambda x: x['priority'])
        
        all_gaps = []
        used_patterns = []

        for pattern_info in sorted_patterns:
            pattern = pattern_info['pattern']
            name = pattern_info['name']

            matches = list(re.finditer(pattern, html_content))
            if matches:
                self.log(f"✅ {name}: Found {len(matches)} gaps")
                all_gaps.extend(matches)
                used_patterns.append(name)
                # Don't break - collect all patterns that match

        if not all_gaps:
            self.log("❌ No completion gaps found in any format")
        else:
            # Remove overlapping gaps (keep the longest one)
            unique_gaps = []
            for gap in all_gaps:
                is_overlapping = False
                for existing_gap in unique_gaps:
                    # Check if gaps overlap
                    if (gap.start() < existing_gap.end() and gap.end() > existing_gap.start()):
                        # Keep the longer gap
                        if gap.end() - gap.start() > existing_gap.end() - existing_gap.start():
                            unique_gaps.remove(existing_gap)
                            unique_gaps.append(gap)
                        is_overlapping = True
                        break
                
                if not is_overlapping:
                    unique_gaps.append(gap)
            
            self.log(f"📊 Total gaps detected: {len(all_gaps)}")
            self.log(f"📊 Unique gaps after deduplication: {len(unique_gaps)}")
            self.log(f"🔍 Used patterns: {used_patterns}")

        return unique_gaps

    def determine_completion_type(self, html_content, found_keywords):
        """Determine the specific type of completion based on content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        plain_text = soup.get_text(separator=' ', strip=True).lower()

        # Check for specific completion types
        if any(keyword in plain_text for keyword in ["complete the table", "table"]):
            return "sentence_completion"
        elif any(keyword in plain_text for keyword in ["complete the form", "form"]):
            return "sentence_completion"
        elif any(keyword in plain_text for keyword in ["complete the notes", "notes"]):
            return "sentence_completion"
        elif any(keyword in plain_text for keyword in ["complete the summary", "summary"]):
            return "sentence_completion"
        elif any(keyword in plain_text for keyword in ["complete the sentences", "sentences"]):
            return "sentence_completion"
        else:
            return "sentence_completion"  # Default

    def create_question_input(self, question_num, completion_type):
        """Create question-input element with appropriate attributes"""
        return f'<question-input data-question-number="{question_num}" data-question-type="sentence_completion">{self.placeholder}</question-input>'

    def parse_and_insert_inputs(self, html_content):
        """
        Main method: Universal sentence completion processing
        
        Args:
            html_content (str): Raw HTML content
            
        Returns:
            str: Processed HTML with question-input elements
        """
        if not html_content or not html_content.strip():
            self.log("⚠️ Empty input - returning unchanged")
            return html_content

        try:
            self.log("🚀 UNIVERSAL SENTENCE COMPLETION PARSER - STARTED")
            self.log("=" * 70)

            # Step 1: Clean HTML content
            cleaned_html = self.clean_html_content(html_content)

            # Step 2: Detect completion context
            is_completion, found_keywords = self.detect_completion_context(cleaned_html)

            if not is_completion:
                self.log("❌ No completion keywords found - skipping")
                return html_content

            self.log("✅ Completion context confirmed")

            # Step 3: Determine completion type
            completion_type = self.determine_completion_type(cleaned_html, found_keywords)
            self.log(f"🎯 Completion type: {completion_type}")

            # Step 4: Extract question numbers (but we'll also extract from gaps)
            questions = self.extract_question_numbers(cleaned_html)
            self.log(f"📋 Extracted question numbers: {questions}")

            # Step 5: Detect completion gaps
            gaps = self.detect_completion_gaps(cleaned_html)

            if not gaps:
                self.log("❌ No completion gaps found")
                return html_content

            # Step 6: Replace gaps with question inputs
            # Sort gaps by position first
            gaps.sort(key=lambda x: x.start())
            result_html = cleaned_html
            created_questions = []
            used_questions = set()

            self.log(f"📍 Gap positions: {[g.start() for g in gaps]}")

            # CRITICAL: Extract question numbers from gaps (AFTER sorting)
            # This handles "15 ........................" format where number is in the gap
            gap_question_map = {}  # Map gap start position to question number
            self.log(f"🔍 Extracting question numbers from {len(gaps)} gaps...")
            for gap_idx, gap in enumerate(gaps):
                gap_start = gap.start()
                gap_end = gap.end()
                gap_text = cleaned_html[gap_start:gap_end]
                
                # Look for number in gap pattern (for "15 ........................" format)
                # Pattern: number + spaces/nbsp + dots (at least 4 dots)
                num_match = re.search(r'(\d+)(?:\s|&nbsp;)+\.{4,}', gap_text, re.IGNORECASE)
                if not num_match:
                    # Check text before gap (for "spare 15 ........................" format)
                    # Look up to 100 chars before gap to find number
                    search_start = max(0, gap_start - 100)
                    text_before = cleaned_html[search_start:gap_start]
                    # Look for pattern: number followed by spaces/nbsp, then dots (in combined text)
                    combined_text = text_before + gap_text
                    num_match = re.search(r'(\d+)(?:\s|&nbsp;)+\.{4,}', combined_text, re.IGNORECASE)
                    if not num_match:
                        # Also check for "number dots" pattern where number is right before gap
                        # Pattern: number + spaces/nbsp + (optional text) + dots
                        num_match = re.search(r'(\d+)(?:\s|&nbsp;)+[^\.]{0,30}\.{4,}', combined_text, re.IGNORECASE)
                    if not num_match:
                        # Just look for number immediately before gap (within last 30 chars)
                        num_match = re.search(r'(\d+)(?:\s|&nbsp;)+', text_before[-30:], re.IGNORECASE)
                
                if num_match:
                    q_num = int(num_match.group(1))
                    if 1 <= q_num <= 50:
                        gap_question_map[gap_start] = q_num  # Use position as key
                        if q_num not in questions:
                            questions.append(q_num)
                        self.log(f"  ✅ Gap at {gap_start}: Extracted Q{q_num} from gap text: {gap_text[:50]}...")
                else:
                    self.log(f"  ⚠️ Gap at {gap_start}: Could not extract question number from: {gap_text[:50]}...")
            
            questions.sort()
            self.log(f"📋 Question numbers from gaps: {questions}")

            # Process in reverse order for string position stability
            for i, gap in enumerate(reversed(gaps)):
                gap_start = gap.start()
                gap_end = gap.end()
                gap_text = cleaned_html[gap_start:gap_end]
                
                # FIRST: Check if we already extracted question number for this gap (by position)
                question_num = None
                if gap_start in gap_question_map:
                    potential_q = gap_question_map[gap_start]
                    if potential_q not in used_questions:
                        question_num = potential_q
                        used_questions.add(question_num)
                        self.log(f"✅ Using pre-extracted Q{question_num} for gap at position {gap_start}")
                
                # If not found, try to find question number right before this gap
                if not question_num:
                    search_start = max(0, gap_start - 100)
                    text_before_gap = cleaned_html[search_start:gap_start]
                    
                    # Pattern 1: Check if gap_text itself contains the number (for "number dots" pattern)
                    q_num_match = re.search(r'(\d+)(?:\s|&nbsp;)+\.{4,}', gap_text, re.IGNORECASE)
                    if not q_num_match:
                        # Also check text_before_gap + gap_text in case gap is just dots
                        q_num_match = re.search(r'(\d+)(?:\s|&nbsp;)+\.{4,}', text_before_gap + gap_text, re.IGNORECASE)
                    
                    if q_num_match:
                        potential_q = int(q_num_match.group(1))
                        # Use it if it's in questions list OR if it's a reasonable question number (1-50)
                        if (potential_q in questions or (1 <= potential_q <= 50)) and potential_q not in used_questions:
                            question_num = potential_q
                            used_questions.add(question_num)
                            if potential_q not in questions:
                                questions.append(potential_q)
                            self.log(f"✅ Found Q{question_num} in gap pattern at position {gap_start}")
                
                if not question_num:
                    # Pattern 2: number in text before gap, then dots (gap is just dots)
                    q_num_match = re.search(r'(\d+)(?:\s|&nbsp;)+[^\.]{0,30}(?:\.{3,}|&hellip;)', text_before_gap + gap_text[:min(30, len(gap_text))], re.IGNORECASE)
                    if q_num_match:
                        potential_q = int(q_num_match.group(1))
                        if (potential_q in questions or (1 <= potential_q <= 50)) and potential_q not in used_questions:
                            question_num = potential_q
                            used_questions.add(question_num)
                            if potential_q not in questions:
                                questions.append(potential_q)
                            self.log(f"✅ Found Q{question_num} before gap at position {gap_start}")
                
                if not question_num:
                    # Pattern 3: Look for number right before gap (within last 30 chars before gap)
                    recent_text = text_before_gap[-30:] if len(text_before_gap) >= 30 else text_before_gap
                    q_num_match = re.search(r'(\d+)(?:\s|&nbsp;)+', recent_text, re.IGNORECASE)
                    if q_num_match:
                        potential_q = int(q_num_match.group(1))
                        if (potential_q in questions or (1 <= potential_q <= 50)) and potential_q not in used_questions:
                            question_num = potential_q
                            used_questions.add(question_num)
                            if potential_q not in questions:
                                questions.append(potential_q)
                            self.log(f"✅ Found Q{question_num} near gap at position {gap_start}")
                
                # Fallback: Use question from list if not found
                if not question_num:
                    # Try to use questions in order
                    if questions:
                        # Find first unused question
                        for q in questions:
                            if q not in used_questions:
                                question_num = q
                                used_questions.add(question_num)
                                self.log(f"⚠️ Using fallback Q{question_num} for gap at position {gap_start}")
                                break
                    # If still no question, try to infer from gap position
                    if not question_num and len(gaps) > 0:
                        # Estimate question number based on gap index
                        estimated_q = start_q if 'start_q' in locals() else (len(gaps) - i)
                        if 1 <= estimated_q <= 50 and estimated_q not in used_questions:
                            question_num = estimated_q
                            used_questions.add(question_num)
                            if estimated_q not in questions:
                                questions.append(estimated_q)
                            self.log(f"⚠️ Using estimated Q{question_num} for gap at position {gap_start}")

                if question_num:
                    self.log(f"✅ Processing gap with Q{question_num} at position {gap_start}")
                    # Create question-input element
                    input_element = self.create_question_input(question_num, completion_type)

                    # Replace gap with input (replace the dots, keep text before)
                    result_html = result_html[:gap.start()] + input_element + result_html[gap.end():]

                    created_questions.append(question_num)
                    self.log(f"✅ Q{question_num}: Gap → question-input")

            created_questions.sort()

            self.log("=" * 70)
            self.log(f"🎉 SUCCESS: {len(created_questions)} inputs created")
            self.log(f"✅ Questions processed: {created_questions}")
            self.log(f"🎯 Completion type: {completion_type}")
            self.log(f"🔍 Keywords detected: {len(found_keywords)}")
            self.log("=" * 70)

            return result_html

        except Exception as e:
            self.log(f"❌ ERROR: {str(e)}")
            return html_content


def parse_universal_completion(html_string):
    """
    Universal completion parser function for Django integration
    
    Args:
        html_string (str): HTML content to process
        
    Returns:
        str: Processed HTML with question-input elements
    """
    try:
        parser = UniversalSentenceCompletionParser()
        result = parser.parse_and_insert_inputs(html_string)

        # Final statistics
        input_pattern = r'<question-input[^>]*data-question-number="(\d+)"[^>]*>'
        all_inputs = re.findall(input_pattern, result, re.IGNORECASE)
        unique_inputs = list(set(all_inputs))
        sorted_unique = sorted([int(x) for x in unique_inputs])

        print(f"[DJANGO-INTEGRATION] 🎉 UNIVERSAL COMPLETION FINAL REPORT:")
        print(f"[DJANGO-INTEGRATION] ✅ Total inputs created: {len(all_inputs)}")
        print(f"[DJANGO-INTEGRATION] ✅ Questions processed: {sorted_unique}")
        print(f"[DJANGO-INTEGRATION] ✅ Status: {'PERFECT' if len(all_inputs) == len(unique_inputs) else 'HAS DUPLICATES'}")
        print(f"[DJANGO-INTEGRATION] 🎯 Parser version: Universal Sentence Completion v1.0")

        return result

    except Exception as e:
        print(f"[DJANGO-INTEGRATION] ❌ Critical error: {e}")
        return html_string


# Legacy function for backward compatibility
def parse_completion_questions(html_string):
    """Legacy function - redirects to universal parser"""
    return parse_universal_completion(html_string)
