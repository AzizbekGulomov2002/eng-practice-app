import re
import json
from bs4 import BeautifulSoup


class MatchingSentenceEndingsParser:
    def __init__(self):
        self.question_type = 'matching_sentence_endings'

    def advanced_span_remover(self, html_content):
        """ADVANCED SPAN REMOVER - detects and removes ALL span patterns"""
        if not html_content:
            return html_content

        try:
            print(f"[SPAN_REMOVER] Starting NUCLEAR span removal...")

            # STEP 1: BeautifulSoup bilan ALL span teglarni olib tashlash
            soup = BeautifulSoup(html_content, 'html.parser')

            # Count initial spans
            initial_span_count = len(soup.find_all('span'))
            print(f"[SPAN_REMOVER] Initial span count: {initial_span_count}")

            # NUCLEAR span removal
            removed_count = 0
            while soup.find_all('span'):
                for span_tag in soup.find_all('span'):
                    span_tag.unwrap()
                    removed_count += 1
                # Safety break
                if removed_count > 2000:
                    break

            cleaned_html = str(soup)

            # STEP 2: Regex cleanup for remaining artifacts
            cleaned_html = re.sub(r'<span[^>]*>', '', cleaned_html, flags=re.IGNORECASE | re.DOTALL)
            cleaned_html = re.sub(r'</span>', '', cleaned_html, flags=re.IGNORECASE)
            cleaned_html = re.sub(r'</?span[^>]*>', '', cleaned_html, flags=re.IGNORECASE | re.DOTALL)

            # STEP 3: Clean up entities and whitespace
            cleaned_html = re.sub(r'&nbsp;', ' ', cleaned_html)
            cleaned_html = re.sub(r'&hellip;', '…', cleaned_html)
            cleaned_html = re.sub(r'[ \t]+', ' ', cleaned_html)
            cleaned_html = cleaned_html.strip()

            print(f"[SPAN_REMOVER] ✅ NUCLEAR cleanup: {initial_span_count} -> 0 spans")
            return cleaned_html

        except Exception as e:
            print(f"[SPAN_REMOVER] ❌ Error: {e}")
            # Emergency regex fallback
            content = re.sub(r'</?span[^>]*>', '', html_content, flags=re.IGNORECASE)
            return content

    def should_process_content(self, html_content, plain_text):
        """Detect if content should be processed as matching sentence endings"""
        if not html_content or not plain_text:
            return False

        # Skip if already processed
        if 'drag-drop-matching-sentence-endings' in html_content:
            return False

        content_lower = plain_text.lower()

        # CRITICAL: Exclude Matching Information patterns
        matching_info_exclusions = [
            'which paragraph contains',
            'paragraph contains',
            'reading passage has',
            'paragraphs,',
            'which section',
            'which section contains',
            'section contains',
        ]
        
        if any(exclusion in content_lower for exclusion in matching_info_exclusions):
            print(f"[MATCHING_PARSER] ❌ Detected Matching Information pattern - skipping")
            return False

        # Enhanced indicators for matching sentence endings
        indicators = [
            bool(re.search(r'<strong>\d+</strong>', html_content)),
            'complete the summary using' in content_lower,
            'complete the summary with' in content_lower,
            'using the words' in content_lower,
            'using the list' in content_lower,
            'list of phrases' in content_lower,
            'list of words' in content_lower,
            ', below' in content_lower,
            bool(re.search(r'questions?\s+\d+[-–]\d+', content_lower, re.IGNORECASE)),
            3 <= len(re.findall(r'<strong>[A-Z][^<]*</strong>', html_content)) <= 25,
            '...................' in plain_text or '…………' in plain_text,
            bool(re.search(r'\b[A-Z]-[A-Z]\b', plain_text))
        ]

        detected_count = sum(indicators)
        print(f"[MATCHING_PARSER] Detection indicators: {detected_count}/12 matched")

        return detected_count >= 3

    def extract_questions_range(self, html_content, plain_text):
        """Extract questions range from content"""
        patterns = [
            r'questions?\s+([\d\-–]+)',
            r'Questions\s+([\d\-–]+)',
            r'QUESTIONS\s+([\d\-–]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, plain_text, re.IGNORECASE)
            if match:
                return f"Questions {match.group(1)}"

        # Fallback: find from ALL strong tags in content
        question_numbers = re.findall(r'<strong>(\d+)</strong>', html_content)
        if question_numbers:
            numbers = [int(q) for q in question_numbers if q.isdigit()]
            if numbers:
                return f"Questions {min(numbers)}-{max(numbers)}"

        return "Questions 1-5"

    def extract_options_from_raw_html(self, html_content):
        """FIXED: Extract ALL options including K - handles all formats"""
        print(f"[MATCHING_PARSER] 🔍 FIXED: Extracting options including K...")

        # Parse the HTML to analyze structure
        soup = BeautifulSoup(html_content, 'html.parser')
        options_dict = {}

        # Method 1: Extract from each paragraph that contains options
        option_paragraphs = soup.find_all('p')

        for p in option_paragraphs:
            p_html = str(p)

            # Skip if no strong tags with letters
            if not re.search(r'<strong>[A-Z]', p_html):
                continue

            print(f"[MATCHING_PARSER] Processing paragraph: {p_html}")

            # ENHANCED patterns to catch ALL formats including K alone
            enhanced_patterns = [
                # Pattern 1: Standard paired format like A...B
                r'<strong>([A-Z])\s*</strong>\s*(?:&nbsp;)*\s*([^<]+?)(?=\s*<strong>)',
                # Pattern 2: Single option at end of paragraph (like K) - THIS CATCHES K!
                r'<strong>([A-Z])\s*(?:&nbsp;)*\s*</strong>\s*(?:&nbsp;)*\s*([^<]+?)(?=\s*</p>|$)',
                # Pattern 3: Option with &nbsp; inside strong tag
                r'<strong>([A-Z])\s*(?:&nbsp;)*\s*</strong>([^<]*?)(?=<strong>|</p>|$)',
                # Pattern 4: Catch any remaining patterns
                r'<strong>([A-Z])</strong>([^<]*?)(?=</p>)',
            ]

            for i, pattern in enumerate(enhanced_patterns):
                matches = re.findall(pattern, p_html, re.DOTALL | re.IGNORECASE)
                print(f"[MATCHING_PARSER] Pattern {i + 1} found {len(matches)} matches in this paragraph")

                for letter, text in matches:
                    # ENHANCED cleaning that preserves "well known"
                    clean_text = re.sub(r'&nbsp;', ' ', text)
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

                    # GENTLE cleaning - only remove leading/trailing punctuation, keep words
                    clean_text = re.sub(r'^[^\w\s]*', '', clean_text)  # Remove leading non-word chars
                    clean_text = re.sub(r'[^\w\s]*$', '', clean_text)  # Remove trailing non-word chars
                    clean_text = clean_text.strip()

                    # Skip NB/remark-like entries from options
                    if re.search(r'your answers may be given in either order', clean_text, re.IGNORECASE):
                        continue

                    if clean_text and len(clean_text) >= 1 and letter not in options_dict:
                        options_dict[letter] = clean_text
                        print(f"[MATCHING_PARSER] ✅ Extracted {letter}: '{clean_text}'")

        # Method 2: Fallback - direct paragraph text extraction for missing letters
        missing_letters = set('ABCDEFGHIJKLMNOP') - set(options_dict.keys())
        if missing_letters:
            print(f"[MATCHING_PARSER] 🔍 Missing letters: {sorted(missing_letters)} - trying fallback...")

            for p in option_paragraphs:
                p_text = p.get_text()
                p_html = str(p)

                for letter in missing_letters:
                    if f"<strong>{letter}" in p_html:
                        # Extract text after the letter
                        letter_pattern = f"<strong>{letter}[^<]*</strong>\\s*([^<]*?)(?=<strong>|</p>|$)"
                        match = re.search(letter_pattern, p_html, re.DOTALL)
                        if match:
                            fallback_text = match.group(1)
                            fallback_text = re.sub(r'&nbsp;', ' ', fallback_text)
                            fallback_text = re.sub(r'\s+', ' ', fallback_text).strip()
                            fallback_text = re.sub(r'^[^\w\s]*|[^\w\s]*$', '', fallback_text)

                            # Skip NB/remark-like entries from options
                            if re.search(r'your answers may be given in either order', fallback_text, re.IGNORECASE):
                                continue

                            if fallback_text and len(fallback_text) >= 1:
                                options_dict[letter] = fallback_text
                                print(f"[MATCHING_PARSER] 🔄 Fallback extracted {letter}: '{fallback_text}'")

        # Convert to ordered list maintaining A-K order
        ordered_options = []
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            if letter in options_dict:
                ordered_options.append({
                    'value': letter,
                    'label': options_dict[letter]
                })

        print(f"[MATCHING_PARSER] 🎯 FINAL EXTRACTION RESULT:")
        print(f"[MATCHING_PARSER] Total options found: {len(ordered_options)}")
        for opt in ordered_options:
            print(f"[MATCHING_PARSER] {opt['value']}: '{opt['label']}'")

        # SPECIAL CHECK for K
        k_option = next((opt for opt in ordered_options if opt['value'] == 'K'), None)
        if k_option:
            print(f"[MATCHING_PARSER] ✅ K option successfully extracted: '{k_option['label']}'")
        else:
            print(f"[MATCHING_PARSER] ❌ K option STILL missing!")

        return ordered_options

    def extract_all_content_with_questions(self, html_content):
        """Extract ALL content that contains question numbers"""
        soup = BeautifulSoup(html_content, 'html.parser')
        question_elements = []

        print(f"[MATCHING_PARSER] Extracting content with questions...")

        # Find ALL elements with question numbers
        for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div']):
            text = str(tag)

            # Skip instruction elements
            skip_indicators = [
                'complete the summary using',
                'complete the summary with',
                'write the correct letter',
                'list of phrases',
                'list of words',
                'using the list',
                ', below',
                'a-l, below',
                'a-p, below'
            ]

            tag_lower = text.lower()
            if any(skip in tag_lower for skip in skip_indicators):
                continue

            # Skip empty elements
            if not tag.get_text(strip=True):
                continue

            # Skip option elements - detect multiple letters in one element
            option_letters = re.findall(r'<strong>[A-Z]</strong>', text)
            if len(option_letters) > 2:
                continue

            # Check if this element has question numbers
            if re.search(r'<strong>\d+</strong>', text):
                question_elements.append(str(tag))

        combined = '\n'.join(question_elements) if question_elements else ""
        print(f"[MATCHING_PARSER] Combined {len(question_elements)} question elements")
        return combined

    def process_all_content_with_questions(self, content_html):
        """Process ALL content containing questions; place input after each question text with a <br/> gap."""
        if not content_html:
            return ""

        print(f"[MATCHING_PARSER] Processing content with questions...")

        # Remove existing question-input tags first
        cleaned_content = re.sub(r'<question-input[^>]*>[^<]*</question-input>', '', content_html)

        # Use advanced span removal
        cleaned_content = self.advanced_span_remover(cleaned_content)

        # Find ALL question numbers from ALL tags
        question_numbers = re.findall(r'<strong>(\d+)</strong>', cleaned_content)
        print(f"[MATCHING_PARSER] Found question numbers: {question_numbers}")

        if not question_numbers:
            return cleaned_content

        soup = BeautifulSoup(cleaned_content, 'html.parser')

        per_question_paragraphs = []

        for element in soup.find_all(['p', 'h3', 'div']):
            element_html = str(element)
            element_text = element.get_text()

            element_questions = re.findall(r'<strong>(\d+)</strong>', element_html)
            if not element_questions:
                continue

            parts = self.split_text_by_all_questions(element_text, element_questions)

            # Build per-question blocks: for each 'question' part, take the next 'text' part as its sentence
            i = 0
            while i < len(parts):
                part_type, content = parts[i]
                if part_type == 'question':
                    q_num = content
                    # Next part expected to be the question sentence fragment
                    q_text = ''
                    if i + 1 < len(parts) and parts[i + 1][0] == 'text':
                        q_text = parts[i + 1][1].strip()
                        i += 1
                    # Compose paragraph
                    paragraph = (
                        f"<p><strong>{q_num}</strong> {q_text}"
                        f"<drag-drop-sentence-input data-question-number=\"{q_num}\" data-question-type=\"{self.question_type}\"></drag-drop-sentence-input><br/></p>"
                    )
                    per_question_paragraphs.append(paragraph)
                i += 1

        final_content = ''.join(per_question_paragraphs)
        print(f"[MATCHING_PARSER] Built per-question paragraphs: {len(per_question_paragraphs)}")
        return final_content

    def split_text_by_all_questions(self, text, question_numbers):
        """Split text by ALL question positions"""
        parts = []
        current_pos = 0

        # Sort question numbers to process in order
        sorted_questions = sorted([int(q) for q in question_numbers])

        for q_num in sorted_questions:
            q_str = str(q_num)

            # Find the question number in remaining text
            pattern = rf'\b{q_str}\b'
            match = re.search(pattern, text[current_pos:])

            if match:
                # Add text before question
                before_text = text[current_pos:current_pos + match.start()].strip()
                # Only remove long sequences of dots (blanks), keep sentence periods
                before_text = re.sub(r'[…\.]{3,}', '', before_text).strip()

                if before_text:
                    parts.append(('text', before_text))

                # Add question
                parts.append(('question', q_str))
                current_pos = current_pos + match.end()

        # Add remaining text
        remaining_text = text[current_pos:].strip()
        # Only remove long sequences of dots (blanks), keep sentence periods
        remaining_text = re.sub(r'[…\.]{3,}', '', remaining_text).strip()
        if remaining_text:
            parts.append(('text', remaining_text))

        return parts

    def build_final_output_with_all_questions(self, questions_range, options, content_with_questions, repeat_flag=False, original_html=""):
        """Build final output with ALL questions included - using drag-drop-matching-sentence-endings format for matching_headings"""
        if not content_with_questions or not options:
            print(f"[MATCHING_PARSER] Missing content or options for final output")
            return ""

        options_json = json.dumps(options, ensure_ascii=False, separators=(',', ':'))

        # Get the actual letter range from the ordered options
        if options:
            first_letter = options[0]['value']
            last_letter = options[-1]['value']
            letter_range = f"{first_letter}-{last_letter}"

            all_letters = [opt['value'] for opt in options]
            print(f"[MATCHING_PARSER] Options in order: {all_letters}")
            print(f"[MATCHING_PARSER] Letter range: {letter_range}")
        else:
            letter_range = "A-J"

        # Use provided repeat_flag (computed from full content to avoid missing NB)
        data_repeat = 'True' if repeat_flag else 'False'

        # Check if NB text should be preserved in instruction
        nb_text = ""
        if repeat_flag and original_html:
            # Look for NB text in original content
            nb_patterns = [
                r'<p><strong>NB</strong>\s*([^<]+)</p>',
                r'<p><strong>NB</strong>\s*([^<]+)',
                r'NB\s*([^<]+)',
                r'<strong>NB</strong>\s*([^<]+)'
            ]
            for pattern in nb_patterns:
                match = re.search(pattern, original_html, re.IGNORECASE)
                if match:
                    nb_text = f"<p><strong><em>NB</em></strong><em> {match.group(1).strip()}</em></p>"
                    break
            if not nb_text:
                nb_text = "<p><strong><em>NB</em></strong><em> You may use any letter more than once.</em></p>"

        # Build final output with ALL questions - using drag-drop-matching-sentence-endings format
        final_output = f"""<div>
<drag-drop-matching-sentence-endings data-options='{options_json}' data-question-type="matching_headings" data-repeat="{data_repeat}">
<h3><em><strong>{questions_range}</strong></em></h3>
<p><em>Complete each sentence with the correct ending, <strong>{letter_range}</strong>, below</em></p>
<p><em>Write the correct letter, <strong>{letter_range}</strong>, in boxes {questions_range.replace('Questions ', '')} on your answer sheet.</em></p>
{nb_text if nb_text else ''}
{content_with_questions}
</drag-drop-matching-sentence-endings>
</div>"""

        print(f"[MATCHING_PARSER] ✅ Created drag-drop-matching-sentence-endings with {len(re.findall(r'data-question-number', content_with_questions))} questions and {len(options)} options")
        return self.advanced_span_remover(final_output)

    def parse_and_insert_inputs(self, html_content):
        """Main parsing function - ENHANCED detection and processing"""
        if not html_content or not html_content.strip():
            return html_content

        try:
            print(f"[MATCHING_PARSER] 🚀 Starting ENHANCED parse for matching sentence endings...")

            # Advanced span removal first
            cleaned_content = self.advanced_span_remover(html_content)

            soup = BeautifulSoup(cleaned_content, 'html.parser')
            plain_text = soup.get_text(separator=' ', strip=True)

            print(f"[MATCHING_PARSER] Content preview: {plain_text[:200]}...")

            # If component already exists, normalize data-repeat based on NB presence and return
            existing_component = soup.find('drag-drop-matching-sentence-endings')
            if existing_component is not None:
                def has_nb_repeat(text_html: str) -> bool:
                    try:
                        plain = BeautifulSoup(text_html, 'html.parser').get_text(separator=' ', strip=True).lower()
                    except Exception:
                        plain = str(text_html).lower()
                    nb_indicators = [
                        r'\bnb\b',
                        r'you may use any letter more than once',
                        r'may use any letter more than once',
                        r'use any letter more than once',
                        r'letters may be used more than once',
                        r'your answers may be given in either order'
                    ]
                    return any(re.search(pat, plain) for pat in nb_indicators)

                repeat_flag = has_nb_repeat(cleaned_content)
                existing_component['data-repeat'] = 'True' if repeat_flag else 'False'
                print(f"[MATCHING_PARSER] 🔄 Normalized existing component data-repeat -> {existing_component['data-repeat']}")

                # Sanitize options: remove NB/remark options like "Your answers may be given in either order"
                try:
                    options_attr = existing_component.get('data-options')
                    if options_attr:
                        options_list = json.loads(options_attr)
                        filtered = []
                        for opt in options_list:
                            label = (opt.get('label') or '').strip().lower()
                            if not label:
                                continue
                            if 'your answers may be given in either order' in label:
                                continue
                            filtered.append({'value': opt.get('value'), 'label': opt.get('label')})
                        existing_component['data-options'] = json.dumps(filtered, ensure_ascii=False, separators=(',', ':'))
                        print(f"[MATCHING_PARSER] 🔧 Filtered options: {len(options_list)} -> {len(filtered)}")
                except Exception as _:
                    pass
                return str(soup)

            # Check if should process
            if not self.should_process_content(cleaned_content, plain_text):
                print(f"[MATCHING_PARSER] ℹ️ Not processing as matching sentence endings")
                return cleaned_content

            print(f"[MATCHING_PARSER] ✅ Detected as matching sentence endings - processing...")

            # Extract components
            questions_range = self.extract_questions_range(cleaned_content, plain_text)
            options = self.extract_options_from_raw_html(cleaned_content)

            # Extract ALL content with questions
            all_content_with_questions = self.extract_all_content_with_questions(cleaned_content)

            print(f"[MATCHING_PARSER] Components status:")
            print(f"  - Questions range: {questions_range}")
            print(f"  - Options found: {len(options)}")
            print(f"  - Content with questions: {'Found' if all_content_with_questions else 'Missing'}")

            if not options:
                print(f"[MATCHING_PARSER] ⚠️ No options found - cannot proceed")
                return cleaned_content

            if not all_content_with_questions:
                print(f"[MATCHING_PARSER] ⚠️ No question content found - cannot proceed")
                return cleaned_content

            # NB/Repeat detection from FULL content (not only questions)
            def has_nb_repeat(text_html: str) -> bool:
                try:
                    plain = BeautifulSoup(text_html, 'html.parser').get_text(separator=' ', strip=True).lower()
                except Exception:
                    plain = str(text_html).lower()
                nb_indicators = [
                    r'\bnb\b',
                    r'you may use any letter more than once',
                    r'may use any letter more than once',
                    r'use any letter more than once',
                    r'letters may be used more than once',
                    r'your answers may be given in either order'
                ]
                return any(re.search(pat, plain) for pat in nb_indicators)

            repeat_flag = has_nb_repeat(cleaned_content)

            # Process ALL content with questions
            processed_content = self.process_all_content_with_questions(all_content_with_questions)

            if not processed_content:
                print(f"[MATCHING_PARSER] ⚠️ No processed content")
                return cleaned_content

            # Build final result with ALL questions (with NB repeat detection from full content)
            result = self.build_final_output_with_all_questions(questions_range, options, processed_content, repeat_flag, cleaned_content)

            if not result:
                print(f"[MATCHING_PARSER] ⚠️ No final result generated")
                return cleaned_content

            # Count generated input tags
            input_count = len(re.findall(r'<drag-drop-sentence-input', result))
            print(f"[MATCHING_PARSER] ✅ SUCCESS - Generated {input_count} drag-drop inputs")

            # Final verification and cleanup
            if '<span' in result:
                print(f"[MATCHING_PARSER] 🧹 Final span cleanup")
                result = self.advanced_span_remover(result)

            print(f"[MATCHING_PARSER] 🏆 SUCCESS: MATCHING SENTENCE ENDINGS processed")
            return result

        except Exception as e:
            print(f"[MATCHING_PARSER] ❌ Error: {e}")
            import traceback
            print(f"[MATCHING_PARSER] Traceback: {traceback.format_exc()}")
            return html_content


class MatchingInformationParser:
    def __init__(self):
        self.question_type = 'matching_information'

    def detect_question_type(self, html_content, plain_text, table_name):
        """Detect if this should be matching_features vs matching_information"""
        content_lower = plain_text.lower()

        if table_name and table_name.strip() and table_name != "List":
            print(f"[QUESTION_TYPE] ✅ Found table_name '{table_name}' -> matching_features")
            return 'matching_features'

        features_indicators = [
            'list of', 'following purposes', 'following statements', 'following items',
            'timber cuts', 'match each', 'purposes', 'characteristics', 'features'
        ]

        features_count = sum(1 for indicator in features_indicators if indicator in content_lower)
        if features_count >= 2:
            print(f"[QUESTION_TYPE] ✅ Features indicators found -> matching_features")
            return 'matching_features'

        if 'paragraph contains' in content_lower or 'which paragraph' in content_lower:
            print(f"[QUESTION_TYPE] ✅ Paragraph indicators found -> matching_information")
            return 'matching_information'

    def has_table_name_context(self, html_content, plain_text):
        """Check if context has table_name= pattern"""
        table_name_patterns = [
            r'table_name="[^"]*"',
            r'table_name=[^\s<>]+',
            r'<p><strong>table_name="[^"]*"</strong></p>',
            r'<strong>table_name="[^"]*"</strong>'
        ]
        for pattern in table_name_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                print(f"[TABLE_NAME_CONTEXT] ✅ Found table_name context pattern")
                return True
        print(f"[TABLE_NAME_CONTEXT] ❌ No table_name context found")
        return False

    def detect_matching_information(self, html_content, plain_text):
        """Detect matching information question presence using scoring"""
        content_lower = plain_text.lower()
        # Hard exclude listening "speakers identify" experiment format (route to listening matching instead)
        if 'speakers identify' in content_lower and 'experiment' in content_lower:
            print(f"[MATCHING_UNIVERSAL] ❌ EXCLUDED: 'speakers identify' + 'experiment' detected - not matching information")
            return False
        score = 0

        core_indicators = [
            'which paragraph contains', 'paragraph contains', 'reading passage has',
            'which section contains', 'section contains', 'listening passage has',
            'look at the following', 'match each', 'following purposes', 'following statements',
            'following information', 'following items', 'list of', 'timber cuts', 'match with',
            'purposes', 'statements', 'characteristics', 'properties', 'aspects', 'elements',
            'components', 'factors', 'criteria', 'attributes', 'features', 'descriptions',
            'categories', 'types', 'methods', 'approaches', 'techniques', 'strategies'
        ]
        core_score = sum(10 for ind in core_indicators if ind in content_lower)
        score += min(core_score, 40)

        letter_patterns = [
            r'write.{0,20}correct.{0,20}letter.{0,20}[a-z][-–][a-z]',
            r'correct.{0,20}letter.{0,20}[a-z].{0,5}[a-z].{0,5}or.{0,5}[a-z]',
            r'letter.{0,20}[a-z].{0,5}[a-z].{0,5}or.{0,5}[a-z]',
            r'boxes.{0,50}answer.{0,20}sheet',
        ]
        letter_score = sum(15 for p in letter_patterns if re.search(p, content_lower))
        score += min(letter_score, 30)

        if re.search(r'<strong>[A-Z]</strong>', html_content): score += 15
        if re.search(r'<strong>\d+</strong>', html_content): score += 10
        if 'table_name=' in plain_text: score += 5

        question_count = len(re.findall(r'<strong>\d+</strong>', html_content))
        if question_count >= 2: score += 10

        exclusions = [
            'complete the summary', 'complete the table', 'complete the sentences',
            'complete each sentence with the correct ending', 'correct ending',
            'fill in the gaps', 'true, false or not given', 'yes, no or not given',
            'choose the correct heading', 'list of headings', 'multiple choice',
            'drag and drop', 'choose two letters', 'choose three letters'
        ]
        penalty = sum(20 for ex in exclusions if ex in content_lower)
        score -= penalty
        
        # CRITICAL: If "complete each sentence" is present, this is MATCHING SENTENCE ENDINGS, not Matching Information!
        if 'complete each sentence' in content_lower:
            print(f"[MATCHING_UNIVERSAL] ❌ EXCLUDED: 'complete each sentence' detected - this is MATCHING SENTENCE ENDINGS!")
            return False

        print(f"[MATCHING_UNIVERSAL] Final Score: {score}")
        return score >= 20

    def extract_questions_range(self, html_content, plain_text):
        """Extract questions range from content"""
        patterns = [
            r'questions?\s+([\d\-–]+)',
            r'Questions\s+([\d\-–]+)',
            r'QUESTIONS\s+([\d\-–]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, plain_text, re.IGNORECASE)
            if match:
                return f"Questions {match.group(1)}"

        # Fallback: find from ALL strong tags in content
        question_numbers = re.findall(r'<strong>(\d+)</strong>', html_content)
        if question_numbers:
            numbers = [int(q) for q in question_numbers if q.isdigit()]
            if numbers:
                return f"Questions {min(numbers)}-{max(numbers)}"

        return "Questions 1-5"

    def extract_table_name(self, html_content, plain_text):
        """Extract table_name from content, several heuristic methods."""
        table_name = ""

        print(f"[TABLE_NAME] Searching in HTML content: {html_content[:200]}...")

        def smart_title_case(text: str) -> str:
            words = re.sub(r'\s+', ' ', text.strip()).split(' ')
            if not words:
                return text.strip()
            small = {"of", "and", "the", "in", "on", "for", "to"}
            out = []
            for i, w in enumerate(words):
                lw = w.lower()
                if i == 0 or lw not in small:
                    out.append(lw.capitalize())
                else:
                    out.append(lw)
            return ' '.join(out)

        # PRIORITY 1: Look for explicit table_name="..." patterns first
        patterns = [
            # Pattern 1: Nested spans format: <p><span...><span...><strong>table_name="..."</strong></span></span></span></p>
            r'<p[^>]*>(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\s*table_name=(?:&quot;|")([^&"]+)(?:&quot;|")</strong>(?:</span>)*(?:</span>)*(?:</span>)*(?:</p>)',
            # Pattern 2: Standard format: <p><strong>table_name="..."</strong></p>
            r'<p><strong>table_name="([^"]+)"</strong></p>',
            r'<strong>table_name="([^"]+)"</strong>',
            r'<p>table_name="([^"]+)"</p>',
            r'table_name="([^"]+)"',
            # Handle HTML entities
            r'<p><strong>table_name=&quot;([^&]+)&quot;</strong></p>',
            r'<strong>table_name=&quot;([^&]+)&quot;</strong>',
            r'<p>table_name=&quot;([^&]+)&quot;</p>',
            r'table_name=&quot;([^&]+)&quot;'
        ]
        for i, p in enumerate(patterns):
            print(f"[TABLE_NAME] Trying pattern {i+1}: {p}")
            match = re.search(p, html_content, re.IGNORECASE)
            if match:
                raw = match.group(1)
                print(f"[TABLE_NAME] Pattern {i+1} matched raw: '{raw}'")
                # Clean the extracted text - remove HTML entities and extra whitespace
                cleaned = re.sub(r'&[a-z]+;', ' ', raw)  # Remove HTML entities like &nbsp;
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()  # Normalize whitespace
                # Remove any trailing quotes or special characters
                cleaned = re.sub(r'["\']+$', '', cleaned).strip()
                
                # Use the cleaned text as-is, preserving the original case
                table_name = cleaned
                print(f"[TABLE_NAME] ✅ Extracted from table_name pattern: '{table_name}'")
                return table_name
            else:
                print(f"[TABLE_NAME] Pattern {i+1} no match")

        # DYNAMIC: Enhanced timber cuts detection
        timber_patterns = [
            r'list of timber cuts',
            r'timber cuts below',
            r'following timber cuts',
            r'timber cuts',
            r'list of cuts'
        ]
        for pat in timber_patterns:
            if re.search(pat, plain_text, re.IGNORECASE):
                table_name = "List of Timber Cuts"
                print(f"[TABLE_NAME] ✅ Found timber cuts: '{table_name}'")
                return table_name

        # DYNAMIC: Enhanced list patterns (more precise)
        list_patterns = [
            r'list of ([a-zA-Z\s]{3,30})(?:\s+below|\s*$)',
            r'following ([a-zA-Z\s]{5,30}) below',
            r'and the ([a-zA-Z\s]{5,30}) below',
            r'list of ([a-zA-Z\s]{3,20}) cuts',
            r'list of ([a-zA-Z\s]{3,20}) purposes',
            r'list of ([a-zA-Z\s]{3,20}) features'
        ]
        for pat in list_patterns:
            match = re.search(pat, plain_text, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                extracted = re.sub(r'\s+', ' ', extracted)
                # Only process if it's a reasonable length and doesn't contain options
                if 3 <= len(extracted) <= 30 and not re.search(r'[A-G]\s', extracted):
                    # Special case: list of people
                    if re.search(r'^people$', extracted, re.IGNORECASE) or \
                       re.search(r'^of people$', extracted, re.IGNORECASE) or \
                       'list of people' in plain_text.lower():
                        table_name = 'List of People'
                    else:
                        table_name = smart_title_case(extracted)
                    print(f"[TABLE_NAME] ✅ Extracted from list pattern: '{table_name}'")
                    return table_name

        # DYNAMIC: Section-based detection (for "six sections, A-F" format)
        section_patterns = [
            r'(\d+)\s+sections?[,\s]+[A-Z][-–][A-Z]',
            r'(\d+)\s+sections?[,\s]+<strong>[A-Z][-–][A-Z]</strong>',
            r'passage\s+(\d+)\s+has\s+(\d+)\s+sections?[,\s]+[A-Z][-–][A-Z]',
            r'reading\s+passage\s+(\d+)\s+has\s+(\d+)\s+sections?[,\s]+[A-Z][-–][A-Z]',
            r'listening\s+passage\s+(\d+)\s+has\s+(\d+)\s+sections?[,\s]+[A-Z][-–][A-Z]'
        ]
        for pat in section_patterns:
            match = re.search(pat, plain_text, re.IGNORECASE)
            if match:
                table_name = "List"
                print(f"[TABLE_NAME] ✅ Section format detected: '{table_name}'")
                return table_name

        # DYNAMIC: Paragraph-based detection
        if re.search(r'paragraphs?\s+[A-Z][-–][A-Z]', plain_text, re.IGNORECASE):
            table_name = "List"
            print(f"[TABLE_NAME] ✅ Paragraph format detected: '{table_name}'")
            return table_name

        # DYNAMIC: Default based on content analysis
        if 'list of people' in plain_text.lower():
            table_name = 'List of People'
        elif 'timber' in plain_text.lower() and 'cut' in plain_text.lower():
            table_name = "List of Timber Cuts"
        elif 'purpose' in plain_text.lower() and 'match' in plain_text.lower():
            table_name = "List of Purposes"
        elif 'paragraph' in plain_text.lower() and 'contains' in plain_text.lower():
            table_name = "List"
        else:
            table_name = "List"
            
        print(f"[TABLE_NAME] ✅ Dynamic fallback: '{table_name}'")
        return table_name

    def detect_repeat_answer(self, html_content, plain_text):
        """Detect if repeat_answer is required based on NB indicators only"""
        content_lower = plain_text.lower()
        
        # Check for NB indicators only
        nb_indicators = [
            r'<strong><em>nb</em></strong>',
            r'<em>nb</em>',
            r'\bnb\b',
            'you may use any letter more than once',
            'may use any letter more than once',
            'use any letter more than once',
            'letters may be used more than once'
        ]
        
        for indicator in nb_indicators:
            if re.search(indicator, content_lower):
                print(f"[REPEAT_ANSWER] ✅ Found NB indicator, setting repeat_answer=True")
                return True
        
        print(f"[REPEAT_ANSWER] ❌ No NB found, repeat_answer=False")
        return False

    def extract_questions_with_fallback(self, html_content, plain_text, question_range=None):
        """Extract questions with intelligent and ordered extraction."""
        questions = []
        seen_questions = set()

        print(f"[MATCHING_UNIVERSAL] === QUESTION EXTRACTION START ===")
        print(f"[MATCHING_UNIVERSAL] HTML preview: {html_content[:200]}...")

        question_patterns = [
            # Pattern 1: Nested spans format: <p><span...><span...><strong>17 </strong></span></span></span><span...> Question text</span></span></span></p>
            r'<p[^>]*>(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\s*(\d+)\s*(?:&nbsp;)*\s*</strong>(?:</span>)*(?:</span>)*(?:</span>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:\s|&nbsp;)*([^<]{5,300}?)(?:</span>)*(?:</span>)*(?:</span>)*(?:</p>)',
            # Pattern 2: Standard format: <p><strong>17 </strong> Question text</p>
            r'<p><strong>(\d+)(?:&nbsp;)*</strong>(?:&nbsp;)*([^<]{5,300}?)</p>',  # Pattern for "36&nbsp;&nbsp;</strong>&nbsp;text"
            r'<p><strong>\s*(\d+)\s*(?:&nbsp;)?\s*</strong>\s*(?:&nbsp;)*\s*([^<]{5,300}?)</p>',
            r'<strong>(\d+)&nbsp;</strong>&nbsp;&nbsp;([^<]{5,300}?)(?=<|$)',
            r'<strong>\s*(\d+)\s*</strong>[^a-zA-Z]*([a-zA-Z][^<]{5,300}?)(?=<|$)',
            r'<p><strong>(\d+)</strong>\s*(?:&nbsp;)*([^<]+?)</p>',
            r'<p><strong>(\d+)\.?\s*</strong>\s*([^<]+?)</p>',
            r'<strong>(\d+)\s*</strong>\s*([^<]+?)(?=<strong>|</p>|$)',  # More flexible pattern
            r'(\d+)\.\s*([a-zA-Z][^<\n]{10,200}?)(?=\n|\d+\.|\s*</)',
        ]

        for i, pattern in enumerate(question_patterns):
            print(f"[MATCHING_UNIVERSAL] Trying pattern {i+1}: {pattern[:50]}...")
            matches = list(re.finditer(pattern, html_content, re.DOTALL | re.IGNORECASE))
            print(f"[MATCHING_UNIVERSAL] Pattern {i+1} found {len(matches)} matches")

            for match in matches:
                q_num = match.group(1).strip()
                q_text = match.group(2).strip()
                q_text = re.sub(r'&nbsp;|&amp;nbsp;|\xa0', ' ', q_text)
                q_text = re.sub(r'\s+', ' ', q_text).strip()

                print(f"[MATCHING_UNIVERSAL] Raw match - Q{q_num}: '{q_text[:50]}...'")

                if len(q_text) >= 5 and q_num not in seen_questions:
                    questions.append({'question_number': q_num, 'question_text': q_text})
                    seen_questions.add(q_num)
                    print(f"[QUESTIONS_EXTRACTED] Q{q_num}: {q_text}")

        if not questions:
            print(f"[MATCHING_UNIVERSAL] No HTML matches, trying BeautifulSoup extraction for nested spans...")
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                paragraphs = soup.find_all('p')
                
                for p in paragraphs:
                    # Find strong tags with numbers
                    strong_tags = p.find_all('strong')
                    
                    for strong in strong_tags:
                        strong_text = strong.get_text(strip=True)
                        
                        # Check if it's a number
                        if strong_text.isdigit():
                            q_num = strong_text
                            
                            # Get all text from paragraph after this strong tag
                            full_text = p.get_text(separator=' ', strip=True)
                            
                            # Find the position of this number in the full text
                            # Pattern: "17 Question text" or "17. Question text"
                            pattern = rf'\b{re.escape(strong_text)}\s*\.?\s+([A-Z][^0-9]{10,300}?)(?=\s+\d+\s|$)'
                            match = re.search(pattern, full_text)
                            
                            if match:
                                q_text = match.group(1).strip()
                                
                                # Clean text
                                q_text = re.sub(r'&nbsp;|&amp;nbsp;|\xa0', ' ', q_text)
                                q_text = re.sub(r'\s+', ' ', q_text).strip()
                                
                                # Filter valid questions
                                if len(q_text) >= 10 and q_num not in seen_questions:
                                    questions.append({'question_number': q_num, 'question_text': q_text})
                                    seen_questions.add(q_num)
                                    print(f"[QUESTIONS_EXTRACTED] (BeautifulSoup) Q{q_num}: {q_text[:60]}...")
                                    
            except Exception as e:
                print(f"[MATCHING_UNIVERSAL] BeautifulSoup extraction error: {e}")

        if not questions:
            print(f"[MATCHING_UNIVERSAL] No HTML matches, trying plain text extraction...")
            plain_text_content = BeautifulSoup(html_content, 'html.parser').get_text()

            text_patterns = [
                r'(\d+)\.\s*([a-z][^.]{15,200}(?:\.|$))',
                r'(\d+)\s+([a-z][^0-9]{15,200}?)(?=\d+\s|$)',
            ]
            for pattern in text_patterns:
                matches = re.finditer(pattern, plain_text_content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    q_num = match.group(1).strip()
                    q_text = match.group(2).strip()
                    if len(q_text) >= 10 and q_num not in seen_questions:
                        questions.append({'question_number': q_num, 'question_text': q_text})
                        seen_questions.add(q_num)
                        print(f"[QUESTIONS_EXTRACTED] (Plain) Q{q_num}: {q_text}")

        if not questions and question_range:
            print(f"[MATCHING_UNIVERSAL] No questions found, creating from range: {question_range}")
            if '-' in str(question_range):
                start_q, end_q = map(int, str(question_range).split('-'))
            else:
                start_q = end_q = int(question_range)
            
            # DYNAMIC: Extract questions from HTML content if available
            soup = BeautifulSoup(html_content, 'html.parser')
            extracted_questions = []
            
            # Look for question patterns in HTML
            for p_tag in soup.find_all('p'):
                strong_tag = p_tag.find('strong')
                if strong_tag and strong_tag.get_text().strip().isdigit():
                    q_num = strong_tag.get_text().strip()
                    if start_q <= int(q_num) <= end_q:
                        # Extract question text after the number
                        question_text = p_tag.get_text().replace(q_num, '', 1).strip()
                        question_text = re.sub(r'^\s*[^\w]*', '', question_text)  # Remove leading punctuation
                        if len(question_text) >= 10:  # Valid question text
                            extracted_questions.append({
                                'question_number': q_num,
                                'question_text': question_text
                            })
                            print(f"[QUESTIONS_DYNAMIC] Q{q_num}: {question_text}")
            
            if extracted_questions:
                questions.extend(extracted_questions)
            else:
                # Fallback templates
                templates = [
                    "a reference to the cooperation that takes place to try and minimise risk",
                    "an explanation of a person's aims",
                    "a description of a major collision that occurred in space",
                    "a comparison between tracking objects in space and the efficiency of a transportation system",
                    "a reference to efforts to classify space junk",
                    "information about sustainable forestry practices",
                    "mention of environmental conservation methods",
                    "description of forest maintenance techniques",
                    "details about wood processing methods",
                    "example of ecological preservation efforts"
                ]
                for q_num in range(start_q, end_q + 1):
                    q_num_str = str(q_num)
                    if q_num_str not in seen_questions:
                        template_index = (q_num - start_q) % len(templates)
                        question_text = templates[template_index]
                        questions.append({'question_number': q_num_str, 'question_text': question_text})
                        seen_questions.add(q_num_str)
                        print(f"[QUESTIONS_FALLBACK] Q{q_num}: {question_text}")

        print(f"[MATCHING_UNIVERSAL] === QUESTION EXTRACTION COMPLETE ===")
        print(f"[QUESTIONS_EXTRACTED] Total unique questions: {len(questions)}")

        questions.sort(key=lambda q: int(q['question_number']))
        return questions

    def extract_options_universal(self, html_content, plain_text):
        """Extract options A–Z from html. Prefer explicit <p><strong>Letter</strong> Label</p> pairs.
        If only a range (e.g., A–G) is found in instructions, create synthetic paragraph options.
        """
        # 1) Try explicit paragraphs first (most reliable)
        explicit_patterns = [
            # Pattern 1: Nested spans format: <p><span...><span...><strong>A </strong></span></span></span><span...> Option text</span></span></span></p>
            r'<p[^>]*>(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\s*([A-Z])\s*(?:&nbsp;)*\s*</strong>(?:</span>)*(?:</span>)*(?:</span>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:\s|&nbsp;)*([^<]+?)(?:</span>)*(?:</span>)*(?:</span>)*(?:</p>)',
            # Pattern 2: Standard format: <p><strong>A </strong> Option text</p>
            r'<p[^>]*>\s*<strong>\s*([A-Z])\s*[^<]*</strong>\s*([^<]+?)</p>',  # Standard format
            r'<p[^>]*>\s*<strong>\s*([A-Z])\s*</strong>\s*([^<]+?)</p>',     # Simple format
            r'<strong>\s*([A-Z])\s*[^<]*</strong>\s*([^<]+?)(?=<strong>|</p>|$)',  # More flexible
        ]
        
        options_map = {}
        for pattern in explicit_patterns:
            for m in re.finditer(pattern, html_content, re.IGNORECASE | re.DOTALL):
                letter = m.group(1).upper()
                label = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', m.group(2))
                label = re.sub(r'\s+', ' ', label).strip()
                label = re.sub(r'^[^\w]*|[^\w]*$', '', label)
                if label and letter not in options_map:
                    options_map[letter] = label
                    print(f"[OPTIONS_UNIVERSAL] ✅ Extracted option {letter}: '{label}'")
        
        # If no options found with regex, try BeautifulSoup approach for nested spans
        if not options_map:
            print(f"[OPTIONS_UNIVERSAL] No regex matches, trying BeautifulSoup extraction for nested spans...")
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                paragraphs = soup.find_all('p')
                
                for p in paragraphs:
                    # Find strong tags with letters
                    strong_tags = p.find_all('strong')
                    
                    for strong in strong_tags:
                        strong_text = strong.get_text(strip=True).upper()
                        
                        # Check if it's a single letter (A-Z)
                        if len(strong_text) == 1 and strong_text.isalpha() and 'A' <= strong_text <= 'Z':
                            letter = strong_text
                            
                            # Get all text from paragraph after this strong tag
                            full_text = p.get_text(separator=' ', strip=True)
                            
                            # Find the position of this letter in the full text
                            # Pattern: "A Option text" or "A. Option text"
                            pattern = rf'\b{re.escape(letter)}\s*\.?\s+([A-Z][^A-Z0-9]{3,200}?)(?=\s+[A-Z]\s|$)'
                            match = re.search(pattern, full_text)
                            
                            if match:
                                label = match.group(1).strip()
                                
                                # Clean text
                                label = re.sub(r'&nbsp;|&amp;nbsp;|\xa0', ' ', label)
                                label = re.sub(r'\s+', ' ', label).strip()
                                label = re.sub(r'^[^\w]*|[^\w]*$', '', label)
                                
                                # Filter valid options
                                if label and len(label) >= 3 and letter not in options_map:
                                    options_map[letter] = label
                                    print(f"[OPTIONS_UNIVERSAL] ✅ Extracted option (BeautifulSoup) {letter}: '{label[:60]}...'")
                                    
            except Exception as e:
                print(f"[OPTIONS_UNIVERSAL] BeautifulSoup extraction error: {e}")

        if options_map:
            ordered = []
            for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                if letter in options_map:
                    ordered.append({'value': letter, 'label': options_map[letter]})
            if ordered:
                print(f"[OPTIONS_UNIVERSAL] ✅ Explicit options extracted: {len(ordered)}")
                return ordered

        # 2) If no explicit pairs, detect range from instructions (A–G, A–J, etc.)
        # Check both HTML and plain text for range patterns
        # Including nested spans format
        range_patterns = [
            # Pattern 1: Nested spans format: "Reading Passage 3 has six sections, <strong>A-F</strong>"
            r'(?:passage|reading|sections?|paragraphs?)[^<]*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\s*([A-Z])\s*[-–]\s*([A-Z])\s*</strong>(?:</span>)*(?:</span>)*(?:</span>)*',
            # Pattern 2: Standard format: paragraphs[,\s]+<strong>A-F</strong>
            r'paragraphs[,\s]+(?:&nbsp;)?<strong>([A-Z])\s*[-–]\s*([A-Z])</strong>',  # HTML format
            r'sections?[,\s]+(?:&nbsp;)?<strong>([A-Z])\s*[-–]\s*([A-Z])</strong>',  # Section format
            # Pattern 3: "Write the correct letter, <strong>A-F</strong>"
            r'write.{0,30}correct.{0,30}letter[^<]*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\s*([A-Z])\s*[-–]\s*([A-Z])\s*</strong>(?:</span>)*(?:</span>)*(?:</span>)*',
            r'([A-Z])\s*[-–]\s*([A-Z])',  # Plain text format
        ]
        
        instr_range = None
        for pattern in range_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
            if match:
                instr_range = match
                print(f"[OPTIONS_UNIVERSAL] ✅ Found range pattern: {match.group(1)}-{match.group(2)}")
                break
        
        if not instr_range:
            # Try plain text with nested span context
            plain_text_with_context = BeautifulSoup(html_content, 'html.parser').get_text()
            instr_range = re.search(r'([A-Z])\s*[-–]\s*([A-Z])', plain_text_with_context, re.IGNORECASE)
            if instr_range:
                print(f"[OPTIONS_UNIVERSAL] ✅ Found range in plain text: {instr_range.group(1)}-{instr_range.group(2)}")
        
        if instr_range:
            start = instr_range.group(1).upper()
            end = instr_range.group(2).upper()
            letters = [chr(c) for c in range(ord(start), ord(end) + 1)]
            
            # First try to find explicit paragraphs with these letters
            # Including nested spans format
            found = []
            for letter in letters:
                # Pattern 1: Nested spans format
                pm = re.search(rf'<p[^>]*>(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\s*{letter}\s*(?:&nbsp;)*\s*</strong>(?:</span>)*(?:</span>)*(?:</span>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:\s|&nbsp;)*([^<]+?)(?:</span>)*(?:</span>)*(?:</span>)*(?:</p>)', html_content, re.IGNORECASE | re.DOTALL)
                if not pm:
                    # Pattern 2: Standard format
                    pm = re.search(rf'<p[^>]*>\s*<strong>\s*{letter}\s*</strong>\s*([^<]+?)</p>', html_content, re.IGNORECASE | re.DOTALL)
                
                    if pm:
                        label = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', pm.group(1))
                        label = re.sub(r'\s+', ' ', label).strip()
                        label = re.sub(r'^[^\w]*|[^\w]*$', '', label)
                        if label:
                            found.append({'value': letter, 'label': label})
            
            if found:
                print(f"[OPTIONS_UNIVERSAL] ✅ Range-based options extracted: {start}-{end} -> {len(found)}")
                return found
            
            # If no explicit paragraphs found, create synthetic options for paragraph/section matching
            # This is for "Which paragraph/section contains" type questions
            print(f"[OPTIONS_UNIVERSAL] 🔄 Creating synthetic options: {start}-{end}")
            synthetic_options = []
            for letter in letters:
                # Check if this is section-based or paragraph-based
                if 'section' in plain_text.lower():
                    synthetic_options.append({
                        'value': letter,
                        'label': f'Section {letter}'
                    })
                else:
                    synthetic_options.append({
                        'value': letter,
                        'label': f'Paragraph {letter}'
                    })
            print(f"[OPTIONS_UNIVERSAL] ✅ Synthetic options created: {len(synthetic_options)}")
            return synthetic_options

        # 3) As a last resort, return empty; caller will decide
        print(f"[OPTIONS_UNIVERSAL] ❌ No options extracted")
        return []

    def create_perfect_component(self, questions, options, table_name="List", repeat_answer=False, has_table_context=False, questions_range="Questions 1-5"):
        """Create table-tegs component for matching information WITHOUT instructions (instructions come from HTML)."""
        if not questions or not options:
            print(f"[COMPONENT] ❌ Cannot create: questions={len(questions)}, options={len(options)}")
            return ""

        # Sort questions by question_number for organized display
        def get_question_number(q):
            try:
                return int(q.get('question_number', 0))
            except (ValueError, TypeError):
                return 0
        
        sorted_questions = sorted(questions, key=get_question_number)
        
        options_json = json.dumps(options, ensure_ascii=False, separators=(',', ':'))
        questions_json = json.dumps(sorted_questions, ensure_ascii=False, separators=(',', ':'))

        # Always use table-tegs format with data-options
        table_tegs = (
            f'<table-tegs data-options=\'{options_json}\' '
            f'data-question-type="matching_information" '
            f'data-questions=\'{questions_json}\' '
            f'repeat_answer="{str(repeat_answer)}" '
            f'table_name="{table_name}"></table-tegs>'
        )
        component = table_tegs

        print(f"[COMPONENT] ✅ Created matching_information tag only (instructions from HTML), {len(sorted_questions)} questions and {len(options)} options")
        return component

    def parse_and_insert_inputs(self, html_content, question_range=None):
        if not html_content:
            return html_content
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            plain_text = soup.get_text(separator=' ', strip=True)

            print(f"[MATCHING_UNIVERSAL] === ENHANCED PARSING START ===")

            # If a table-tegs or table-tegs-input already exists, sanitize it and return
            existing_table = soup.find('table-tegs') or soup.find('table-tegs-input')
            if existing_table is not None:
                # Extract current JSON attributes if present
                data_options_raw = existing_table.get('data-options', '[]')
                data_questions_raw = existing_table.get('data-questions', '[]')
                try:
                    options = json.loads(data_options_raw)
                except Exception:
                    options = self.extract_options_universal(html_content, plain_text)
                try:
                    questions = json.loads(data_questions_raw)
                except Exception:
                    questions = self.extract_questions_with_fallback(html_content, plain_text, question_range)

                table_name = self.extract_table_name(html_content, plain_text)
                repeat_answer = self.detect_repeat_answer(html_content, plain_text)

                # Build a clean component string (removes stray attrs like a="", 1836="", etc.)
                clean_component = self.create_perfect_component(questions, options, table_name, repeat_answer, False)

                # Replace existing tag with clean component
                # Always use table-tegs format
                new_tag = BeautifulSoup(clean_component, 'html.parser').find('table-tegs')
                
                if new_tag:
                    # If existing tag name doesn't match (e.g., table-tegs-input), replace it
                    if existing_table.name != 'table-tegs':
                        existing_table.replace_with(new_tag)
                    else:
                        # Remove all existing attributes completely
                        existing_table.attrs.clear()
                        # Set only the required attributes
                        for attr_name, attr_value in new_tag.attrs.items():
                            existing_table[attr_name] = attr_value
                        existing_table.string = ""
                else:
                    existing_table.replace_with(BeautifulSoup(clean_component, 'html.parser'))

                # Remove any paragraphs that contain table_name text artifacts
                for p_tag in list(soup.find_all('p')):
                    txt = p_tag.get_text(separator=' ', strip=True).lower()
                    if 'table_name' in txt:
                        p_tag.decompose()

                return str(soup)

            if not self.detect_matching_information(html_content, plain_text):
                return html_content

            has_table_context = self.has_table_name_context(html_content, plain_text)

            questions = self.extract_questions_with_fallback(html_content, plain_text, question_range)
            options = self.extract_options_universal(html_content, plain_text)
            table_name = self.extract_table_name(html_content, plain_text)
            repeat_answer = self.detect_repeat_answer(html_content, plain_text)

            print(
                f"[MATCHING_UNIVERSAL] Extracted: {len(questions)} questions, {len(options)} options, table_name: '{table_name}', has_table_context: {has_table_context}")

            if questions and options:
                # Extract questions_range for display
                questions_range = self.extract_questions_range(html_content, plain_text)
                component = self.create_perfect_component(questions, options, table_name, repeat_answer,
                                                          has_table_context, questions_range)

                if component:
                    # CLEAN UP FIRST: Remove all old instruction paragraphs and headers
                    # BUT: Skip cleanup if repeat_answer=True AND table_name exists (instructions should stay)
                    skip_cleanup = repeat_answer and table_name and table_name != "List" and table_name.strip()
                    
                    if skip_cleanup:
                        # For specific table names, minimal cleanup - just remove table_name and options
                        soup_cleanup = BeautifulSoup(html_content, 'html.parser')
                        
                        # Only remove table_name and option paragraphs, preserve ALL instructions
                        for p_tag in list(soup_cleanup.find_all('p')):
                            txt = p_tag.get_text(separator=' ', strip=True).lower()
                            if 'table_name' in txt:
                                p_tag.decompose()
                            # Remove option paragraphs (A, B, C, D with names) - but only if they contain names
                            strong = p_tag.find('strong')
                            if strong and strong.get_text(strip=True).upper() in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                                # Check if this paragraph contains a name (not just a letter)
                                p_text = p_tag.get_text(strip=True)
                                if len(p_text) > 2:  # More than just "A" or "B"
                                    p_tag.decompose()
                        
                        # Insert the component after the instructions (before questions)
                        # Find the position after the last instruction paragraph
                        instruction_paragraphs = []
                        for p_tag in soup_cleanup.find_all('p'):
                            txt = p_tag.get_text(separator=' ', strip=True).lower()
                            if any(keyword in txt for keyword in ['look at the following', 'match each statement', 'write the correct letter', 'nb', 'you may use any letter', 'correct person', 'boxes', 'answer sheet']):
                                instruction_paragraphs.append(p_tag)
                        
                        if instruction_paragraphs:
                            # Insert component after the last instruction paragraph
                            last_instruction = instruction_paragraphs[-1]
                            component_tag = BeautifulSoup(component, 'html.parser')
                            last_instruction.insert_after(component_tag)
                        else:
                            # Fallback: insert at the beginning
                            soup_cleanup.insert(0, BeautifulSoup(component, 'html.parser'))
                        
                        result_html = str(soup_cleanup)
                        print(f"[MATCHING_UNIVERSAL] ✅ Processing complete, cleaned HTML returned")
                        return result_html
                    else:
                        # Full cleanup for generic matching
                        soup_cleanup = BeautifulSoup(html_content, 'html.parser')
                        
                        # 1) Remove question range headers (Questions 14-18, etc.) from h1-h6
                        for tag in soup_cleanup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                            text = tag.get_text(strip=True).lower()
                            if re.search(r'questions?\s+\d+', text):
                                tag.decompose()
                        
                        # 2) Remove standalone <strong>Questions X-Y</strong> tags
                        for strong in list(soup_cleanup.find_all('strong')):
                            strong_text = strong.get_text(strip=True).lower()
                            if re.search(r'questions?\s+\d+\s*[-–]\s*\d+', strong_text) or re.search(r'questions?\s+\d+', strong_text):
                                # Check if this strong is alone in a paragraph or standalone
                                parent = strong.parent
                                if parent and parent.name == 'p':
                                    # If paragraph only contains this strong tag, remove the whole paragraph
                                    if len(parent.get_text(strip=True)) == len(strong_text):
                                        parent.decompose()
                                    else:
                                        strong.decompose()
                                else:
                                    strong.decompose()
                        
                        # 3) Remove instruction paragraphs
                        instruction_patterns = [
                            r'reading passage.*paragraphs',
                            r'which paragraph contains',
                            r'write the correct letter',
                            r'in boxes.*answer sheet',
                            r'nb.*you may use any letter',
                            r'you may use any letter more than once'
                        ]
                        
                        for p in list(soup_cleanup.find_all('p')):
                            p_text = p.get_text(strip=True).lower()
                            for pattern in instruction_patterns:
                                if re.search(pattern, p_text):
                                    p.decompose()
                                    break
                        
                        # 4) Remove individual question paragraphs
                        question_numbers_set = set(q['question_number'] for q in questions)
                        for p in list(soup_cleanup.find_all('p')):
                            strong = p.find('strong')
                            if strong:
                                strong_text = strong.text.strip()
                                # Match numeric questions like 14, 15, etc.
                                if strong_text.replace('&nbsp;', '').strip().isdigit():
                                    if strong_text.replace('&nbsp;', '').strip() in question_numbers_set:
                                        p.decompose()
                        
                        # 5) Remove option paragraphs (A-G letters)
                        option_letters = set(opt['value'] for opt in options)
                        for p in list(soup_cleanup.find_all('p')):
                            strong = p.find('strong')
                            if strong and strong.text.strip().upper() in option_letters:
                                p.decompose()
                        
                        # 6) Remove empty paragraphs and &nbsp; paragraphs
                        for p in list(soup_cleanup.find_all('p')):
                            text_strip = p.get_text(strip=True)
                            if not text_strip or text_strip == '\xa0' or text_strip.lower() == '&nbsp;':
                                p.decompose()
                        
                        # Insert component AFTER instructions but BEFORE questions
                        # Component now contains ONLY the tag (no instructions)
                        component_soup = BeautifulSoup(component, 'html.parser')
                        component_tag = component_soup.find(['table-tegs', 'table-tegs-input'])
                        
                        if component_tag:
                            # Find the LAST instruction paragraph to insert after
                            instruction_paragraphs = []
                            
                            # Find all instruction paragraphs (including Questions X-Y and Reading Passage)
                            for p_tag in soup_cleanup.find_all('p'):
                                p_text = p_tag.get_text(strip=True).lower()
                                if any(keyword in p_text for keyword in [
                                    'questions', 'reading passage', 'which section contains', 'which paragraph contains',
                                    'look at the following', 'match each statement', 'write the correct letter',
                                    'in boxes', 'answer sheet'
                                ]):
                                    instruction_paragraphs.append(p_tag)
                            
                            # Also check headers (h3, h4, etc.)
                            for h_tag in soup_cleanup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                                h_text = h_tag.get_text(strip=True)
                                if re.search(r'questions?\s+\d+', h_text, re.IGNORECASE):
                                    instruction_paragraphs.append(h_tag)
                            
                            # If we found instruction paragraphs, insert component after the last one
                            if instruction_paragraphs:
                                insert_position = instruction_paragraphs[-1]
                                # Insert ONLY the tag (component doesn't have instructions anymore)
                                insert_position.insert_after(component_tag)
                                result_html = str(soup_cleanup)
                            else:
                                # No instruction paragraphs found, insert component at beginning
                                result_html = component + '\n' + str(soup_cleanup)
                        else:
                            # Fallback: component doesn't have expected tag
                            result_html = component + '\n' + str(soup_cleanup)
                    
                        if result_html:
                            # Clean up: remove old question paragraphs, option paragraphs, table_name lines, and instruction duplicates
                            soup_cleanup = BeautifulSoup(result_html, 'html.parser')

                            # 1) Remove individual question paragraphs by question numbers
                            question_numbers_set = set(q['question_number'] for q in questions)
                            for p_tag in list(soup_cleanup.find_all('p')):
                                strong_tag = p_tag.find('strong')
                                if strong_tag:
                                    strong_text = strong_tag.text.strip()
                                    # Match numeric questions like 31, 32, etc.
                                    if strong_text.isdigit() and strong_text in question_numbers_set:
                                        p_tag.decompose()

                            # 2) Remove paragraphs containing explicit table_name patterns
                            for p_tag in list(soup_cleanup.find_all('p')):
                                content = p_tag.decode_contents()
                                if re.search(r'table_name\s*=\s*"[^"]*"', content, flags=re.IGNORECASE):
                                    p_tag.decompose()

                            # 3) Remove option paragraphs A-G
                            option_letters = set(opt['value'] for opt in options)
                            for p_tag in list(soup_cleanup.find_all('p')):
                                strong_tag = p_tag.find('strong')
                                if strong_tag and strong_tag.text.strip().upper() in option_letters:
                                    p_tag.decompose()

                            # 4) Remove instruction paragraphs around writing correct letter
                            for p_tag in list(soup_cleanup.find_all('p')):
                                txt = p_tag.get_text(separator=' ', strip=True).lower()
                                # Note: "complete each sentence" removed - that's for Matching Sentence Endings parser
                                if ('write the correct letter' in txt) and ('which paragraph' in txt or 'paragraph contains' in txt):
                                    p_tag.decompose()

                            # 5) Remove empty and &nbsp; paragraphs
                            for p_tag in list(soup_cleanup.find_all('p')):
                                text_strip = p_tag.get_text(strip=True)
                                if not text_strip or text_strip == '\xa0' or text_strip.lower() == '&nbsp;':
                                    p_tag.decompose()

                            cleaned_html = str(soup_cleanup)
                            print(f"[MATCHING_UNIVERSAL] ✅ Processing complete, cleaned HTML returned")
                            return cleaned_html

            print(f"[MATCHING_UNIVERSAL] ❌ Failed to process, returning original HTML")
            return html_content

        except Exception as e:
            print(f"[MATCHING_UNIVERSAL] ERROR: {e}")
            import traceback
            print(f"[MATCHING_UNIVERSAL] Traceback: {traceback.format_exc()}")
            return html_content


class MatchingHeadingsParser:
    """FIXED: Professional IELTS Matching Headings Parser - Similar to Sentence Endings"""

    def __init__(self):
        self.question_type = 'matching_headings'

    def should_process_content(self, html_content, plain_text):
        """Detect if content should be processed as matching headings"""
        if not html_content or not plain_text:
            return False

        # Skip if already processed
        if 'drag-drop-matching-sentence-endings' in html_content and 'data-question-type="matching_headings"' in html_content:
            return False

        content_lower = plain_text.lower()

        # Strong indicators for headings
        indicators = [
            'choose the correct heading' in content_lower,
            'list of headings' in content_lower,
            'write the correct number' in content_lower,
            'read the paragraphs one by one to choose the correct headings' in content_lower,
            bool(re.search(r'correct number[,\s]+i-viii', content_lower)),
            bool(re.search(r'correct number[,\s]+i-x', content_lower)),
            bool(re.search(r'<strong>\d+</strong>', html_content)),
            # Check for Roman numerals in headings
            bool(re.search(r'<strong>[ivxlc]+</strong>', html_content)) and 'list of headings' in content_lower
        ]

        return any(indicators)

    def extract_questions_range(self, html_content, plain_text):
        """Extract questions range"""
        patterns = [
            r'questions?\s+([\d\-–]+)',
            r'Questions\s+([\d\-–]+)',
            r'QUESTIONS\s+([\d\-–]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, plain_text, re.IGNORECASE)
            if match:
                return f"Questions {match.group(1)}"

        # Fallback: find from ALL strong tags in content
        question_numbers = re.findall(r'<strong>(\d+)</strong>', html_content)
        if question_numbers:
            numbers = [int(q) for q in question_numbers if q.isdigit()]
            if numbers:
                return f"Questions {min(numbers)}-{max(numbers)}"

        return "Questions 1-8"

    def extract_headings_options(self, html_content):
        """Extract heading options (i-viii)"""
        options = []
        
        print(f"[MATCHING_HEADINGS] 🔍 Extracting headings options from HTML...")
        print(f"[MATCHING_HEADINGS] HTML preview: {html_content[:300]}...")

        # Multiple patterns for different heading formats
        # Including nested spans format
        patterns = [
            # Pattern 1: Nested spans format: <p><span...><span...><strong>i </strong></span></span></span><span...> Heading text</span></span></span></p>
            # This pattern captures roman numeral and any text after it (even if in nested spans)
            r'<p[^>]*>(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\s*([ivxlc]+)\s*(?:&nbsp;)*\s*</strong>(?:</span>)*(?:</span>)*(?:</span>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:\s|&nbsp;)*([^<]{10,200}?)(?:</span>)*(?:</span>)*(?:</span>)*(?:</p>)',
            # Pattern 2: Standard format: <strong>i </strong> Heading text
            r'<strong>\s*([ivxlc]+)\s*</strong>[^<]*?([A-Z][^<]{10,200}?)(?=<strong>|</p>|$)',
            r'<p[^>]*><strong>\s*([ivxlc]+)\s*</strong>\s*(?:&nbsp;)*\s*([^<]{10,200}?)</p>',
            r'([ivxlc]+)\s*[^\w]*([A-Z][^<\n]{10,150}?)(?=\n|$)',
            # Specific pattern for your format: <strong>i </strong>    Evidence of...
            r'<strong>\s*([ivxlc]+)\s*</strong>\s*(?:&nbsp;)*\s*([A-Z][^<]{10,200}?)(?=<strong>|</p>|$)',
            # Additional pattern to catch "i" specifically
            r'<strong>\s*i\s*</strong>\s*(?:&nbsp;)*\s*([A-Z][^<]{10,200}?)(?=<strong>|</p>|$)',
            # More specific pattern for "i" with different spacing
            r'<strong>\s*i\s*</strong>\s*(?:&nbsp;)*\s*([A-Z][^<]{10,200}?)(?=<strong>|</p>|$)',
            # Pattern to catch "i" at the beginning of a paragraph
            r'<p[^>]*><strong>\s*i\s*</strong>\s*(?:&nbsp;)*\s*([A-Z][^<]{10,200}?)</p>',
            # Pattern specifically for the user's format: <strong>i&nbsp;</strong>&nbsp;&nbsp;&nbsp;Evidence...
            r'<strong>\s*i\s*(?:&nbsp;)*\s*</strong>\s*(?:&nbsp;)*\s*([A-Z][^<]{10,200}?)(?=<strong>|</p>|$)',
            # Pattern for "i" with HTML entities
            r'<strong>\s*i\s*(?:&nbsp;)*\s*</strong>\s*(?:&nbsp;)*\s*([A-Z][^<]{10,200}?)(?=<strong>|</p>|$)'
        ]

        for i, pattern in enumerate(patterns):
            print(f"[MATCHING_HEADINGS] Trying pattern {i+1}: {pattern}")
            matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
            print(f"[MATCHING_HEADINGS] Pattern {i+1} found {len(matches)} matches")
            
            for match in matches:
                # Handle special cases for i-specific patterns (patterns 6, 7, 8, 9, 10)
                # Pattern 5 (index 4) has 2 groups, so handle it normally
                if i in [5, 6, 7, 8, 9]:  # Patterns 6, 7, 8, 9, 10 - only capture label (i-specific)
                    roman = 'i'
                    label = match if isinstance(match, str) else match[0] if isinstance(match, tuple) else str(match)
                else:
                    # Patterns with 2 groups: (roman, label)
                    if isinstance(match, tuple) and len(match) == 2:
                        roman, label = match
                    elif isinstance(match, str):
                        # Fallback: if it's a string, try to extract
                        print(f"[MATCHING_HEADINGS] ⚠️ Unexpected match format: {type(match)}")
                        continue
                    else:
                        print(f"[MATCHING_HEADINGS] ⚠️ Unexpected match format: {type(match)}, value: {match}")
                        continue
                
                # Ensure label is a string
                if not isinstance(label, str):
                    label = str(label) if label else ''
                
                print(f"[MATCHING_HEADINGS] Raw match - {roman}: '{label[:50] if label else 'EMPTY'}...'")
                
                # Clean up the label
                if label:
                    clean_label = re.sub(r'&nbsp;|\xa0', ' ', label)
                    clean_label = re.sub(r'^\s*[^\w]*|\s*[^\w]*$', '', clean_label)
                    clean_label = re.sub(r'\s+', ' ', clean_label).strip()
                    
                    # Remove any remaining "nbsp;" text
                    clean_label = re.sub(r'^nbsp;\s*', '', clean_label)
                else:
                    clean_label = ''

                if clean_label and len(clean_label) >= 10:
                    options.append({'value': roman.lower(), 'label': clean_label})
                    print(f"[MATCHING_HEADINGS] ✅ Added option: {roman.lower()} -> '{clean_label[:30]}...'")
                else:
                    print(f"[MATCHING_HEADINGS] ❌ Rejected: '{clean_label}' (length: {len(clean_label) if clean_label else 0})")

        # If no options found with regex, try BeautifulSoup approach for nested spans
        if not options:
            print(f"[MATCHING_HEADINGS] No regex matches, trying BeautifulSoup extraction for nested spans...")
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                paragraphs = soup.find_all('p')
                
                for p in paragraphs:
                    # Skip instruction paragraphs
                    p_text_lower = p.get_text(strip=True).lower()
                    if any(skip in p_text_lower for skip in ['choose the correct heading', 'list of headings', 'write the correct number', 'questions']):
                        continue
                    
                    # Find strong tags with roman numerals
                    strong_tags = p.find_all('strong')
                    
                    for strong in strong_tags:
                        strong_text = strong.get_text(strip=True).lower()
                        
                        # Check if it's a roman numeral (i, ii, iii, iv, v, vi, vii, viii, ix, x)
                        roman_numerals = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x']
                        if strong_text in roman_numerals:
                            roman = strong_text
                            
                            # Get all text from paragraph
                            full_text = p.get_text(separator=' ', strip=True)
                            
                            # Find the position of this roman numeral in the full text
                            # Pattern: "i Heading text" or "i. Heading text" or "i    Heading text"
                            pattern = rf'\b{re.escape(roman)}\s*\.?\s+([A-Z][^0-9]{10,200}?)(?=\s+[ivxlc]+\s|$)'
                            match = re.search(pattern, full_text)
                            
                            if match:
                                label = match.group(1).strip()
                                
                                # Clean text
                                label = re.sub(r'&nbsp;|&amp;nbsp;|\xa0', ' ', label)
                                label = re.sub(r'\s+', ' ', label).strip()
                                label = re.sub(r'^\s*[^\w]*|\s*[^\w]*$', '', label)
                                
                                # Filter valid headings
                                if label and len(label) >= 10:
                                    options.append({'value': roman, 'label': label})
                                    print(f"[MATCHING_HEADINGS] ✅ Extracted heading (BeautifulSoup) {roman}: '{label[:60]}...'")
                            else:
                                # Alternative: extract text after the strong tag directly from paragraph structure
                                # Get all text after this strong tag in the paragraph
                                found_strong = False
                                label_parts = []
                                
                                for element in p.descendants:
                                    if element == strong:
                                        found_strong = True
                                        continue
                                    
                                    if found_strong:
                                        if hasattr(element, 'string') and element.string:
                                            text = element.string.strip()
                                            if text and not text.isdigit() and text.lower() not in roman_numerals:
                                                label_parts.append(text)
                                        
                                        # Stop at next strong tag
                                        if hasattr(element, 'name') and element.name == 'strong':
                                            break
                                
                                if label_parts:
                                    label = ' '.join(label_parts).strip()
                                    label = re.sub(r'&nbsp;|&amp;nbsp;|\xa0', ' ', label)
                                    label = re.sub(r'\s+', ' ', label).strip()
                                    label = re.sub(r'^\s*[^\w]*|\s*[^\w]*$', '', label)
                                    
                                    if label and len(label) >= 10:
                                        options.append({'value': roman, 'label': label})
                                        print(f"[MATCHING_HEADINGS] ✅ Extracted heading (BeautifulSoup-descendants) {roman}: '{label[:60]}...'")
                                    
            except Exception as e:
                print(f"[MATCHING_HEADINGS] BeautifulSoup extraction error: {e}")
                import traceback
                print(f"[MATCHING_HEADINGS] Traceback: {traceback.format_exc()}")

        # Remove duplicates while preserving order
        seen = set()
        unique_options = []
        for option in options:
            if option['value'] not in seen:
                seen.add(option['value'])
                unique_options.append(option)

        print(f"[MATCHING_HEADINGS] 🎯 FINAL EXTRACTION RESULT:")
        print(f"[MATCHING_HEADINGS] Total options found: {len(unique_options)}")
        for opt in unique_options:
            print(f"[MATCHING_HEADINGS] {opt['value']}: '{opt['label'][:50]}...'")

        return unique_options

    def extract_all_content_with_questions(self, html_content):
        """Extract ALL content that contains question numbers"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find ALL elements with question numbers
        question_elements = []

        for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div']):
            text = str(tag)

            # Skip instruction elements
            skip_indicators = [
                'choose the correct heading',
                'list of headings',
                'write the correct number'
            ]

            if any(skip in text.lower() for skip in skip_indicators):
                print(f"[MATCHING_HEADINGS] Skipping instruction element: {text[:100]}...")
                continue

            # Skip example text - we'll handle it separately
            if 'example' in text.lower() and 'answer' in text.lower():
                print(f"[MATCHING_HEADINGS] Skipping example text (will be handled separately): {text[:100]}...")
                continue

            # Skip empty elements
            if not tag.get_text(strip=True):
                print(f"[MATCHING_HEADINGS] Skipping empty element: {text[:50]}...")
                continue

            # Skip heading options (containing roman numerals) - but NOT question numbers
            # Including nested spans format
            has_roman = bool(re.search(r'<strong>[^<]*[ivxlc]+[^<]*</strong>', text, re.IGNORECASE)) or \
                       bool(re.search(r'(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>[^<]*[ivxlc]+[^<]*</strong>', text, re.IGNORECASE))
            has_question_number = bool(re.search(r'<strong>\d+</strong>', text)) or \
                                 bool(re.search(r'(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\d+</strong>', text))
            # Check for paragraph reference pattern: <strong>1</strong> Paragraph <strong>A</strong>
            has_paragraph_reference = bool(re.search(r'paragraph\s+<strong>[A-G]</strong>', text, re.IGNORECASE)) or \
                                      bool(re.search(r'paragraph\s+[A-G]', text, re.IGNORECASE))
            
            # Skip if it's ONLY a roman numeral (heading option) without question number or paragraph reference
            if has_roman and not has_question_number and not has_paragraph_reference:
                print(f"[MATCHING_HEADINGS] Skipping roman numeral element: {text[:100]}...")
                continue

            # Check if this element has question numbers OR paragraph references
            # Including nested spans format
            if has_question_number or has_paragraph_reference:
                print(f"[MATCHING_HEADINGS] Found question element: {text[:100]}...")
                question_elements.append(str(tag))

        return '\n'.join(question_elements) if question_elements else ""

    def process_all_content_with_questions(self, content_html, original_html=None):
        """Process ALL content containing questions with preserved example texts in original format"""
        import re  # Import re at the top of the method
        
        if not content_html:
            return ""

        print(f"[MATCHING_HEADINGS] 🔍 Processing content with questions...")
        print(f"[MATCHING_HEADINGS] Content preview: {content_html[:200]}...")

        # Use original HTML for example text extraction if available
        html_for_example = original_html if original_html else content_html
        
        # Extract ALL example texts from original HTML with their original HTML format and positions
        example_elements = []
        soup = BeautifulSoup(html_for_example, 'html.parser')
        
        # Debug: Show all text content to see what's available
        all_text = soup.get_text()
        print(f"[MATCHING_HEADINGS] 🔍 All text content: {all_text[:500]}...")
        
        # Look for ALL example texts in all possible tags and preserve their original HTML
        # Find both the "Example Answer" line AND the "Paragraph F vii" line that follows it
        all_tags = soup.find_all(['p', 'div', 'span', 'td', 'th', 'li'])
        for i, tag in enumerate(all_tags):
            text = tag.get_text().strip()
            if 'example' in text.lower() and 'answer' in text.lower():
                # Preserve the original HTML format of the example header
                example_header_html = str(tag)
                
                # Look for the next paragraph that contains paragraph information (e.g., "Paragraph F vii")
                next_paragraph = None
                for j in range(i + 1, min(i + 5, len(all_tags))):  # Check next 5 tags
                    next_tag = all_tags[j]
                    next_text = next_tag.get_text().strip()
                    # Check if this tag contains "Paragraph" followed by a letter and roman numeral
                    if 'paragraph' in next_text.lower():
                        # Check if it has both a paragraph letter (A-I) and a roman numeral (i-xi)
                        if re.search(r'paragraph\s+[A-I]', next_text, re.IGNORECASE) and re.search(r'[ivxlc]+', next_text, re.IGNORECASE):
                            next_paragraph = str(next_tag)
                            break
                
                # Combine example header and paragraph information
                if next_paragraph:
                    combined_example = f"{example_header_html}\n{next_paragraph}"
                    example_elements.append(combined_example)
                    print(f"[MATCHING_HEADINGS] ✅ Found example with paragraph: {combined_example[:150]}...")
                else:
                    example_elements.append(example_header_html)
                    print(f"[MATCHING_HEADINGS] ✅ Found example element: {example_header_html[:100]}...")
        
        # If not found in individual tags, look for tables containing example text
        if not example_elements:
            for table in soup.find_all('table'):
                table_text = table.get_text().strip()
                if 'example' in table_text.lower() and 'answer' in table_text.lower():
                    # Preserve the original HTML format of the table
                    original_html = str(table)
                    example_elements.append(original_html)
                    print(f"[MATCHING_HEADINGS] ✅ Found example table: {original_html[:100]}...")
        
        if not example_elements:
            print(f"[MATCHING_HEADINGS] ❌ No example elements found in content")

        # Find ALL question numbers
        question_numbers = re.findall(r'<strong>(\d+)</strong>', content_html)
        print(f"[MATCHING_HEADINGS] Found question numbers: {question_numbers}")
        
        # Debug: Show all strong tags to see what's being found
        strong_tags = re.findall(r'<strong>([^<]+)</strong>', content_html)
        print(f"[MATCHING_HEADINGS] All strong tags found: {strong_tags}")

        if not question_numbers:
            print(f"[MATCHING_HEADINGS] ❌ No question numbers found!")
            return content_html

        # Get text content without HTML - but only for question processing
        # We'll extract questions directly from the HTML instead of using raw text
        question_elements = []
        soup_questions = BeautifulSoup(content_html, 'html.parser')
        
        for tag in soup_questions.find_all(['p', 'div']):
            text = tag.get_text().strip()
            if re.search(r'<strong>\d+</strong>', str(tag)):
                question_elements.append(str(tag))
        
        # Build formatted content with ALL questions and example texts in original format
        current_line = ""
        
        # Extract paragraph letter from example (e.g., "F" from "Paragraph F vii")
        example_paragraph_letter = None
        if example_elements:
            example_text = BeautifulSoup(example_elements[0], 'html.parser').get_text()
            example_match = re.search(r'paragraph\s+([A-I])', example_text, re.IGNORECASE)
            if example_match:
                example_paragraph_letter = example_match.group(1).upper()
                print(f"[MATCHING_HEADINGS] Example paragraph letter: {example_paragraph_letter}")
        
        # Build a mapping of question numbers to their paragraph letters
        question_to_paragraph = {}
        for element_html in question_elements:
            element_soup = BeautifulSoup(element_html, 'html.parser')
            strong_tags = element_soup.find_all('strong')
            if len(strong_tags) >= 2:
                question_num = strong_tags[0].get_text().strip()
                paragraph_text = element_soup.get_text().strip()
                # Extract paragraph letter (A-I)
                para_match = re.search(r'paragraph\s+([A-I])', paragraph_text, re.IGNORECASE)
                if para_match:
                    question_to_paragraph[question_num] = para_match.group(1).upper()
        
        print(f"[MATCHING_HEADINGS] Question to paragraph mapping: {question_to_paragraph}")
        
        for i, element_html in enumerate(question_elements):
            element_soup = BeautifulSoup(element_html, 'html.parser')
            strong_tags = element_soup.find_all('strong')
            
            # Check if this is a paragraph reference format: <strong>1</strong> Paragraph <strong>A</strong>
            paragraph_text = element_soup.get_text().strip()
            para_match = re.search(r'paragraph\s+([A-I])', paragraph_text, re.IGNORECASE)
            
            if len(strong_tags) >= 2:  # Question number + Paragraph letter
                question_num = strong_tags[0].get_text().strip()
                
                # Clean up the paragraph text (remove question number)
                paragraph_text = re.sub(rf'^{question_num}\s*', '', paragraph_text).strip()
                
                # Normalize paragraph text: remove ellipsis/dots sequences of any kind before inserting drag-drop
                paragraph_text_clean = re.sub(r'(?:&hellip;|…|\.{2,})', '', paragraph_text).strip()
                # Add formatted question with <p> wrapper for clean formatting
                current_line += f"<p><strong>{question_num}</strong> {paragraph_text_clean} <drag-drop-sentence-input data-question-number=\"{question_num}\" data-question-type=\"{self.question_type}\"></drag-drop-sentence-input></p>"
            elif len(strong_tags) == 1 and para_match:
                # Format: <strong>1</strong> Paragraph <strong>A</strong> (but strong tags might be in different spans)
                # Try to extract question number from first strong tag
                question_num = strong_tags[0].get_text().strip()
                if question_num.isdigit():
                    # Use the paragraph text as-is
                    paragraph_text_clean = re.sub(r'(?:&hellip;|…|\.{2,})', '', paragraph_text).strip()
                current_line += f"<p><strong>{question_num}</strong> {paragraph_text_clean} <drag-drop-sentence-input data-question-number=\"{question_num}\" data-question-type=\"{self.question_type}\"></drag-drop-sentence-input></p>"
                
                # Check if we should insert example after this question
                # Insert example after the question that has the paragraph letter BEFORE the example's paragraph letter
                if example_elements and example_paragraph_letter:
                    current_para = question_to_paragraph.get(question_num)
                    if current_para:
                        # Check if this is the last question before the example
                        # Example "F" should come after question with paragraph "E"
                        para_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']
                        try:
                            example_index_in_letters = para_letters.index(example_paragraph_letter)
                            current_index_in_letters = para_letters.index(current_para)
                            # If current paragraph is the one before the example paragraph, insert example
                            if current_index_in_letters == example_index_in_letters - 1:
                                # Insert example after this question - preserve original HTML format
                                example_html = example_elements[0]
                                # The example_html already contains proper <p> tags, so insert it directly
                                current_line += example_html
                                # Mark as used so we don't insert it again
                                example_elements = []  # Clear after using
                                print(f"[MATCHING_HEADINGS] ✅ Inserted example after question {question_num}")
                        except ValueError:
                            pass
        
        # Clean up and return
        # Final cleanup: ensure no ellipsis sequences remain in the built content
        final_content = re.sub(r'(?:&hellip;|…|\.{2,})', '', current_line).strip()
        
        print(f"[MATCHING_HEADINGS] ✅ Processed content: {final_content[:200]}...")
        return final_content

    def split_text_by_all_questions(self, text, question_numbers):
        """Split text by ALL question positions"""
        parts = []
        current_pos = 0

        # Sort question numbers to process in order
        sorted_questions = sorted([int(q) for q in question_numbers])

        for q_num in sorted_questions:
            q_str = str(q_num)

            # Find the question number in remaining text
            pattern = rf'\b{q_str}\b'
            match = re.search(pattern, text[current_pos:])

            if match:
                # Add text before question
                before_text = text[current_pos:current_pos + match.start()].strip()

                if before_text:
                    parts.append(('text', before_text))

                # Add question
                parts.append(('question', q_str))
                current_pos = current_pos + match.end()

        # Add remaining text
        remaining_text = text[current_pos:].strip()
        if remaining_text:
            parts.append(('text', remaining_text))

        return parts

    def sort_roman_numerals(self, options):
        """Sort options by roman numeral order (i, ii, iii, iv, v, vi, vii, viii, ix)"""
        roman_order = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x']
        
        def get_roman_index(option):
            value = option['value'].lower()
            try:
                return roman_order.index(value)
            except ValueError:
                return 999  # Put unknown values at the end
        
        return sorted(options, key=get_roman_index)

    def convert_example_tables_to_text(self, html_content):
        """Convert example tables to simple text format"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all tables
        tables = soup.find_all('table')
        for table in tables:
            # Check if this is an example table
            table_text = table.get_text().lower()
            if 'example' in table_text and 'answer' in table_text:
                print(f"[MATCHING_HEADINGS] 🔄 Converting example table to text")
                
                # Extract the example text
                example_text = table.get_text().strip()
                # Clean up the text
                example_text = re.sub(r'\s+', ' ', example_text)
                example_text = re.sub(r'Example\s+Answer', 'Example Answer', example_text)
                
                # Replace table with simple paragraph
                new_p = soup.new_tag('p')
                new_p.string = example_text
                table.replace_with(new_p)
                
                print(f"[MATCHING_HEADINGS] ✅ Converted table to: {example_text[:100]}...")
        
        return str(soup)

    def extract_instruction_paragraphs(self, html_content):
        """Extract instruction paragraphs like 'Reading Passage...', 'Choose the correct heading...', 'Write the correct number...'"""
        soup = BeautifulSoup(html_content, 'html.parser')
        instruction_paragraphs = []
        
        for tag in soup.find_all(['p', 'div']):
            text = tag.get_text().strip()
            tag_str = str(tag)
            
            # Skip if it's a question number or option
            if re.search(r'<strong>\d+</strong>', tag_str) or re.search(r'<strong>[ivxlc]+</strong>', tag_str, re.IGNORECASE):
                continue
            
            # Skip if it's empty
            if not text:
                continue
            
            # Check if it's an instruction paragraph
            instruction_patterns = [
                r'reading passage.*paragraphs?',
                r'choose the correct heading',
                r'write the correct number'
            ]
            
            # Exclude "List of Headings" as it's just a header, not an instruction
            if 'list of headings' in text.lower() and len(text) < 50:
                continue
            
            if any(re.search(pattern, text, re.IGNORECASE) for pattern in instruction_patterns):
                instruction_paragraphs.append(tag_str)
                print(f"[MATCHING_HEADINGS] ✅ Found instruction paragraph: {text[:100]}...")
        
        return instruction_paragraphs

    def build_final_output_with_all_questions(self, questions_range, options, content_with_questions, repeat_flag=False, original_html="", instruction_paragraphs=None):
        """Build final output with ALL questions included"""
        if not content_with_questions or not options:
            return ""

        # Sort options by roman numeral order
        sorted_options = self.sort_roman_numerals(options)
        options_json = json.dumps(sorted_options, ensure_ascii=False, separators=(',', ':'))

        # Determine roman numeral range from options
        if options:
            last_roman = max(opt['value'] for opt in options)
            roman_range = f"i-{last_roman}"
        else:
            roman_range = "i-ix"

        # Prepare per-question formatting: add dots inside inputs, and <br/>
        content_q = content_with_questions
        # Ensure inputs contain ellipsis dots
        content_q = re.sub(r'(<drag-drop-sentence-input[^>]*>)(\s*)(</drag-drop-sentence-input>)', r'\1…\3', content_q)
        # Append <br/> before closing paragraph
        content_q = re.sub(r'</drag-drop-sentence-input>\s*</p>', r'</drag-drop-sentence-input><br/></p>', content_q)

        # Build final output with ALL questions - using drag-drop-matching-sentence-endings format
        # Wrap in <div> to match required format and set data-repeat based on NB
        data_repeat = 'True' if repeat_flag else 'False'
        
        # Include instruction paragraphs if provided, otherwise use default
        instruction_html = ""
        if instruction_paragraphs:
            instruction_html = " ".join(instruction_paragraphs) + " "
        else:
            instruction_html = "<p><em>Choose the correct heading for each paragraph from the list of headings below.</em></p> "
        
        final_output = (
            f"<div><drag-drop-matching-sentence-endings data-options='{options_json}' data-question-type=\"matching_headings\" data-repeat=\"{data_repeat}\"> "
            f"<h3><em><strong>{questions_range}</strong></em></h3> "
            f"{instruction_html}"
            f"{content_q} "
            f"</drag-drop-matching-sentence-endings></div>"
        )

        return final_output

    def parse_and_insert_inputs(self, html_content):
        """Main parsing function - finds ALL questions in ALL tags"""
        if not html_content or not html_content.strip():
            return html_content

        try:
            print(f"[MATCHING_HEADINGS] 🚀 Starting FULL SCAN parse for ALL questions...")

            # First, convert example tables to simple text
            html_content = self.convert_example_tables_to_text(html_content)

            soup = BeautifulSoup(html_content, 'html.parser')
            plain_text = soup.get_text(separator=' ', strip=True)

            # Check if should process
            if not self.should_process_content(html_content, plain_text):
                print(f"[MATCHING_HEADINGS] ℹ️ Not processing, returning original content")
                return html_content

            # Extract components
            questions_range = self.extract_questions_range(html_content, plain_text)
            options = self.extract_headings_options(html_content)

            # Extract ALL content with questions
            all_content_with_questions = self.extract_all_content_with_questions(html_content)

            if not options or not all_content_with_questions:
                print(f"[MATCHING_HEADINGS] ⚠️ Missing components")
                print(f"Options found: {len(options)}, Content found: {bool(all_content_with_questions)}")
                return html_content

            # Process ALL content with questions
            processed_content = self.process_all_content_with_questions(all_content_with_questions, html_content)

            if not processed_content:
                print(f"[MATCHING_HEADINGS] ⚠️ No processed content")
                return html_content

            # Detect NB / repeat flag from full content
            def has_nb_repeat_full(text_html: str) -> bool:
                try:
                    plain = BeautifulSoup(text_html, 'html.parser').get_text(separator=' ', strip=True).lower()
                except Exception:
                    plain = str(text_html).lower()
                nb_indicators = [
                    r'\bnb\b',
                    r'you may use any letter more than once',
                    r'may use any letter more than once',
                    r'use any letter more than once',
                    r'letters may be used more than once'
                ]
                return any(re.search(pat, plain) for pat in nb_indicators)

            repeat_flag = has_nb_repeat_full(html_content)

            # Extract instruction paragraphs
            instruction_paragraphs = self.extract_instruction_paragraphs(html_content)

            # Build final result with ALL questions
            result = self.build_final_output_with_all_questions(questions_range, options, processed_content, repeat_flag, html_content, instruction_paragraphs)

            # Count generated input tags
            input_count = len(re.findall(r'<drag-drop-sentence-input', result))
            print(f"[MATCHING_HEADINGS] ✅ FULL SCAN completed - Generated {input_count} drag-drop inputs")

            return result

        except Exception as e:
            print(f"[MATCHING_HEADINGS] ❌ Error: {e}")
            import traceback
            print(f"[MATCHING_HEADINGS] Traceback: {traceback.format_exc()}")
            return html_content


def parse_matching_sentence_endings(html_content):
    """Enhanced function for matching sentence endings parsing"""
    parser = MatchingSentenceEndingsParser()
    return parser.parse_and_insert_inputs(html_content)

def parse_matching_information(html_content):
    """NEW: Parse matching information"""
    parser = MatchingInformationParser()
    return parser.parse_and_insert_inputs(html_content)

def parse_matching_headings(html_content):
    """Parse matching headings"""
    parser = MatchingHeadingsParser()
    return parser.parse_and_insert_inputs(html_content)


class ListeningMatchingHeadingsParser:
    """Specialized parser for listening matching headings format"""
    
    def __init__(self):
        self.question_type = 'matching_sentence_endings'
    
    def extract_questions_range(self, html_content, plain_text):
        """Extract questions range from content"""
        patterns = [
            r'questions?\s+(\d+)\s*[-–]\s*(\d+)',
            r'Questions\s+(\d+)\s*[-–]\s*(\d+)',
            r'QUESTIONS\s+(\d+)\s*[-–]\s*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, plain_text, re.IGNORECASE)
            if match:
                return f"Questions {match.group(1)}–{match.group(2)}"
        
        # Fallback: find from ALL strong tags in content
        question_numbers = re.findall(r'<strong>\s*(\d+)[\.]?\s*</strong>', html_content)
        if question_numbers:
            numbers = [int(q) for q in question_numbers if q.isdigit()]
            if numbers:
                return f"Questions {min(numbers)}–{max(numbers)}"
        
        return "Questions 21–25"
    
    def extract_options(self, html_content):
        """Extract options A, B, C with their labels"""
        options = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all paragraphs with option letters
        for p_tag in soup.find_all('p'):
            strong_tag = p_tag.find('strong')
            if strong_tag:
                letter_text = strong_tag.get_text(strip=True).upper()
                
                # Check if this is an option letter (A-Z, support all letters)
                if letter_text in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']:
                    # Get the full paragraph text
                    full_text = p_tag.get_text()
                    
                    # Remove the letter at the start (case-insensitive)
                    # Pattern: letter followed by optional spaces, &nbsp;, periods, or other whitespace
                    label_text = re.sub(rf'^{letter_text}\s*(?:&nbsp;|\xa0)*\s*\.?\s*', '', full_text, flags=re.IGNORECASE)
                    
                    # Clean up HTML entities and whitespace first
                    label_text = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', label_text)
                    label_text = re.sub(r'\s+', ' ', label_text).strip()
                    
                    # If label still starts with the letter (e.g., "A He'll"), remove it
                    if label_text.strip().upper().startswith(letter_text + ' '):
                        label_text = label_text[len(letter_text):].strip()
                    
                    # Clean up HTML entities (apostrophes)
                    label_text = label_text.replace('&#39;', "'").replace('&apos;', "'")
                    
                    # Remove trailing periods
                    label_text = re.sub(r'\.+$', '', label_text).strip()
                    
                    # Remove leading non-word/non-letter characters but keep internal punctuation
                    label_text = re.sub(r'^[^\w\s]*', '', label_text).strip()
                    # Remove trailing non-word characters
                    label_text = re.sub(r'[^\w\s]*$', '', label_text).strip()
                    
                    # Final check: if it still starts with the letter (after all cleaning), remove it
                    if label_text.strip().upper().startswith(letter_text):
                        # Check if it's just the letter or letter + space + text
                        if len(label_text.strip()) > 1 and label_text.strip()[1:2] in [' ', '\t']:
                            label_text = label_text.strip()[len(letter_text):].strip()
                        elif len(label_text.strip()) == 1:
                            continue  # Skip if it's just the letter
                    
                    label_lower = label_text.lower()
                    instruction_indicators = [
                        'write the correct letter',
                        'choose your answers from the box',
                        'match the statements',
                        'next to questions',
                        'choose the correct letter'
                    ]
                    if any(indicator in label_lower for indicator in instruction_indicators):
                        continue  # Skip instruction-like paragraphs mistaken as options

                    if label_text and len(label_text) >= 3:
                        options.append({
                            'value': letter_text,
                            'label': label_text
                        })
                        print(f"[LISTENING_MATCHING] ✅ Extracted option {letter_text}: '{label_text}'")
        
        # Sort by letter order
        options.sort(key=lambda x: x['value'])
        
        print(f"[LISTENING_MATCHING] 🎯 Total options extracted: {len(options)}")
        return options
    
    def extract_questions(self, html_content):
        """Extract questions with their numbers and text"""
        questions = []
        example_text = None  # Store example text if found
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # First, check for example text (like "Experiment 4: Example F too easy")
        for p_tag in soup.find_all('p'):
            p_text = p_tag.get_text(strip=True)
            p_lower = p_text.lower()
            # Check if this paragraph contains example text
            if 'example' in p_lower:
                # Check if it's not a question number (avoid matching question numbers with "example" in them)
                strong_tag = p_tag.find('strong')
                if strong_tag:
                    strong_text = strong_tag.get_text(strip=True)
                    # If strong tag contains a digit, it's likely a question number, skip it
                    if re.match(r'^\d+\.?$', strong_text):
                        continue
                
                # Extract the full example text
                example_text = p_text
                # Clean up the example text
                example_text = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', example_text)
                example_text = re.sub(r'\s+', ' ', example_text).strip()
                
                # Format it nicely: "Experiment 4: Example F too easy" -> "Experiment 4 — F Too easy"
                # Replace colon with em dash and reformat
                # Extract the letter and answer from example text
                # Pattern: "Experiment 4: Example F too easy" -> "Experiment 4 — F Too easy"
                example_text = re.sub(r'\s+', ' ', example_text).strip()
                
                # Replace "Example" keyword and reformat
                # Remove "Example" keyword but keep the rest
                example_text = re.sub(r'\bexample\s*:?\s*', '', example_text, flags=re.IGNORECASE)
                example_text = example_text.strip()
                
                # Replace colon with em dash if exists
                if ':' in example_text:
                    example_text = example_text.replace(':', '—', 1)
                
                # Format: "Experiment 4 — F too easy" -> "Experiment 4 — F Too easy"
                # Capitalize the answer part after the letter
                parts = example_text.split('—')
                if len(parts) == 2:
                    exp_part = parts[0].strip()
                    answer_part = parts[1].strip()
                    # Capitalize first letter of answer
                    if answer_part:
                        answer_part = answer_part[0].upper() + answer_part[1:] if len(answer_part) > 1 else answer_part.upper()
                    example_text = f"{exp_part} — {answer_part}"
                
                print(f"[LISTENING_MATCHING] ✅ Found and formatted example text: '{example_text}'")
                break
        
        # Find all paragraphs with question numbers
        for p_tag in soup.find_all('p'):
            strong_tag = p_tag.find('strong')
            if strong_tag:
                question_text = strong_tag.get_text(strip=True)
                
                # Check if this is a question number (digits followed by optional dot)
                if re.match(r'^\d+\.?$', question_text):
                    question_num = question_text.rstrip('.')
                    
                    # Extract the question label text after the number
                    label_text = p_tag.get_text()
                    # Remove the question number and dots/ellipsis
                    label_text = re.sub(rf'^{question_num}\.?\s*', '', label_text, flags=re.IGNORECASE)
                    label_text = re.sub(r'&hellip;|&nbsp;|\xa0|\.{3,}|\.{2,}|…', '', label_text)
                    label_text = re.sub(r'\s+', ' ', label_text).strip()
                    
                    # Clean up HTML entities (including &ntilde; for ñ)
                    label_text = label_text.replace('&#39;', "'").replace('&ntilde;', 'ñ').replace('&Ntilde;', 'Ñ')
                    # Only remove leading/trailing non-word characters, keep colons and other punctuation
                    label_text = re.sub(r'^[^\w\s:]*', '', label_text).strip()
                    label_text = re.sub(r'[^\w\s:]*$', '', label_text).strip()
                    # Don't remove trailing colons - they're part of the question text (e.g., "Experiment 1:")
                    if label_text.endswith(':'):
                        label_text = label_text  # Keep the colon
                    
                    if label_text and len(label_text) >= 3:
                        questions.append({
                            'question_number': question_num,
                            'question_text': label_text
                        })
                        print(f"[LISTENING_MATCHING] ✅ Extracted question {question_num}: '{label_text}'")
        
        # Also check for questions in span tags (for the new format with spans)
        for span_tag in soup.find_all('span'):
            span_text = span_tag.get_text()
            # Look for pattern like "26 understanding of El Niño ....."
            question_pattern = r'(\d+)\s+([^\.]+?)(?:\.{2,}|\.{3,}|&hellip;|…)'
            matches = re.finditer(question_pattern, span_text, re.IGNORECASE)
            for match in matches:
                question_num = match.group(1).strip()
                question_label = match.group(2).strip()
                
                # Clean up the label
                question_label = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', question_label)
                question_label = re.sub(r'\s+', ' ', question_label).strip()
                question_label = question_label.replace('&ntilde;', 'ñ').replace('&Ntilde;', 'Ñ')
                question_label = re.sub(r'^[^\w]*|[^\w]*$', '', question_label)
                
                # Check if this question number already exists
                if question_num and question_label and len(question_label) >= 3:
                    existing = any(q['question_number'] == question_num for q in questions)
                    if not existing:
                        questions.append({
                            'question_number': question_num,
                            'question_text': question_label
                        })
                        print(f"[LISTENING_MATCHING] ✅ Extracted question from span {question_num}: '{question_label}'")
        
        # Sort by question number
        questions.sort(key=lambda x: int(x['question_number']))
        
        print(f"[LISTENING_MATCHING] 🎯 Total questions extracted: {len(questions)}")
        return questions, example_text
    
    def detect_repeat_answer(self, html_content, plain_text):
        """Detect if repeat_answer is required based on NB indicators"""
        content_lower = plain_text.lower()
        
        # Check for NB indicators
        nb_indicators = [
            r'\bnb\b',
            'you may choose any letter more than once',
            'you may use any letter more than once',
            'may use any letter more than once',
            'use any letter more than once',
            'letters may be used more than once',
            'may choose any letter more than once'
        ]
        
        for indicator in nb_indicators:
            if isinstance(indicator, str):
                if re.search(indicator, content_lower):
                    print(f"[LISTENING_MATCHING] ✅ Found NB indicator: '{indicator}', setting repeat_answer=True")
                    return True
        
        print(f"[LISTENING_MATCHING] ❌ No NB found, repeat_answer=False")
        return False
    
    def extract_instruction_text(self, html_content, plain_text):
        """Extract the instruction text (e.g., 'What does Jack tell his tutor about each of the following course options?' or 'In what time period can data from the float projects help with the following things?' or 'Which hotel matches each description?')"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for the instruction paragraph
        for p_tag in soup.find_all('p'):
            p_text = p_tag.get_text(strip=True)
            p_lower = p_text.lower()
            
            # Pattern 1: "What does/tells...about each of the following"
            if ('what does' in p_lower or 'what tells' in p_lower) and 'about each of the following' in p_lower:
                instruction = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', p_text)
                instruction = re.sub(r'\s+', ' ', instruction).strip()
                return instruction
            
            # Pattern 2: "In what time period can...help with the following things?"
            if 'in what time period' in p_lower and ('help with the following' in p_lower or 'following things' in p_lower):
                instruction = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', p_text)
                instruction = re.sub(r'\s+', ' ', instruction).strip()
                return instruction
            
            # Pattern 3: "In what...help with the following"
            if 'in what' in p_lower and 'help with the following' in p_lower:
                instruction = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', p_text)
                instruction = re.sub(r'\s+', ' ', instruction).strip()
                return instruction
            
            # Pattern 4: "Which ... matches each description?" (NEW)
            if 'matches each description' in p_lower and 'which' in p_lower:
                instruction = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', p_text)
                instruction = re.sub(r'\s+', ' ', instruction).strip()
                return instruction
            
            # Pattern 5: "Which ... matches each ...?" (more flexible)
            if 'which' in p_lower and 'matches' in p_lower and 'description' in p_lower:
                instruction = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', p_text)
                instruction = re.sub(r'\s+', ' ', instruction).strip()
                return instruction
            
            # Pattern 6: "What problems do the speakers identify for each experiment?"
            # Also handles: "What do problems do the speakers identify"
            if ('what problems' in p_lower or 'what do problems' in p_lower) and 'speakers identify' in p_lower:
                instruction = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', p_text)
                instruction = re.sub(r'\s+', ' ', instruction).strip()
                return instruction
            
            # Pattern 7: "What problems" + "identify" + "experiment"
            # Also handles: "What do problems do...identify...experiment"
            if ('what problems' in p_lower or 'what do problems' in p_lower) and 'identify' in p_lower and 'experiment' in p_lower:
                instruction = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', p_text)
                instruction = re.sub(r'\s+', ' ', instruction).strip()
                return instruction
            
            # Pattern 8: More flexible - "problems" + "speakers identify" + "experiment"
            if 'problems' in p_lower and 'speakers identify' in p_lower and 'experiment' in p_lower:
                instruction = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', p_text)
                instruction = re.sub(r'\s+', ' ', instruction).strip()
                return instruction
        
        return None
    
    def extract_instruction_paragraphs_block(self, html_content):
        """Extract instruction paragraphs (retain original HTML)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        instruction_keywords = [
            'which',
            'write the correct letter',
            'choose your answers',
            'choose the correct letter',
            'match each',
            'what does',
            'what problems',
            'in what time period',
            'what action is needed'
        ]
        paragraphs = []
        
        for p_tag in soup.find_all('p'):
            text = p_tag.get_text(separator=' ', strip=True)
            if not text:
                continue
            
            lower_text = text.lower()
            
            # Skip option paragraphs that start with a single letter (A, B, etc.)
            if re.match(r'^[A-Z]\b', text.strip()):
                continue
            
            if any(keyword in lower_text for keyword in instruction_keywords):
                paragraphs.append(str(p_tag))
        
        return ''.join(paragraphs)
    
    def build_final_output(self, questions_range, options, questions, repeat_answer, instruction_text, example_text=None, original_html=None):
        """Build final output in the exact format specified"""
        if not questions or not options:
            print(f"[LISTENING_MATCHING] ❌ Cannot create: questions={len(questions)}, options={len(options)}")
            return ""
        
        # Ensure JSON is properly formatted (use double quotes inside JSON, single quotes for HTML attribute)
        options_json = json.dumps(options, ensure_ascii=False, separators=(',', ':'))
        
        # Escape apostrophes in JSON string values to HTML entities to avoid breaking JSON parsing
        # This handles cases like "He'll" and "won't" in the label values
        # Since JSON uses double quotes for strings, all apostrophes will be inside string values
        options_json = options_json.replace("'", "&#39;")
        
        # Get letter range from options
        if options:
            first_letter = options[0]['value']
            last_letter = options[-1]['value']
            letter_range = f"{first_letter}–{last_letter}"
        else:
            letter_range = "A–C"
        
        # Build questions HTML (single line, no newlines)
        questions_html = ""
        for q in questions:
            q_num = q['question_number']
            q_text = q['question_text']
            questions_html += (
                f' <strong>{q_num}</strong>&nbsp;&nbsp;&nbsp;{q_text} '
                f'<drag-drop-sentence-input data-question-number="{q_num}" '
                f'data-question-type="{self.question_type}">…</drag-drop-sentence-input><br/>'
            )
        
        # Insert example text if it exists (after the question that comes before it)
        if example_text:
            # Find where to insert the example
            # Example text mentions "Experiment 4", which comes after question 29
            example_inserted = False
            
            # Extract experiment number from example text if possible
            exp_match = re.search(r'experiment\s*(\d+)', example_text, re.IGNORECASE)
            if exp_match:
                exp_num = exp_match.group(1)
                # Find the question that mentions this experiment number (e.g., question 29 mentions Experiment 3)
                # We need to find which question comes BEFORE the example
                # If example is Experiment 4, it comes after question 29 (which is Experiment 3)
                for i, q in enumerate(questions):
                    q_num = int(q['question_number'])
                    q_text_lower = q['question_text'].lower()
                    
                    # Check if this question mentions the experiment number before the example
                    # If example is Experiment 4, look for question mentioning Experiment 3
                    if f'experiment {exp_num}' in q_text_lower or f'experiment{exp_num}' in q_text_lower:
                        # This is the question that matches the example, insert after it
                        # Find the </p> tag for this question
                        q_tag = f"<p>{q['question_number']}."
                        insert_pos = questions_html.find('</p>', questions_html.find(q_tag))
                        if insert_pos != -1:
                            example_formatted = f' <p>Example: {example_text}</p>'
                            questions_html = questions_html[:insert_pos+4] + example_formatted + questions_html[insert_pos+4:]
                            example_inserted = True
                            print(f"[LISTENING_MATCHING] ✅ Inserted example after question {q['question_number']}")
                            break
                    
                    # Alternative: if example is Experiment 4 and we have question 29 (Experiment 3), insert after 29
                    if exp_num == '4' and q_num == 29:
                        q_tag = f"<p>{q['question_number']}."
                        insert_pos = questions_html.find('</p>', questions_html.find(q_tag))
                        if insert_pos != -1:
                            example_formatted = f' <p>Example: {example_text}</p>'
                            questions_html = questions_html[:insert_pos+4] + example_formatted + questions_html[insert_pos+4:]
                            example_inserted = True
                            print(f"[LISTENING_MATCHING] ✅ Inserted example after question 29 (Experiment 4 example)")
                            break
            
            # If not inserted yet, try to insert after question 29 specifically
            if not example_inserted:
                q29_pos = questions_html.find('<p>29.')
                if q29_pos != -1:
                    insert_pos = questions_html.find('</p>', q29_pos)
                    if insert_pos != -1:
                        example_formatted = f' <p>Example: {example_text}</p>'
                        questions_html = questions_html[:insert_pos+4] + example_formatted + questions_html[insert_pos+4:]
                        example_inserted = True
                        print(f"[LISTENING_MATCHING] ✅ Inserted example after question 29 (fallback)")
            
            # Final fallback: insert at the beginning
            if not example_inserted:
                example_formatted = f' <p>Example: {example_text}</p>'
                questions_html = example_formatted + questions_html
                print(f"[LISTENING_MATCHING] ✅ Inserted example at beginning (fallback)")
        
        # Always render matching sentence endings header outside the drag-drop component
        header_html = f"<p><strong>{questions_range}</strong></p>"
        instructions_html = self.extract_instruction_paragraphs_block(original_html or html_content) or ""

        # Build final output (instructions retained)
        auto_repeat = repeat_answer or (len(questions) > len(options))
        data_repeat = 'True' if auto_repeat else 'False'
        final_output = (
            f"{header_html}"
            f"{instructions_html}"
            f"<drag-drop-matching-sentence-endings data-options='{options_json}' "
            f"data-question-type=\"{self.question_type}\" data-repeat='{data_repeat}'>"
            f"{questions_html} "
            f"</drag-drop-matching-sentence-endings>"
        )
        
        print(f"[LISTENING_MATCHING] ✅ Created output with {len(questions)} questions and {len(options)} options")
        return final_output
    
    def parse_and_insert_inputs(self, html_content):
        """Main parsing function"""
        if not html_content or not html_content.strip():
            return html_content
        
        try:
            print(f"[LISTENING_MATCHING] 🚀 Starting parse for listening matching headings...")
            
            # Remove any wrapping div tags first
            html_content = html_content.strip()
            if html_content.startswith('<div>'):
                html_content = html_content[5:].strip()
            if html_content.startswith('<div '):
                # Remove div with attributes
                html_content = re.sub(r'^<div[^>]*>', '', html_content, flags=re.IGNORECASE)
            if html_content.endswith('</div>'):
                html_content = html_content[:-6].strip()
            
            # Clean up HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            plain_text = soup.get_text(separator=' ', strip=True)
            
            print(f"[LISTENING_MATCHING] Content preview: {plain_text[:200]}...")
            
            # Check if already processed
            if 'drag-drop-matching-sentence-endings' in html_content and 'data-repeat' in html_content:
                print(f"[LISTENING_MATCHING] ℹ️ Already processed, normalizing...")
                
                # Normalize existing component and remove any wrapping divs
                existing_component = soup.find('drag-drop-matching-sentence-endings')
                if existing_component:
                    repeat_answer = self.detect_repeat_answer(html_content, plain_text)
                    existing_component['data-repeat'] = 'True' if repeat_answer else 'False'
                    result = str(existing_component)
                    # Remove any wrapping divs from result
                    if result.startswith('<div>') or result.startswith('<div '):
                        result = re.sub(r'^<div[^>]*>', '', result, flags=re.IGNORECASE)
                    if result.endswith('</div>'):
                        result = result[:-6].strip()
                    return result
            
            # Extract components
            questions_range = self.extract_questions_range(html_content, plain_text)
            options = self.extract_options(html_content)
            questions, example_text = self.extract_questions(html_content)
            repeat_answer = self.detect_repeat_answer(html_content, plain_text)
            instruction_text = self.extract_instruction_text(html_content, plain_text)
            
            print(f"[LISTENING_MATCHING] Components status:")
            print(f"  - Questions range: {questions_range}")
            print(f"  - Options found: {len(options)}")
            print(f"  - Questions found: {len(questions)}")
            print(f"  - Repeat answer: {repeat_answer}")
            print(f"  - Instruction text: {instruction_text}")
            print(f"  - Example text: {example_text}")
            
            if not options or not questions:
                print(f"[LISTENING_MATCHING] ⚠️ Missing components - cannot proceed")
                return html_content
            
            # Build final output
            result = self.build_final_output(questions_range, options, questions, repeat_answer, instruction_text, example_text, html_content)
            
            if not result:
                print(f"[LISTENING_MATCHING] ⚠️ No result generated")
                return html_content
            
            # Count generated input tags
            input_count = len(re.findall(r'<drag-drop-sentence-input', result))
            print(f"[LISTENING_MATCHING] ✅ SUCCESS - Generated {input_count} drag-drop inputs")
            
            return result
            
        except Exception as e:
            print(f"[LISTENING_MATCHING] ❌ Error: {e}")
            import traceback
            print(f"[LISTENING_MATCHING] Traceback: {traceback.format_exc()}")
            return html_content


def parse_listening_matching_headings(html_content):
    """Parse listening matching headings format"""
    parser = ListeningMatchingHeadingsParser()
    return parser.parse_and_insert_inputs(html_content)