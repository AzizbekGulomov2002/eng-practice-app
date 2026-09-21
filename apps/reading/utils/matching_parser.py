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

        # ENHANCED: Strong indicators for matching sentence endings (especially "Complete each sentence with the correct ending")
        strong_indicators = [
            'complete each sentence with the correct ending' in content_lower,
            'complete each sentence with the correct ending,' in content_lower,
            'correct ending' in content_lower and 'complete each sentence' in content_lower,
        ]
        
        if any(strong_indicators):
            print(f"[MATCHING_PARSER] ✅ STRONG INDICATOR: 'Complete each sentence with the correct ending' detected")
            return True

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
            tag_text = tag.get_text(strip=True)

            # Skip instruction elements (but NOT if they also contain question numbers)
            skip_indicators = [
                'complete the summary using',
                'complete the summary with',
                'list of phrases',
                'list of words',
                'using the list',
                ', below',
                'a-l, below',
                'a-p, below'
            ]

            tag_lower = text.lower()
            has_question_number = bool(re.search(r'<strong>\d+</strong>', text))
            
            # Only skip if it's an instruction element AND doesn't have question numbers
            if any(skip in tag_lower for skip in skip_indicators) and not has_question_number:
                continue

            # Skip "write the correct letter" instruction ONLY if it doesn't contain question numbers
            if 'write the correct letter' in tag_lower and not has_question_number:
                continue

            # Skip empty elements
            if not tag_text:
                continue

            # Skip option elements - detect multiple letters in one element (but allow if it has question numbers)
            option_letters = re.findall(r'<strong>[A-Z]</strong>', text)
            if len(option_letters) > 2 and not has_question_number:
                continue

            # Check if this element has question numbers - THIS IS THE KEY CHECK
            if has_question_number:
                question_elements.append(str(tag))
                print(f"[MATCHING_PARSER] ✅ Found question element: {tag_text[:100]}...")

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
                        f"<drag-drop-sentence-input data-question-number=\"{q_num}\" data-question-type=\"{self.question_type}\">…</drag-drop-sentence-input><br/></p>"
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

    def build_final_output_with_all_questions(self, questions_range, options, content_with_questions, repeat_flag=False, original_html="", question_type="matching_sentence_endings"):
        """Build final output with ALL questions included - using drag-drop-matching-sentence-endings format"""
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
<drag-drop-matching-sentence-endings data-options='{options_json}' data-question-type="{question_type}" data-repeat="{data_repeat}">
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
            result = self.build_final_output_with_all_questions(questions_range, options, processed_content, repeat_flag, cleaned_content, question_type="matching_sentence_endings")

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
            r'<p><strong>\s*(\d+)\s*(?:&nbsp;)?\s*</strong>\s*(?:&nbsp;)*\s*([^<]{5,300}?)</p>',
            r'<strong>(\d+)&nbsp;</strong>&nbsp;&nbsp;([^<]{5,300}?)(?=<|$)',
            r'<strong>\s*(\d+)\s*</strong>[^a-zA-Z]*([a-zA-Z][^<]{5,300}?)(?=<|$)',
            r'<p><strong>(\d+)</strong>\s*(?:&nbsp;)*([^<]+?)</p>',
            r'<p><strong>(\d+)\.?\s*</strong>\s*([^<]+?)</p>',
            r'<strong>(\d+)\s*</strong>\s*([^<]+?)(?=<strong>|</p>|$)',  # More flexible pattern
            r'(\d+)\.\s*([a-zA-Z][^<\n]{10,200}?)(?=\n|\d+\.|\s*</)',
            r'\.(\d+)\s+([a-zA-Z][^<]{10,200}?)(?=<strong>|</p>|$)',  # Handle ".7 Question text" format
            r'\.(\d+)\s*([A-Z][^<]{10,200}?)(?=<strong>|</p>|$)',  # Handle ".7Question text" format (no space)
            r'<p>([^<]*?)(\d+)\s+([A-Z][^<]{10,200}?)</p>',  # Handle "NB text.7 Question text" in paragraph
        ]
        
        # Special handling for pattern with 3 groups (NB text.7 Question text)
        for i, pattern in enumerate(question_patterns):
            print(f"[MATCHING_UNIVERSAL] Trying pattern {i+1}: {pattern[:50]}...")
            matches = list(re.finditer(pattern, html_content, re.DOTALL | re.IGNORECASE))
            print(f"[MATCHING_UNIVERSAL] Pattern {i+1} found {len(matches)} matches")

            for match in matches:
                # Handle patterns with 3 groups (NB text.7 Question text)
                if len(match.groups()) == 3:
                    q_num = match.group(2).strip()  # Question number is in group 2
                    q_text = match.group(3).strip()  # Question text is in group 3
                else:
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
            print(f"[MATCHING_UNIVERSAL] No HTML matches, trying plain text extraction...")
            plain_text_content = BeautifulSoup(html_content, 'html.parser').get_text()

            text_patterns = [
                r'(\d+)\.\s*([a-z][^.]{15,200}(?:\.|$))',
                r'(\d+)\s+([a-z][^0-9]{15,200}?)(?=\d+\s|$)',
                r'\.(\d+)\s+([A-Z][^.]{15,200}?)(?=\.|$|\d)',  # Handle ".7 Question text" format in plain text
                r'nb[^.]*\.(\d+)\s+([A-Z][^.]{15,200}?)(?=\.|$|\d)',  # Handle "NB...once.7 Question text" format
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
        options_map = {}
        
        # Pattern 0: Handle options in single paragraph with <br /> separators
        # Format: <p><strong>A</strong> Label<br /><strong>B</strong> Label<br />...</p>
        multi_option_pattern = r'<p[^>]*>(.*?)</p>'
        multi_option_matches = re.finditer(multi_option_pattern, html_content, re.IGNORECASE | re.DOTALL)
        for match in multi_option_matches:
            paragraph_content = match.group(1)
            # Check if this paragraph contains multiple <strong>Letter</strong> patterns with <br />
            option_matches = re.finditer(r'<strong>\s*([A-Z])\s*</strong>\s*([^<]+?)(?=<br\s*/?>|<strong>|$)', paragraph_content, re.IGNORECASE | re.DOTALL)
            found_options = []
            for opt_match in option_matches:
                letter = opt_match.group(1).upper()
                label = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', opt_match.group(2))
                label = re.sub(r'\s+', ' ', label).strip()
                label = re.sub(r'^[^\w]*|[^\w]*$', '', label)
                
                # Skip invalid labels
                if len(label) >= 3 and label.lower() not in ['in boxes', 'on your', 'answer sheet', 'boxes', 'sheet', 'correct letter', 'or']:
                    found_options.append((letter, label))
            
            # If we found multiple options in this paragraph, add them
            if len(found_options) >= 2:
                for letter, label in found_options:
                    if letter not in options_map:
                        options_map[letter] = label
                        print(f"[OPTIONS_UNIVERSAL] ✅ Extracted option {letter} from multi-option paragraph: '{label}'")
        
        # Pattern 1-2: Standard separate paragraph formats
        explicit_patterns = [
            r'<p[^>]*>\s*<strong>\s*([A-Z])\s*[^<]*</strong>\s*([^<]+?)</p>',  # Standard format
            r'<p[^>]*>\s*<strong>\s*([A-Z])\s*</strong>\s*([^<]+?)</p>',     # Simple format
        ]
        
        for pattern in explicit_patterns:
            for m in re.finditer(pattern, html_content, re.IGNORECASE | re.DOTALL):
                letter = m.group(1).upper()
                full_match = m.group(0)
                
                # EXCLUDE: Skip if this match contains a range pattern like A-J
                if re.search(r'<strong>\s*[A-Z]\s*[-–]\s*[A-Z]\s*</strong>', full_match, re.IGNORECASE):
                    print(f"[OPTIONS_UNIVERSAL] ⏭️ Skipping match with range pattern: {full_match[:100]}")
                    continue
                
                label = re.sub(r'&nbsp;|\xa0|&amp;nbsp;', ' ', m.group(2))
                label = re.sub(r'\s+', ' ', label).strip()
                label = re.sub(r'^[^\w]*|[^\w]*$', '', label)
                
                # EXCLUDE: Skip if this looks like a range pattern (e.g., "A-J" should not be parsed as option A with label "-J")
                if re.match(r'^[-–]\s*[A-Z]$', label, re.IGNORECASE):
                    print(f"[OPTIONS_UNIVERSAL] ⏭️ Skipping range pattern: {letter}-{label}")
                    continue
                
                # EXCLUDE: Skip if label is too short or doesn't look like a real option label
                # Real option labels should be at least 3 characters of meaningful text
                if len(label) < 3 or label.lower() in ['in boxes', 'on your', 'answer sheet', 'boxes', 'sheet', 'correct letter']:
                    print(f"[OPTIONS_UNIVERSAL] ⏭️ Skipping invalid label: {letter}-'{label}'")
                    continue
                
                if label and letter not in options_map:
                    options_map[letter] = label
                    print(f"[OPTIONS_UNIVERSAL] ✅ Extracted option {letter}: '{label}'")

        if options_map:
            ordered = []
            for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                if letter in options_map:
                    ordered.append({'value': letter, 'label': options_map[letter]})
            if ordered:
                # Safety check: If we only found 1-2 options and the input mentions a range like A-J,
                # we should check for range detection instead
                if len(ordered) <= 2:
                    # Check if there's a range mentioned in the content
                    range_check = re.search(r'([A-Z])\s*[-–]\s*([A-Z])', html_content, re.IGNORECASE)
                    if range_check:
                        start_letter = range_check.group(1).upper()
                        end_letter = range_check.group(2).upper()
                        expected_count = ord(end_letter) - ord(start_letter) + 1
                        if expected_count > len(ordered):
                            print(f"[OPTIONS_UNIVERSAL] ⚠️ Found only {len(ordered)} options but range suggests {expected_count}, falling back to range detection")
                            options_map = {}  # Clear to fall through to range detection
                        else:
                            print(f"[OPTIONS_UNIVERSAL] ✅ Explicit options extracted: {len(ordered)}")
                            return ordered
                    else:
                        print(f"[OPTIONS_UNIVERSAL] ✅ Explicit options extracted: {len(ordered)}")
                        return ordered
                else:
                    print(f"[OPTIONS_UNIVERSAL] ✅ Explicit options extracted: {len(ordered)}")
                    return ordered

        # 2) If no explicit pairs, detect range from instructions (A–G, A–J, etc.)
        # Check both HTML and plain text for range patterns
        range_patterns = [
            r'<strong>\s*([A-Z])\s*[-–]\s*([A-Z])\s*</strong>',  # <strong>A-J</strong> format (PRIORITY)
            r'<strong>([A-Z])[-–]([A-Z])</strong>',  # <strong>A-J</strong> without spaces
            r'paragraphs[,\s]+(?:&nbsp;)?<strong>([A-Z])\s*[-–]\s*([A-Z])</strong>',  # HTML format
            r'sections?[,\s]+(?:&nbsp;)?<strong>([A-Z])\s*[-–]\s*([A-Z])</strong>',  # Section format
            r'correct letter[,\s]+(?:&nbsp;)?<strong>([A-Z])\s*[-–]\s*([A-Z])</strong>',  # Write correct letter format
            r'([A-Z])\s*[-–]\s*([A-Z])',  # Plain text format
        ]
        
        instr_range = None
        for pattern in range_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                instr_range = match
                print(f"[OPTIONS_UNIVERSAL] ✅ Found range pattern: {match.group(0)} -> {match.group(1)}-{match.group(2)}")
                break
        
        if not instr_range:
            instr_range = re.search(r'([A-Z])\s*[-–]\s*([A-Z])', plain_text, re.IGNORECASE)
            if instr_range:
                print(f"[OPTIONS_UNIVERSAL] ✅ Found range in plain text: {instr_range.group(0)} -> {instr_range.group(1)}-{instr_range.group(2)}")
        
        if instr_range:
            start = instr_range.group(1).upper()
            end = instr_range.group(2).upper()
            letters = [chr(c) for c in range(ord(start), ord(end) + 1)]
            print(f"[OPTIONS_UNIVERSAL] 📊 Range detected: {start}-{end} -> Letters: {letters}")
            
            # First try to find explicit paragraphs with these letters
            found = []
            for letter in letters:
                # Find the first paragraph starting with this letter
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
            # IMPORTANT: Use just the letter as label, not "Section A" or "Paragraph A"
            print(f"[OPTIONS_UNIVERSAL] 🔄 Creating synthetic options: {start}-{end}")
            synthetic_options = []
            for letter in letters:
                # Use just the letter as the label (e.g., "A" not "Section A")
                synthetic_options.append({
                    'value': letter,
                    'label': letter  # Just the letter itself
                })
            print(f"[OPTIONS_UNIVERSAL] ✅ Synthetic options created: {len(synthetic_options)} (labels: {[opt['label'] for opt in synthetic_options]})")
            return synthetic_options

        # 3) As a last resort, return empty; caller will decide
        print(f"[OPTIONS_UNIVERSAL] ❌ No options extracted")
        return []

    def create_perfect_component(self, questions, options, table_name="List", repeat_answer=False, has_table_context=False, questions_range="Questions 1-5"):
        """Create table-tegs-input component for matching information WITHOUT instructions (instructions come from HTML)."""
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

        # Always use table-tegs-input format with data-options
        table_tegs_input = (
            f'<table-tegs-input data-options=\'{options_json}\' '
            f'data-question-type="matching_information" '
            f'data-questions=\'{questions_json}\' '
            f'repeat_answer="{str(repeat_answer)}" '
            f'table_name="{table_name}"></table-tegs-input>'
        )
        component = table_tegs_input

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

                # Replace existing tag with clean component (table-tegs-input)
                new_tag = BeautifulSoup(clean_component, 'html.parser').find(['table-tegs', 'table-tegs-input'])
                
                if new_tag:
                    # If tag names differ replace entirely; otherwise refresh attributes
                    if existing_table.name != new_tag.name:
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
                    
                    soup_cleanup = BeautifulSoup(html_content, 'html.parser')
                    
                    if not skip_cleanup:
                        # 1) Remove question range headers (Questions 14-18, etc.) from h1-h6
                        # BUT: Keep "Questions X-Y" if it matches our question range (it's part of instructions)
                        for tag in list(soup_cleanup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])):
                            text = tag.get_text(strip=True).lower()
                            if re.search(r'questions?\s+\d+', text):
                                # Check if this matches our question range
                                # Extract question range from text (e.g., "questions 1-3" -> "1-3")
                                range_match = re.search(r'questions?\s+(\d+)[-–]?(\d+)?', text, re.IGNORECASE)
                                if range_match:
                                    start_q = int(range_match.group(1))
                                    end_q = int(range_match.group(2)) if range_match.group(2) else start_q
                                    # Check if any of our questions fall in this range
                                    our_questions = [int(q['question_number']) for q in questions]
                                    if any(start_q <= q_num <= end_q for q_num in our_questions):
                                        # This is OUR question range header - KEEP IT!
                                        continue
                                # Otherwise, remove it
                                tag.decompose()
                        
                        # 2) Remove standalone <strong>Questions X-Y</strong> tags
                        # BUT: Keep "Questions X-Y" if it matches our question range
                        for strong in list(soup_cleanup.find_all('strong')):
                            strong_text = strong.get_text(strip=True).lower()
                            if re.search(r'questions?\s+\d+\s*[-–]\s*\d+', strong_text) or re.search(r'questions?\s+\d+', strong_text):
                                # Check if this matches our question range
                                range_match = re.search(r'questions?\s+(\d+)[-–]?(\d+)?', strong_text, re.IGNORECASE)
                                if range_match:
                                    start_q = int(range_match.group(1))
                                    end_q = int(range_match.group(2)) if range_match.group(2) else start_q
                                    # Check if any of our questions fall in this range
                                    our_questions = [int(q['question_number']) for q in questions]
                                    if any(start_q <= q_num <= end_q for q_num in our_questions):
                                        # This is OUR question range header - KEEP IT!
                                        continue
                                # Check if this strong is alone in a paragraph or standalone
                                parent = strong.parent
                                if parent and parent.name == 'p':
                                    # If paragraph only contains this strong tag, keep it if it's our range
                                    if len(parent.get_text(strip=True)) == len(strong_text):
                                        # Check if it's our question range
                                        range_match = re.search(r'questions?\s+(\d+)[-–]?(\d+)?', strong_text, re.IGNORECASE)
                                        if range_match:
                                            start_q = int(range_match.group(1))
                                            end_q = int(range_match.group(2)) if range_match.group(2) else start_q
                                            our_questions = [int(q['question_number']) for q in questions]
                                            if any(start_q <= q_num <= end_q for q_num in our_questions):
                                                # Keep this paragraph - it's our question range
                                                continue
                                        parent.decompose()
                                    else:
                                        strong.decompose()
                                else:
                                    strong.decompose()
                        
                        # 3) Remove instruction paragraphs
                        # BUT: Keep NB instruction paragraphs - they're part of instructions that should stay
                        instruction_patterns = [
                            r'reading passage.*paragraphs',
                            r'which paragraph contains',
                            r'which section contains',
                            r'write the correct letter',
                            r'in boxes.*answer sheet',
                            # NOTE: NB instruction is NOT removed here - it stays as part of instructions
                            r'you may use any letter more than once',  # Only if NOT preceded by NB
                            r'look at the following statements',
                            r'match each statement',
                            r'list of.*below',
                            r'correct theory',
                            r'correct person',
                            r'correct timber'
                        ]
                        
                        for p in list(soup_cleanup.find_all('p')):
                            p_text = p.get_text(strip=True).lower()
                            
                            # IMPORTANT: NEVER remove NB instruction paragraphs - they stay before component
                            if re.search(r'nb.*you may use any letter', p_text, re.IGNORECASE):
                                continue  # Keep NB paragraphs
                            
                            # IMPORTANT: NEVER remove paragraphs that contain question numbers or question text
                            # Check if this paragraph contains a question number
                            contains_question_number = False
                            strong_tags = p.find_all('strong')
                            for strong in strong_tags:
                                strong_text = strong.get_text(strip=True)
                                # Check if it's a question number
                                if strong_text.replace('&nbsp;', '').strip().isdigit():
                                    contains_question_number = True
                                    break
                            
                            # Also check if paragraph contains question text (long content after a number)
                            if not contains_question_number:
                                # Check for patterns like ".7 Question text" or "7 Question text"
                                if re.search(r'[.\s](\d+)\s+[A-Z][^<]{15,}', str(p), re.IGNORECASE):
                                    contains_question_number = True
                                
                                # Check if it's a long paragraph that looks like question text
                                text_length = len(p.get_text(strip=True))
                                if text_length > 40:  # Long paragraphs are likely questions, not pure instructions
                                    contains_question_number = True
                            
                            # Skip removal if this paragraph contains question content
                            if contains_question_number:
                                continue
                            
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
                        
                        # Find all instruction paragraphs (including Questions X-Y, Reading Passage, and NB)
                        for p_tag in soup_cleanup.find_all('p'):
                            p_text = p_tag.get_text(strip=True).lower()
                            if any(keyword in p_text for keyword in [
                                'questions', 'reading passage', 'which section contains', 'which paragraph contains',
                                'look at the following', 'match each statement', 'write the correct letter',
                                'in boxes', 'answer sheet', 'nb'
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

                        # 4) Remove instruction paragraphs that appear AFTER the component
                        # BEFORE cleanup: Handle NB instruction that might be combined with question text
                        # Extract NB from paragraphs that contain both NB and question text
                        for p_tag in list(soup_cleanup.find_all('p')):
                            p_text = p_tag.get_text(separator=' ', strip=True)
                            txt_lower = p_text.lower()
                            
                            # Check if paragraph contains NB instruction
                            has_nb = bool(re.search(r'nb.*you may use any letter', txt_lower, re.IGNORECASE))
                            
                            if has_nb:
                                # Check if this paragraph also contains question text
                                contains_question = False
                                strong_tags = p_tag.find_all('strong')
                                for strong in strong_tags:
                                    strong_text = strong.get_text(strip=True)
                                    if strong_text.replace('&nbsp;', '').strip().isdigit():
                                        q_num = strong_text.replace('&nbsp;', '').strip()
                                        if q_num in question_numbers_set:
                                            contains_question = True
                                            break
                                
                                # If paragraph contains both NB and question, split it
                                if contains_question:
                                    # Extract NB part (everything before the question number)
                                    # Pattern: "NB ... You may use any letter more than once" followed by question number
                                    nb_match = re.search(r'(NB.*?you may use any letter more than once)', p_text, re.IGNORECASE | re.DOTALL)
                                    if nb_match:
                                        nb_text = nb_match.group(1).strip()
                                        
                                        # Always keep NB instruction paragraphs (they're part of instructions)
                                        # Extract just the NB part, remove question text
                                        from bs4 import NavigableString
                                        p_tag.clear()
                                        nb_strong = soup_cleanup.new_tag('strong')
                                        nb_strong.string = 'NB'
                                        p_tag.append(nb_strong)
                                        p_tag.append(NavigableString(' You may use any letter more than once.'))
                                        print(f"[NB] Extracted and kept NB instruction from paragraph with question")
                                    else:
                                        # Couldn't extract NB cleanly - keep the paragraph if it's before component
                                        # Check position relative to component insertion point
                                        instruction_paragraphs = []
                                        for p in soup_cleanup.find_all('p'):
                                            p_txt = p.get_text(strip=True).lower()
                                            if any(keyword in p_txt for keyword in [
                                                'questions', 'reading passage', 'which section contains', 'which paragraph contains',
                                                'look at the following', 'match each statement', 'write the correct letter',
                                                'in boxes', 'answer sheet'
                                            ]):
                                                instruction_paragraphs.append(p)
                                        
                                        # If it's an instruction paragraph, keep it
                                        if instruction_paragraphs and p_tag in instruction_paragraphs:
                                            # Keep the paragraph - it's part of instructions
                                            print(f"[NB] Keeping NB paragraph that's part of instructions")
                                        else:
                                            # Remove it if it comes after component
                                            p_tag.decompose()
                                    
                                    continue
                        
                        # Now continue with normal cleanup
                        # Find the component tag (table-tegs or table-tegs-input)
                        component_tag = soup_cleanup.find(['table-tegs', 'table-tegs-input'])
                        
                        if component_tag:
                            # Get ALL elements that come AFTER the component tag
                            elements_after_component = component_tag.find_all_next()
                            
                            # Remove instruction paragraphs that come AFTER the component
                            for p_tag in list(soup_cleanup.find_all('p')):
                                # Skip if paragraph is inside component tag
                                parent = p_tag.parent
                                skip = False
                                while parent:
                                    if parent.name in ['table-tegs', 'table-tegs-input']:
                                        skip = True
                                        break
                                    parent = parent.parent
                                
                                if skip:
                                    continue
                                
                                # Check if this paragraph comes AFTER the component tag
                                if p_tag in elements_after_component:
                                    txt = p_tag.get_text(separator=' ', strip=True).lower()
                                    
                                    # Check if this paragraph matches instruction patterns
                                    instruction_patterns_after = [
                                        r'look at the following statements',
                                        r'match each statement',
                                        r'write the correct letter',
                                        r'which paragraph contains',
                                        r'which section contains',
                                        r'reading passage.*has.*sections',
                                        r'reading passage.*has.*paragraphs',
                                        r'reading passage.*sections',
                                        r'reading passage.*paragraphs',
                                        r'list of.*below',
                                        r'correct theory',
                                        r'correct person',
                                        r'correct timber',
                                        r'you may use any letter more than once',
                                        r'nb.*you may use any letter'
                                    ]
                                    
                                    # IMPORTANT: NB instruction paragraphs that come BEFORE component should ALWAYS stay
                                    # Check if this paragraph contains NB instruction
                                    has_nb_instruction = bool(re.search(r'nb.*you may use any letter', txt, re.IGNORECASE))
                                    if has_nb_instruction:
                                        # Check if paragraph comes BEFORE component in document order
                                        # Get component position
                                        comp_pos = list(soup_cleanup.descendants).index(component_tag) if component_tag in soup_cleanup.descendants else -1
                                        p_pos = list(soup_cleanup.descendants).index(p_tag) if p_tag in soup_cleanup.descendants else -1
                                        
                                        # If NB paragraph comes BEFORE component, KEEP IT
                                        if comp_pos != -1 and p_pos != -1 and p_pos < comp_pos:
                                            print(f"[NB] Keeping NB paragraph that comes before component: {txt[:100]}")
                                            continue  # Keep this paragraph - it's before component
                                        else:
                                            # NB paragraph comes AFTER component - remove it
                                            print(f"[CLEANUP] Removing NB paragraph that comes after component: {txt[:100]}")
                                            p_tag.decompose()
                                            continue
                                    
                                    paragraph_text_plain = p_tag.get_text(separator=' ', strip=True)
                                    
                                    # Check if paragraph contains question number pattern (like ".7" or "7   Question text")
                                    contains_question_number = False
                                    question_number_found = None
                                    
                                    # Check for patterns like "once.7" or ".7" or "7   Question text"
                                    nb_question_patterns = [
                                        r'nb.*?once\.\s*(\d+)',
                                        r'once\.\s*(\d+)',
                                        r'\.(\d+)\s+[A-Z]',
                                        r'(\d+)\s{2,}[A-Z]'
                                    ]
                                    
                                    for pattern in nb_question_patterns:
                                        match = re.search(pattern, paragraph_text_plain, re.IGNORECASE)
                                        if match:
                                            q_num_candidate = match.group(1).strip()
                                            if q_num_candidate in question_numbers_set:
                                                contains_question_number = True
                                                question_number_found = q_num_candidate
                                                break
                                    
                                    # Also check strong tags for question numbers
                                    if not contains_question_number:
                                        strong_tags = p_tag.find_all('strong')
                                        for strong in strong_tags:
                                            strong_text = strong.get_text(strip=True)
                                            if strong_text.replace('&nbsp;', '').strip().isdigit():
                                                q_num_candidate = strong_text.replace('&nbsp;', '').strip()
                                                if q_num_candidate in question_numbers_set:
                                                    contains_question_number = True
                                                    question_number_found = q_num_candidate
                                                    break
                                    
                                    # CRITICAL: If paragraph contains BOTH NB instruction AND extracted question number, REMOVE it
                                    # Both are already in the component, so this is a duplicate
                                    if has_nb_instruction and contains_question_number:
                                        print(f"[CLEANUP] Removing duplicate NB + Question {question_number_found} paragraph (both already in component): {txt[:100]}")
                                        p_tag.decompose()
                                        continue
                                    
                                    # If paragraph matches instruction patterns, remove it (even if it contains question text)
                                    # because questions are already extracted and in the component
                                    matches_instruction = False
                                    for pattern in instruction_patterns_after:
                                        if re.search(pattern, txt):
                                            matches_instruction = True
                                            break
                                    
                                    # Remove if it matches instruction patterns (duplicate instruction)
                                    if matches_instruction:
                                        print(f"[CLEANUP] Removing duplicate instruction paragraph after component: {txt[:100]}")
                                        p_tag.decompose()
                                        continue
                                    
                                    # CRITICAL: Check if this paragraph starts a NEW question section
                                    # If it contains "Questions X-Y" or "Question X", it's a new section - STOP cleanup
                                    new_section_patterns = [
                                        r'<strong>questions?\s+\d+[-–—]\d+</strong>',
                                        r'<strong>questions?\s+\d+\s+and\s+\d+</strong>',
                                        r'<strong>question\s+\d+</strong>',
                                        r'questions?\s+\d+[-–—]\d+',
                                        r'questions?\s+\d+\s+and\s+\d+',
                                    ]
                                    
                                    is_new_section = False
                                    p_html = str(p_tag)
                                    for pattern in new_section_patterns:
                                        if re.search(pattern, p_html, re.IGNORECASE):
                                            is_new_section = True
                                            print(f"[CLEANUP] Found new question section, stopping cleanup: {txt[:100]}")
                                            break
                                    
                                    # If this is a new section, STOP removing paragraphs
                                    if is_new_section:
                                        break  # Exit the cleanup loop - don't remove this or subsequent paragraphs
                                    
                                    # MODIFIED: Only remove paragraphs that are clearly part of THIS matching section
                                    # Don't remove if it contains completion patterns (like "24__________")
                                    has_completion_gap = bool(re.search(r'\d+_{3,}', str(p_tag)))
                                    has_completion_keywords = any(kw in txt for kw in ['complete the summary', 'complete the sentences', 'one word only', 'two words only'])
                                    
                                    if has_completion_gap or has_completion_keywords:
                                        print(f"[CLEANUP] Keeping paragraph with completion content: {txt[:100]}")
                                        continue  # Don't remove - it's a different question type
                                    
                                    # Only remove if it's clearly part of the matching section (contains question numbers from this section)
                                    if p_tag in elements_after_component:
                                        # Check if paragraph contains question numbers from the extracted questions
                                        contains_extracted_question = False
                                        for strong in p_tag.find_all('strong'):
                                            strong_text = strong.get_text(strip=True)
                                            if strong_text.replace('&nbsp;', '').strip() in question_numbers_set:
                                                contains_extracted_question = True
                                                break
                                        
                                        if contains_extracted_question:
                                            print(f"[CLEANUP] Removing paragraph with extracted question: {txt[:100]}")
                                            p_tag.decompose()
                                            continue
                                        else:
                                            # Don't remove - might be a different section
                                            print(f"[CLEANUP] Keeping paragraph (not part of extracted questions): {txt[:50]}...")
                                    
                                    # Also check if paragraph contains ONLY question content (no instruction text)
                                    # If it's a pure question paragraph without instruction text, we might want to keep it
                                    # But if it's already extracted, we can remove it
                                    strong_tags = p_tag.find_all('strong')
                                    for strong in strong_tags:
                                        strong_text = strong.get_text(strip=True)
                                        # Check if it's a question number that's already extracted
                                        if strong_text.replace('&nbsp;', '').strip().isdigit():
                                            q_num = strong_text.replace('&nbsp;', '').strip()
                                            if q_num in question_numbers_set:
                                                # This question is already extracted, remove duplicate
                                                print(f"[CLEANUP] Removing duplicate question paragraph (Q{q_num} already in component): {txt[:100]}")
                                                p_tag.decompose()
                                                break
                        else:
                            # If no component found, still remove duplicate instruction paragraphs
                            for p_tag in list(soup_cleanup.find_all('p')):
                                txt = p_tag.get_text(separator=' ', strip=True).lower()
                                
                                instruction_patterns_after = [
                                    r'look at the following statements',
                                    r'match each statement',
                                    r'write the correct letter',
                                    r'which paragraph contains',
                                    r'which section contains',
                                    r'list of.*below',
                                    r'correct theory',
                                    r'correct person',
                                    r'correct timber',
                                    r'you may use any letter more than once'
                                ]
                                
                                for pattern in instruction_patterns_after:
                                    if re.search(pattern, txt):
                                        p_tag.decompose()
                                        break

                        # FINAL CLEANUP: Remove elements that are part of THIS matching section
                        # BUT: Stop at the next question section (don't remove other question types)
                        component_tag = soup_cleanup.find(['table-tegs', 'table-tegs-input'])
                        if component_tag:
                            # Get all elements that come after component
                            all_elements_after = component_tag.find_all_next()
                            
                            # Remove elements that are part of this matching section
                            for element in list(all_elements_after):
                                # Skip if element is inside component tag
                                parent = element.parent
                                skip = False
                                while parent:
                                    if parent.name in ['table-tegs', 'table-tegs-input']:
                                        skip = True
                                        break
                                    parent = parent.parent
                                
                                if not skip:
                                    # Check if this element starts a NEW question section
                                    element_html = str(element)
                                    element_text = element.get_text(strip=True).lower() if hasattr(element, 'get_text') else ''
                                    
                                    # Patterns that indicate a new question section
                                    new_section_patterns = [
                                        r'<strong>questions?\s+\d+[-–—]\d+</strong>',
                                        r'<strong>questions?\s+\d+\s+and\s+\d+</strong>',
                                        r'<strong>question\s+\d+</strong>',
                                    ]
                                    
                                    is_new_section = any(re.search(pattern, element_html, re.IGNORECASE) for pattern in new_section_patterns)
                                    
                                    # Also check for completion patterns
                                    has_completion_gap = bool(re.search(r'\d+_{3,}', element_html))
                                    has_completion_keywords = any(kw in element_text for kw in ['complete the summary', 'complete the sentences', 'one word only', 'two words only'])
                                    
                                    if is_new_section:
                                        print(f"[CLEANUP] Final: Found new question section, stopping cleanup")
                                        break  # Stop removing - this is a new section
                                    
                                    if has_completion_gap or has_completion_keywords:
                                        print(f"[CLEANUP] Final: Found completion content, stopping cleanup")
                                        break  # Stop removing - this is a different question type
                                    
                                    # Only remove if it contains question numbers from the extracted set
                                    should_remove = False
                                    if element.name == 'p':
                                        for strong in element.find_all('strong'):
                                            strong_text = strong.get_text(strip=True)
                                            if strong_text.replace('&nbsp;', '').strip() in question_numbers_set:
                                                should_remove = True
                                                break
                                    
                                    if should_remove:
                                        if hasattr(element, 'decompose'):
                                            print(f"[CLEANUP] Final: Removing element with extracted question: {element.name} - {element_text[:50]}")
                                            element.decompose()
                                        elif hasattr(element, 'extract'):
                                            element.extract()
                                    else:
                                        # Don't remove - might be a different section
                                        print(f"[CLEANUP] Final: Keeping element (not part of this section): {element.name} - {element_text[:50]}")
                            
                            # Final safety check: remove any remaining paragraphs after component
                            # BUT: Keep NB instruction paragraphs that come before component
                            for p_tag in list(soup_cleanup.find_all('p')):
                                # Skip if paragraph is inside component tag
                                parent = p_tag.parent
                                skip = False
                                while parent:
                                    if parent.name in ['table-tegs', 'table-tegs-input']:
                                        skip = True
                                        break
                                    parent = parent.parent
                                
                                if skip:
                                    continue
                                
                                # IMPORTANT: Keep NB instruction paragraphs that come before component
                                p_text = p_tag.get_text(strip=True).lower()
                                has_nb = bool(re.search(r'nb.*you may use any letter', p_text, re.IGNORECASE))
                                if has_nb:
                                    # Check if NB comes before component
                                    comp_pos = list(soup_cleanup.descendants).index(component_tag) if component_tag in soup_cleanup.descendants else -1
                                    p_pos = list(soup_cleanup.descendants).index(p_tag) if p_tag in soup_cleanup.descendants else -1
                                    if comp_pos != -1 and p_pos != -1 and p_pos < comp_pos:
                                        # NB comes before component - KEEP IT
                                        continue
                                
                                # Check position: if component comes before this paragraph in the DOM, check if we should remove it
                                # Get all elements in order
                                all_p_tags = list(soup_cleanup.find_all('p'))
                                component_tags = soup_cleanup.find_all(['table-tegs', 'table-tegs-input'])
                                
                                if component_tags:
                                    comp = component_tags[0]
                                    # Check if paragraph comes after component in document order
                                    comp_pos = list(soup_cleanup.descendants).index(comp) if comp in soup_cleanup.descendants else -1
                                    p_pos = list(soup_cleanup.descendants).index(p_tag) if p_tag in soup_cleanup.descendants else -1
                                    
                                    if comp_pos != -1 and p_pos != -1 and p_pos > comp_pos:
                                        # Paragraph comes after component - check if it's part of THIS section or a new section
                                        p_html = str(p_tag)
                                        p_text_lower = p_text.lower()
                                        
                                        # Check for new question section patterns
                                        new_section_patterns = [
                                            r'<strong>questions?\s+\d+[-–—]\d+</strong>',
                                            r'<strong>questions?\s+\d+\s+and\s+\d+</strong>',
                                            r'<strong>question\s+\d+</strong>',
                                        ]
                                        
                                        is_new_section = any(re.search(pattern, p_html, re.IGNORECASE) for pattern in new_section_patterns)
                                        
                                        # Check for completion patterns
                                        has_completion_gap = bool(re.search(r'\d+_{3,}', p_html))
                                        has_completion_keywords = any(kw in p_text_lower for kw in ['complete the summary', 'complete the sentences', 'one word only', 'two words only'])
                                        
                                        if is_new_section or has_completion_gap or has_completion_keywords:
                                            print(f"[CLEANUP] Final safety: Keeping paragraph (new section or different type): {p_tag.get_text(strip=True)[:50]}")
                                            continue  # Don't remove - it's a different section
                                        
                                        # Only remove if it contains question numbers from the extracted set
                                        should_remove = False
                                        for strong in p_tag.find_all('strong'):
                                            strong_text = strong.get_text(strip=True)
                                            if strong_text.replace('&nbsp;', '').strip() in question_numbers_set:
                                                should_remove = True
                                                break
                                        
                                        if should_remove:
                                            print(f"[CLEANUP] Final safety: Removing paragraph with extracted question: {p_tag.get_text(strip=True)[:50]}")
                                            p_tag.decompose()
                                        else:
                                            print(f"[CLEANUP] Final safety: Keeping paragraph (not part of extracted questions): {p_tag.get_text(strip=True)[:50]}")
                        
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
        patterns = [
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
                # Handle special cases for i-specific patterns (patterns 5, 6, 7, 8, 9)
                if i in [4, 5, 6, 7, 8]:  # Patterns 5, 6, 7, 8, 9 - only capture label
                    roman = 'i'
                    label = match
                else:
                    roman, label = match
                
                print(f"[MATCHING_HEADINGS] Raw match - {roman}: '{label[:50]}...'")
                # Clean up the label
                clean_label = re.sub(r'&nbsp;|\xa0', ' ', label)
                clean_label = re.sub(r'^\s*[^\w]*|\s*[^\w]*$', '', clean_label)
                clean_label = re.sub(r'\s+', ' ', clean_label).strip()
                
                # Remove any remaining "nbsp;" text
                clean_label = re.sub(r'^nbsp;\s*', '', clean_label)

                if clean_label and len(clean_label) >= 10:
                    options.append({'value': roman.lower(), 'label': clean_label})
                    print(f"[MATCHING_HEADINGS] ✅ Added option: {roman.lower()} -> '{clean_label[:30]}...'")
                else:
                    print(f"[MATCHING_HEADINGS] ❌ Rejected: '{clean_label}' (length: {len(clean_label)})")

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
            if len(re.findall(r'<strong>[ivxlc]+', text, re.IGNORECASE)) > 0 and not re.search(r'<strong>\d+</strong>', text):
                print(f"[MATCHING_HEADINGS] Skipping roman numeral element: {text[:100]}...")
                continue

            # Check if this element has question numbers
            if re.search(r'<strong>\d+</strong>', text):
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
        # Also look for the paragraph information that follows each example
        for i, tag in enumerate(soup.find_all(['p', 'div', 'span', 'td', 'th', 'li'])):
            text = tag.get_text().strip()
            if 'example' in text.lower() and 'answer' in text.lower():
                # Preserve the original HTML format of the example
                original_html = str(tag)
                
                # Look for the next paragraph that contains paragraph information
                next_paragraph = None
                for j in range(i + 1, len(soup.find_all(['p', 'div']))):
                    next_tag = soup.find_all(['p', 'div'])[j]
                    next_text = next_tag.get_text().strip()
                    if 'paragraph' in next_text.lower() and any(letter in next_text.upper() for letter in ['A', 'B', 'C', 'D', 'E', 'F']):
                        next_paragraph = str(next_tag)
                        break
                
                # Combine example and paragraph information
                if next_paragraph:
                    combined_example = f"{original_html} {next_paragraph}"
                    example_elements.append(combined_example)
                    print(f"[MATCHING_HEADINGS] ✅ Found example with paragraph: {combined_example[:100]}...")
                else:
                    example_elements.append(original_html)
                    print(f"[MATCHING_HEADINGS] ✅ Found example element: {original_html[:100]}...")
        
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
        example_index = 0
        
        # Create a mapping of question numbers to their positions in the original content
        question_positions = {}
        original_soup = BeautifulSoup(html_for_example, 'html.parser')
        all_paragraphs = original_soup.find_all(['p', 'div'])
        
        for i, tag in enumerate(all_paragraphs):
            text = tag.get_text().strip()
            # Look for question numbers in paragraphs
            question_match = re.search(r'^(\d+)\s+Paragraph', text)
            if question_match:
                question_num = question_match.group(1)
                question_positions[question_num] = i
        
        # Also create a mapping of example positions
        example_positions = {}
        for i, tag in enumerate(all_paragraphs):
            text = tag.get_text().strip()
            if 'example' in text.lower() and 'answer' in text.lower():
                example_positions[len(example_positions)] = i
        
        print(f"[MATCHING_HEADINGS] Question positions: {question_positions}")
        print(f"[MATCHING_HEADINGS] Example positions: {example_positions}")
        
        for i, element_html in enumerate(question_elements):
            element_soup = BeautifulSoup(element_html, 'html.parser')
            strong_tags = element_soup.find_all('strong')
            
            if len(strong_tags) >= 2:  # Question number + Paragraph letter
                question_num = strong_tags[0].get_text().strip()
                paragraph_text = element_soup.get_text().strip()
                
                # Clean up the paragraph text (remove question number)
                paragraph_text = re.sub(rf'^{question_num}\s*', '', paragraph_text).strip()
                
                # Add formatted question first
                current_line += f"<strong>{question_num}</strong> {paragraph_text} <drag-drop-sentence-input data-question-number=\"{question_num}\" data-question-type=\"{self.question_type}\">…</drag-drop-sentence-input><br/>"
                
                # Check if there's an example that should appear after this question
                current_question_pos = question_positions.get(question_num, -1)
                if current_question_pos != -1:
                    # Check if there's an example that appears after this question but before the next question
                    for ex_index, ex_pos in example_positions.items():
                        if ex_index == example_index and example_index < len(example_elements):
                            # Check if this example appears after the current question
                            next_question_pos = float('inf')
                            for next_q_num, next_q_pos in question_positions.items():
                                if next_q_pos > current_question_pos:
                                    next_question_pos = min(next_question_pos, next_q_pos)
                            
                            if current_question_pos < ex_pos < next_question_pos:
                                # This example should appear after the current question
                                current_line += f"<br> {example_elements[example_index]} <br> "
                                example_index += 1
                                break
        
        # Clean up and return
        final_content = current_line.strip()
        
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

    def build_final_output_with_all_questions(self, questions_range, options, content_with_questions):
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

        # Build final output with ALL questions - using drag-drop-matching-sentence-endings format
        # Don't include example text in instruction - let it appear in its natural position
        final_output = f"""<div><drag-drop-matching-sentence-endings data-options='{options_json}' data-question-type="matching_headings" data-repeat="false"> <h3><em><strong>{questions_range}</strong></em></h3> <p><em>Choose the correct heading for each section from the list of headings below. Write the correct number, <strong>{roman_range}</strong>, in boxes.</em></p> {content_with_questions} </drag-drop-matching-sentence-endings></div>"""

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

            # Build final result with ALL questions
            result = self.build_final_output_with_all_questions(questions_range, options, processed_content)

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