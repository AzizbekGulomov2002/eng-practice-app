import re
from bs4 import BeautifulSoup


class UniversalCompletionParser:
    def __init__(self):
        self.question_type = "sentence_completion"
        self.placeholder = ".............."

        # IELTS completion keywords - COMPREHENSIVE LIST
        self.ielts_completion_keywords = [
            # Word limits
            "no more than one word", "no more than two words", "no more than three words",
            "no more than four words", "no more than five words", "no more than six words",
            "one word only", "two words only", "three words only", "four words only",
            "one word and/or a number", "two words and/or a number", "three words and/or a number",

            # Instructions
            "choose no more than", "write no more than", "select no more than",
            "words from the passage", "word from the text", "from the passage for each answer",

            # Task types
            "complete the sentences", "complete the summary", "complete the notes",
            "complete the table", "complete the form", "complete the flow chart",
            "answer the questions below", "fill in the gaps", "write your answers in boxes",
            
            # Form completion specific
            "customer quotation form", "shipping agency", "quotation form",
            "complete the form below", "form below", "quotation",
            
            # Additional patterns for 22-26
            "complete the sentences below",
            "choose one word only",
            "one word only from the passage",
            "write your answers in boxes"
        ]

    def clean_html_styling(self, html_content):
        """Remove HTML styling but keep structure"""
        if not html_content:
            return html_content

        print("[CompletionParser] 🧹 Cleaning HTML styling...")

        # Remove span tags with styling but keep content
        cleaned = re.sub(r'<span[^>]*>', '', html_content)
        cleaned = re.sub(r'</span>', '', cleaned)

        # ENHANCED: Clean up &nbsp; entities and extra spaces
        # Note: We preserve "number + dots" patterns by detecting them BEFORE cleaning
        cleaned = re.sub(r'&nbsp;+', ' ', cleaned)  # Replace multiple &nbsp; with single space
        # Don't normalize ALL spaces - preserve space between number and dots
        # Only normalize multiple spaces to single space, but keep at least one space
        cleaned = re.sub(r' {2,}', ' ', cleaned)  # Normalize multiple spaces to single space
        cleaned = re.sub(r'>\s+<', '><', cleaned)  # Remove spaces between tags
        cleaned = re.sub(r'<p>\s*', '<p>', cleaned)  # Remove spaces after <p>
        cleaned = re.sub(r'\s*</p>', '</p>', cleaned)  # Remove spaces before </p>
        cleaned = re.sub(r'\s*\n\s*', '\n', cleaned)

        return cleaned.strip()

    def detect_ielts_completion_context(self, html_content):
        """Detect IELTS completion keywords in content"""
        if not html_content:
            return False, []

        print("[CompletionParser] 🔍 Detecting IELTS completion context...")

        # Extract plain text for keyword matching
        soup = BeautifulSoup(html_content, 'html.parser')
        plain_text = soup.get_text(separator=' ', strip=True).lower()

        found_keywords = []
        keyword_count = 0

        for keyword in self.ielts_completion_keywords:
            if keyword.lower() in plain_text:
                found_keywords.append(keyword)
                keyword_count += 1

        is_completion = keyword_count > 0

        if found_keywords:
            print(f"[CompletionParser] ✅ IELTS completion keywords found: {found_keywords}")

        print(f"[CompletionParser] 📊 Context Analysis:")
        print(f"  🔍 Keywords matched: {keyword_count}")
        print(f"  🎯 Is completion context: {is_completion}")

        return is_completion, found_keywords

    def extract_question_numbers(self, html_content):
        """Extract question numbers from various HTML elements"""
        if not html_content:
            return []

        print("[CompletionParser] 🔢 Extracting question numbers...")

        # Multiple patterns to catch question numbers in different formats
        question_patterns = [
            r'<strong[^>]*>(\d+)</strong>',  # <strong>22</strong>
            r'<p[^>]*>.*?<strong[^>]*>(\d+)</strong>.*?</p>',  # In paragraph with strong
            r'\b(\d+)\.',  # 22. format
            r'<p[^>]*>.*?(\d+)\s*\..*?</p>',  # Number with dot in paragraph
            r'Question\s+(\d+)-\d+',  # Question 1-8 format
            r'<strong>\s*(\d+)\s*</strong>',  # <strong> 1 </strong> format
            r'<strong>(\d+)</strong>',  # <strong>1</strong> format (no spaces)
            r'(\d+)\s*&hellip;',  # Number followed by &hellip;
            r'<strong>[^<]*?(\d+)[^<]*?</strong>',  # Numbers inside strong tags with other text
        ]

        questions = []
        for pattern in question_patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                if match.isdigit():
                    num = int(match)
                    if 1 <= num <= 50 and num not in questions:
                        questions.append(num)

        # Special handling for "Question 1-8" format
        range_pattern = r'Question\s+(\d+)-(\d+)'
        range_matches = re.findall(range_pattern, html_content)
        for start_match, end_match in range_matches:
            if start_match.isdigit() and end_match.isdigit():
                start_num = int(start_match)
                end_num = int(end_match)
                for num in range(start_num, end_num + 1):
                    if 1 <= num <= 50 and num not in questions:
                        questions.append(num)

        questions.sort()
        print(f"[CompletionParser] 📋 Found questions: {questions}")

        return questions

    def detect_completion_gaps_multi_format(self, html_content):
        """Detect completion gaps in multiple formats - ENHANCED for &hellip; handling"""
        if not html_content:
            return []

        print("[CompletionParser] 🔍 Multi-format gap detection...")

        # ENHANCED patterns to handle &hellip;, dots, and underscores - more specific patterns
        gap_patterns = [
            # Pattern 0: Number followed by dots (e.g., "15 ........................" or "spare 15 ........................")
            # This pattern matches number + spaces/nbsp + dots together
            {'pattern': r'\d+(?:\s|&nbsp;)+\.{4,}', 'name': 'number + dots'},
            # Pattern 0b: Number immediately before dots (no space requirement)
            {'pattern': r'\d+\.{4,}', 'name': 'number + dots (no space)'},
            
            # Pattern 1: Underscore lines (most common in table completion)
            {'pattern': r'_{3,}', 'name': 'underscore lines'},
            
            # Pattern 2: Dotted lines only (preserve numbers) - MOST SPECIFIC for form completion
            {'pattern': r'\.{4,}', 'name': 'dotted lines only'},
            
            # Pattern 3: &hellip; sequences only (preserve numbers)
            {'pattern': r'&hellip;{4,}', 'name': 'hellip sequences only'},
            
            # Pattern 4: Mixed dot patterns (preserve numbers)
            {'pattern': r'(?:\.|&hellip;){4,}', 'name': 'mixed dot patterns'},
        ]

        all_gaps = []

        for pattern_info in gap_patterns:
            pattern = pattern_info['pattern']
            name = pattern_info['name']

            matches = list(re.finditer(pattern, html_content))
            if matches:
                print(f"[CompletionParser] ✅ {name}: Found {len(matches)} gaps")
                all_gaps.extend(matches)
                break  # Use first successful pattern type

        if not all_gaps:
            print("[CompletionParser] ❌ No completion gaps found in any format")
        else:
            print(f"[CompletionParser] 📊 Total gaps detected: {len(all_gaps)}")

        return all_gaps

    def parse_and_insert_inputs(self, html_content):
        """
        ENHANCED MAIN METHOD: IELTS context-aware completion processing

        Args:
            html_content (str): Raw HTML content with any styling

        Returns:
            str: Processed HTML with question-input elements
        """
        if not html_content or not html_content.strip():
            print("[CompletionParser] ⚠️ Empty input - returning unchanged")
            return html_content

        try:
            print("[CompletionParser] 🚀 ENHANCED IELTS COMPLETION PARSER - STARTED")
            print("=" * 70)

            # Step 1: Clean HTML styling
            cleaned_html = self.clean_html_styling(html_content)

            # Step 2: Detect IELTS completion context
            is_completion, found_keywords = self.detect_ielts_completion_context(cleaned_html)

            if not is_completion:
                print("[CompletionParser] ❌ No IELTS completion keywords found - skipping")
                return html_content

            print("[CompletionParser] ✅ IELTS completion context confirmed")

            # Step 3: Detect completion gaps in multiple formats
            gaps = self.detect_completion_gaps_multi_format(cleaned_html)

            if not gaps:
                print("[CompletionParser] ❌ No completion gaps found")
                return html_content

            # Step 4: Extract question numbers WITH context (before each gap)
            # This is the FIX: extract question numbers that appear right before gaps
            question_gap_pairs = []
            gaps.sort(key=lambda x: x.start())
            
            # First, extract all question numbers from the section to use as fallback
            all_question_numbers = self.extract_question_numbers(cleaned_html)
            print(f"[CompletionParser] 📋 All question numbers found in section: {all_question_numbers}")
            
            for gap_idx, gap in enumerate(gaps):
                gap_start = gap.start()
                gap_end = gap.end()
                gap_text = cleaned_html[gap_start:gap_end]
                
                # DEBUG: Print gap info
                print(f"[CompletionParser] 🔍 Processing gap {gap_idx+1} at position {gap_start}: {gap_text[:50]}...")
                
                # Look for question number in multiple ways:
                question_num = None
                
                # Method 1: Check if gap itself contains number (for "15 ........................" format)
                num_in_gap = re.search(r'(\d+)(?:\s|&nbsp;)+\.{4,}', gap_text, re.IGNORECASE)
                if num_in_gap:
                    question_num = int(num_in_gap.group(1))
                    if 1 <= question_num <= 50:
                        question_gap_pairs.append((question_num, gap))
                        print(f"[CompletionParser] 📍 Found Q{question_num} IN gap text at position {gap_start}")
                        continue
                
                # Method 2: Look for number in text before gap (within 150 chars for better coverage)
                pre_gap_text = cleaned_html[max(0, gap_start - 150):gap_start]
                
                # Pattern 1: <strong>number</strong> before gap
                strong_pattern = r'<strong[^>]*>\s*(\d+)\s*</strong>'
                matches = list(re.finditer(strong_pattern, pre_gap_text))
                if matches:
                    question_num = int(matches[-1].group(1))
                    if 1 <= question_num <= 50:
                        question_gap_pairs.append((question_num, gap))
                        print(f"[CompletionParser] 📍 Found Q{question_num} in <strong> before gap at position {gap_start}")
                        continue
                
                # Pattern 2: Number followed by spaces/nbsp, then dots (for "15 ........................" format)
                # Check combined text: pre_gap + gap_text
                combined_text = pre_gap_text + gap_text
                num_before_dots = re.search(r'(\d+)(?:\s|&nbsp;)+\.{4,}', combined_text, re.IGNORECASE)
                if num_before_dots:
                    question_num = int(num_before_dots.group(1))
                    if 1 <= question_num <= 50:
                        question_gap_pairs.append((question_num, gap))
                        print(f"[CompletionParser] 📍 Found Q{question_num} before dots at position {gap_start}")
                        continue
                
                # Pattern 3: Just number followed by spaces/nbsp (within last 50 chars before gap)
                recent_text = pre_gap_text[-50:] if len(pre_gap_text) >= 50 else pre_gap_text
                num_match = re.search(r'(\d+)(?:\s|&nbsp;)+', recent_text, re.IGNORECASE)
                if num_match:
                    question_num = int(num_match.group(1))
                    if 1 <= question_num <= 50:
                        question_gap_pairs.append((question_num, gap))
                        print(f"[CompletionParser] 📍 Found Q{question_num} near gap at position {gap_start}")
                        continue
                
                # Pattern 4: Look for plain number (without spaces requirement) in recent text
                # This handles cases like "spare15" or "strength-16"
                plain_num_match = re.search(r'(\d{1,2})(?:\s|&nbsp;|\.{4,})', recent_text + gap_text[:20], re.IGNORECASE)
                if plain_num_match:
                    question_num = int(plain_num_match.group(1))
                    if 1 <= question_num <= 50:
                        question_gap_pairs.append((question_num, gap))
                        print(f"[CompletionParser] 📍 Found Q{question_num} as plain number at position {gap_start}")
                        continue
                
                # Fallback: Use question numbers from list in order
                if all_question_numbers and gap_idx < len(all_question_numbers):
                    question_num = all_question_numbers[gap_idx]
                    question_gap_pairs.append((question_num, gap))
                    print(f"[CompletionParser] 📍 Using fallback Q{question_num} from question list for gap at position {gap_start}")
                    continue
                
                # If still no number found, add None
                question_gap_pairs.append((None, gap))
                print(f"[CompletionParser] ⚠️ Could not find question number for gap at position {gap_start}")
                print(f"[CompletionParser]   Pre-gap text (last 100 chars): {pre_gap_text[-100:]}")
                print(f"[CompletionParser]   Gap text: {gap_text}")

            if not question_gap_pairs:
                print("[CompletionParser] ❌ No question numbers found before gaps")
                return html_content

            # Step 5: Replace gaps with question inputs
            result_html = cleaned_html
            created_questions = []

            print(f"[CompletionParser] 📍 Processing {len(question_gap_pairs)} question-gap pairs")

            # Process in reverse order for string position stability
            for i, (question_num, gap) in enumerate(reversed(question_gap_pairs)):
                if question_num is None:
                    print(f"[CompletionParser] ⚠️ Skipping gap with no question number")
                    continue

                # EXACT FORMAT: Keep number before gap, put only dots in tag
                # Input: "spare 15 ........................&nbsp;<br />"
                # Output: "spare 15 <question-input data-question-number="15">..............</question-input><br />"
                
                gap_start = gap.start()
                gap_end = gap.end()
                gap_text = result_html[gap_start:gap_end]
                
                # Extract dots from gap (remove everything except dots)
                dots_text = re.sub(r'[^\.]', '', gap_text)
                if len(dots_text) < 10:
                    dots_text = '.' * 14  # Standard 14 dots
                
                # Check if number is in the gap text itself (like "15 ........................")
                num_in_gap_match = re.search(r'(\d+)(?:\s|&nbsp;)+', gap_text, re.IGNORECASE)
                
                if num_in_gap_match:
                    # Number is inside gap - keep it, replace gap with number + tag
                    # Format: "text_before 15 <question-input>...</question-input>"
                    number_part = num_in_gap_match.group(1)
                    # Find where number starts in gap
                    num_start_in_gap = num_in_gap_match.start()
                    # Get text before number in gap (if any)
                    text_before_num_in_gap = gap_text[:num_start_in_gap]
                    # Get text before gap
                    text_before_gap = result_html[:gap_start]
                    
                    # Replace: text_before_gap + text_before_num_in_gap + number + space + tag
                    replacement = text_before_gap + text_before_num_in_gap + f'{number_part} <question-input data-question-number="{question_num}" data-question-type="{self.question_type}">{dots_text}</question-input>'
                    result_html = replacement + result_html[gap_end:]
                else:
                    # Number is before gap - keep it, just replace gap with tag
                    # Look in text before gap (last 50 chars) for the question number
                    text_before_start = max(0, gap_start - 50)
                    text_before = result_html[text_before_start:gap_start]
                    num_before_match = re.search(rf'(?<![0-9])({question_num})(?:\s|&nbsp;)+', text_before, re.IGNORECASE)
                    
                    if num_before_match:
                        # Found the number - keep it, just replace gap with tag
                        # Format: "text_before 15 <question-input>...</question-input>"
                        replacement = result_html[:gap_start] + f'<question-input data-question-number="{question_num}" data-question-type="{self.question_type}">{dots_text}</question-input>'
                        result_html = replacement + result_html[gap_end:]
                    else:
                        # Number not found - just replace gap with tag (number will be in data-question-number)
                        replacement = f'<question-input data-question-number="{question_num}" data-question-type="{self.question_type}">{dots_text}</question-input>'
                        result_html = result_html[:gap_start] + replacement + result_html[gap_end:]

                created_questions.append(question_num)
                print(f"[CompletionParser] ✅ Q{question_num}: Dotted lines → question-input")

            # ENHANCED: Clean up any remaining &hellip; or dot patterns that might have been missed
            print("[CompletionParser] 🧹 Cleaning up remaining dots/hellip patterns...")
            
            # Remove any remaining &hellip; patterns
            result_html = re.sub(r'&hellip;+', '', result_html)
            
            # Remove any remaining dot patterns that are not inside question-input tags
            def clean_dots_outside_inputs(match):
                content = match.group(0)
                # Only clean if not inside question-input tags
                if '<question-input' not in content and '</question-input>' not in content:
                    return re.sub(r'\.{4,}', '', content)
                return content
            
            # Apply cleaning to text outside of question-input tags
            result_html = re.sub(r'[^<]*(?:<question-input[^>]*>.*?</question-input>)?[^<]*', clean_dots_outside_inputs, result_html)

            # FINAL CLEANUP: Ensure clean output format
            print("[CompletionParser] 🧹 Final cleanup for clean output...")
            result_html = re.sub(r'&nbsp;+', ' ', result_html)  # Replace &nbsp; with spaces
            result_html = re.sub(r'\s+', ' ', result_html)  # Normalize spaces
            result_html = re.sub(r'>\s+<', '><', result_html)  # Remove spaces between tags
            result_html = re.sub(r'<p>\s*', '<p>', result_html)  # Clean paragraph tags
            result_html = re.sub(r'\s*</p>', '</p>', result_html)  # Clean paragraph closing tags

            created_questions.sort()

            print("=" * 70)
            print(f"[CompletionParser] 🎉 ENHANCED SUCCESS: {len(created_questions)} inputs created")
            print(f"[CompletionParser] ✅ Questions processed: {created_questions}")
            print(f"[CompletionParser] 🎯 IELTS keywords detected: {len(found_keywords)}")
            print("=" * 70)

            return result_html

        except Exception as e:
            print(f"[CompletionParser] ❌ ERROR: {str(e)}")
            return html_content

def parse_completion_questions(html_string):

    try:
        parser = UniversalCompletionParser()
        result = parser.parse_and_insert_inputs(html_string)

        # Final statistics
        input_pattern = r'<question-input[^>]*data-question-number="(\d+)"[^>]*>'
        all_inputs = re.findall(input_pattern, result, re.IGNORECASE)
        unique_inputs = list(set(all_inputs))
        sorted_unique = sorted([int(x) for x in unique_inputs])

        print(f"[DJANGO-INTEGRATION] 🎉 ENHANCED COMPLETION FINAL REPORT:")
        print(f"[DJANGO-INTEGRATION] ✅ Total inputs created: {len(all_inputs)}")
        print(f"[DJANGO-INTEGRATION] ✅ Questions processed: {sorted_unique}")
        print(
            f"[DJANGO-INTEGRATION] ✅ Status: {'PERFECT' if len(all_inputs) == len(unique_inputs) else 'HAS DUPLICATES'}")
        print(f"[DJANGO-INTEGRATION] 🎯 Parser version: Enhanced IELTS Context-Aware v3.0")

        return result

    except Exception as e:
        print(f"[DJANGO-INTEGRATION] ❌ Critical error: {e}")
        return html_string