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

        # Clean up extra spaces and normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
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
            # Pattern 1: <strong>24__________.</strong> or <strong>24__________</strong> (number followed by underscores/gaps)
            r'<strong[^>]*>(\d+)(?:_{3,}|\.{3,}|&hellip;{3,})[^<]*</strong>',
            # Pattern 2: <strong>22</strong> (standard format)
            r'<strong[^>]*>(\d+)</strong>',
            # Pattern 3: In paragraph with strong
            r'<p[^>]*>.*?<strong[^>]*>(\d+)</strong>.*?</p>',
            # Pattern 4: 22. format
            r'\b(\d+)\.',
            # Pattern 5: Number with dot in paragraph
            r'<p[^>]*>.*?(\d+)\s*\..*?</p>',
        ]

        questions = []
        for pattern in question_patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                if match.isdigit():
                    num = int(match)
                    if 1 <= num <= 50 and num not in questions:
                        questions.append(num)

        questions.sort()
        print(f"[CompletionParser] 📋 Found questions: {questions}")

        return questions

    def detect_completion_gaps_multi_format(self, html_content):
        """Detect completion gaps in multiple formats"""
        if not html_content:
            return []

        print("[CompletionParser] 🔍 Multi-format gap detection...")

        gap_patterns = [
            # Pattern 1: Underscores - HIGHEST PRIORITY (most common in reading completion)
            {'pattern': r'_{10,}', 'name': '10+ underscores'},
            {'pattern': r'_{8,}', 'name': '8+ underscores'},
            {'pattern': r'_{6,}', 'name': '6+ underscores'},
            {'pattern': r'_{5,}', 'name': '5+ underscores'},
            {'pattern': r'_{4,}', 'name': '4+ underscores'},
            {'pattern': r'_{3,}', 'name': '3+ underscores'},
            {'pattern': r'_{2,}', 'name': '2+ underscores'},
            
            # Pattern 2: &hellip; sequences - SECOND PRIORITY
            # IMPORTANT: Match ALL consecutive hellip's (4+), greedy match
            {'pattern': r'(&hellip;(?:&hellip;){3,})', 'name': '4+ hellip (greedy)'},
            {'pattern': r'(&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;)', 'name': '8+ hellip'},
            {'pattern': r'(&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;)', 'name': '6+ hellip'},
            {'pattern': r'(&hellip;&hellip;&hellip;&hellip;)', 'name': '4+ hellip'},

            # Pattern 3: Regular dots - THIRD PRIORITY
            {'pattern': r'(\.{15,})', 'name': '15+ dots'},
            {'pattern': r'(\.{12,})', 'name': '12+ dots'},
            {'pattern': r'(\.{10,})', 'name': '10+ dots'},
            {'pattern': r'(\.{8,})', 'name': '8+ dots'},
            {'pattern': r'(\.{6,})', 'name': '6+ dots'},
            {'pattern': r'(\.{4,})', 'name': '4+ dots'},

            # Pattern 4: Mixed patterns
            {'pattern': r'(?:\.|&hellip;){6,}', 'name': 'Mixed 6+'},
            {'pattern': r'(?:\.|&hellip;){4,}', 'name': 'Mixed 4+'},

            # Pattern 5: Spaced patterns
            {'pattern': r'(?:\.\s*){4,}', 'name': 'Spaced dots 4+'},
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

            # Step 3: SPECIAL CASE - Handle <strong>24__________.</strong> format directly
            # This pattern matches numbers with gaps inside the same <strong> tag
            # Pattern matches: <strong>24__________.</strong> or <strong>24__________</strong>
            strong_with_gap_pattern = r'<strong[^>]*>(\d+)((?:_{3,}|\.{3,}|&hellip;{3,})(?:[.,;:!?])?)</strong>'
            strong_matches = list(re.finditer(strong_with_gap_pattern, cleaned_html))
            
            if strong_matches:
                print(f"[CompletionParser] 🎯 Found {len(strong_matches)} <strong>number+gap</strong> patterns - processing directly")
                result_html = cleaned_html
                created_questions = []
                
                # Process in reverse order to maintain positions
                for match in reversed(strong_matches):
                    question_num = int(match.group(1))
                    gap_content = match.group(2)
                    
                    # Extract trailing punctuation if any
                    trailing_punct = ''
                    if gap_content and gap_content[-1] in '.,;:!?':
                        trailing_punct = gap_content[-1]
                        gap_content = gap_content[:-1]
                    
                    # Create question-input element with trailing punctuation inside if needed
                    if trailing_punct:
                        input_element = f'<strong>{question_num}</strong><question-input data-question-number="{question_num}" data-question-type="{self.question_type}">{self.placeholder}</question-input>{trailing_punct}'
                    else:
                        input_element = f'<strong>{question_num}</strong><question-input data-question-number="{question_num}" data-question-type="{self.question_type}">{self.placeholder}</question-input>'
                    
                    # Replace the entire <strong>number+gap</strong> with <strong>number</strong><question-input>
                    result_html = result_html[:match.start()] + input_element + result_html[match.end():]
                    created_questions.append(question_num)
                    print(f"[CompletionParser] ✅ Q{question_num}: <strong>{question_num}{match.group(2)}</strong> → question-input")
                
                created_questions.sort()
                print("=" * 70)
                print(f"[CompletionParser] 🎉 ENHANCED SUCCESS: {len(created_questions)} inputs created")
                print(f"[CompletionParser] ✅ Questions processed: {created_questions}")
                print("=" * 70)
                return result_html

            # Step 4: Extract question numbers (fallback for other formats)
            questions = self.extract_question_numbers(cleaned_html)

            if not questions:
                print("[CompletionParser] ❌ No valid question numbers found")
                return html_content

            # Step 5: Detect completion gaps in multiple formats
            gaps = self.detect_completion_gaps_multi_format(cleaned_html)

            if not gaps:
                print("[CompletionParser] ❌ No completion gaps found")
                return html_content

            # Step 6: Replace gaps with question inputs
            # Process gaps in reverse order to maintain string positions
            result_html = cleaned_html
            created_questions = []

            print(f"[CompletionParser] 📍 Gap positions: {[g.start() for g in gaps]}")

            # Store gap info with trailing chars before replacement
            gap_replacements = []
            for i, gap in enumerate(reversed(gaps)):
                if i < len(questions):
                    question_index = len(gaps) - 1 - i
                    question_num = questions[question_index] if question_index < len(questions) else questions[i]
                    
                    gap_text = gap.group(0)
                    gap_start = gap.start()
                    gap_end = gap.end()
                    
                    # Check for trailing dots/commas after the gap in original cleaned_html
                    trailing_pattern = r'[,.]+'
                    remaining_text = cleaned_html[gap_end:gap_end+10]
                    trailing_match = re.search(trailing_pattern, remaining_text)
                    
                    trailing_chars = trailing_match.group(0) if trailing_match else ''
                    
                    gap_replacements.append({
                        'start': gap_start,
                        'end': gap_end + len(trailing_chars),
                        'question_num': question_num,
                        'gap_text': gap_text,
                        'trailing_chars': trailing_chars
                    })
            
            # Replace gaps in reverse order (from end to start)
            for replacement in gap_replacements:
                input_element = f'<question-input data-question-number="{replacement["question_num"]}" data-question-type="{self.question_type}">{replacement["gap_text"]}{replacement["trailing_chars"]}</question-input>'
                result_html = result_html[:replacement['start']] + input_element + result_html[replacement['end']:]
                created_questions.append(replacement['question_num'])
                print(f"[CompletionParser] ✅ Q{replacement['question_num']}: Gap → question-input ({replacement['gap_text'][:20]}...{replacement['trailing_chars']})")

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



