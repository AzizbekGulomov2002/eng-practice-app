from bs4 import BeautifulSoup
from django.db import models
from ckeditor.fields import RichTextField
import re
from apps.app.models import Users
from apps.reading.utils.completion_parser import parse_completion_questions
from apps.reading.utils.matching_parser import parse_matching_headings, parse_matching_information, parse_matching_sentence_endings
from apps.reading.utils.multiple_choice_perfect import parse_multiple_choice
from apps.reading.utils.true_false_parser import parse_true_false_questions
from apps.reading.utils.labelling_parser import parse_labelling_questions
from apps.reading.utils.label_table import convert_to_label_table, detect_label_table

class ReadingMaterial(models.Model):
    test_material = models.ForeignKey("app.TestMaterial", on_delete=models.CASCADE,related_name="reading_materials")
    title = models.CharField(max_length=200, null=True,blank=True)
    answer_time = models.PositiveIntegerField(default=3600, verbose_name="Answer Time (seconds)", help_text="Answer time (seconds)")
            
    def __str__(self):
        return f"{self.title if self.title else self.test_material.test.title}"

class Reading(models.Model):
    PASSAGE_CHOICES = (
        (1, "Passage 1"),
        (2, "Passage 2"),
        (3, "Passage 3"),
    )
    
    reading_material = models.ForeignKey(ReadingMaterial, on_delete=models.CASCADE, related_name='reading_materials')
    content = RichTextField(verbose_name="Reading Content")
    questions = RichTextField(verbose_name="Questions", blank=True)
    questions_raw = RichTextField(verbose_name="Original Questions (Unparsed)", blank=True, null=True, help_text="Stores original questions before parsing")
    passage_number = models.PositiveIntegerField(choices=PASSAGE_CHOICES, verbose_name="Passage Number")
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(null=True, blank=True)
    title = models.CharField(null=True, blank=True, max_length=200)
        
    def __str__(self):
        title_part = f" - {self.title}" if self.title else ""
        return f"{self.reading_material.title} | Passage {self.passage_number}{title_part}"

    def clean_malformed_tags(self, html_content):
        """Remove malformed tags that interfere with parsing"""
        if not html_content:
            return html_content
        
        print(f"[READING] 🧹 Cleaning malformed tags...")
        
        # Remove malformed <table-tegs> tags
        # These tags often contain corrupted data-attributes and interfere with parsing
        malformed_patterns = [
            r'<table-tegs[^>]*>.*?</table-tegs>',  # Full tag with closing
            r'<table-tegs[^>]*>',  # Self-closing or unclosed
        ]
        
        cleaned = html_content
        for pattern in malformed_patterns:
            matches = re.findall(pattern, cleaned, re.DOTALL | re.IGNORECASE)
            if matches:
                print(f"[READING] 🗑️ Removing {len(matches)} malformed tags matching pattern: {pattern[:50]}...")
                for match in matches:
                    print(f"[READING] Removing: {match[:100]}...")
                cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        
        if cleaned != html_content:
            print(f"[READING] ✅ Cleaned malformed tags successfully")
        else:
            print(f"[READING] ℹ️ No malformed tags found")
        
        return cleaned

    def find_existing_tags(self, html_content):
        """Find all existing question-input tags and their question numbers"""
        existing_tags = {}
        
        # Check for all types of question input tags
        patterns = [
            r'&lt;question-input[^&gt;]*data-question-number="(\d+)"[^&gt;]*data-question-type="([^"]*)"[^&gt;]*&gt;',
            r'&lt;drag-drop-sentence-input[^&gt;]*data-question-number="(\d+)"[^&gt;]*data-question-type="([^"]*)"[^&gt;]*&gt;',
            r'<question-input[^>]*data-question-number="(\d+)"[^>]*data-question-type="([^"]*)"[^>]*>',
            r'<drag-drop-sentence-input[^>]*data-question-number="(\d+)"[^>]*data-question-type="([^"]*)"[^>]*>',
            r'<table-tegs-input[^>]*data-question-type="([^"]*)"[^>]*>',  # NEW - for matching information
            r'<drag-drop-matching-sentence-endings[^>]*data-question-type="([^"]*)"[^>]*>',  # NEW - for matching headings
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, html_content)
            for match in matches:
                if len(match.groups()) >= 2:
                    question_number = int(match.group(1))
                    question_type = match.group(2)
                    existing_tags[question_number] = question_type
            
        # Also detect list-selection-tegs and mark all its question_numbers as existing
        try:
            for m in re.finditer(r'<list-selection-tegs[^>]*question_numbers=\'\[(.*?)\]\'[^>]*question_type="([^"]*)"[^>]*>', html_content):
                numbers_blob = m.group(1)
                qtype = m.group(2)
                for num in re.findall(r'"(\d+)"', numbers_blob):
                    try:
                        existing_tags[int(num)] = qtype
                    except Exception:
                        continue
        except Exception:
            pass
            
        # Also detect drag-drop-matching-sentence-endings and mark all its question_numbers as existing
        try:
            print(f"[READING] 🔍 Looking for drag-drop-matching-sentence-endings tags...")
            matches = list(re.finditer(r'<drag-drop-matching-sentence-endings[^>]*data-question-type="([^"]*)"[^>]*>', html_content))
            print(f"[READING] Found {len(matches)} drag-drop-matching-sentence-endings tags")
            
            for m in matches:
                qtype = m.group(1)
                print(f"[READING] Found drag-drop tag with type: {qtype}")
                # Find all question numbers within this tag
                tag_content = m.group(0)
                print(f"[READING] Tag content: {tag_content[:200]}...")
                for num_match in re.finditer(r'data-question-number="(\d+)"', tag_content):
                    try:
                        question_number = int(num_match.group(1))
                        existing_tags[question_number] = qtype
                        print(f"[READING] Added question {question_number} with type {qtype}")
                    except Exception as e:
                        print(f"[READING] Error processing question number: {e}")
                        continue
        except Exception as e:
            print(f"[READING] Error in drag-drop detection: {e}")
            pass

        print(f"[READING] 🏷️ Found {len(existing_tags)} existing question-input tags: {existing_tags}")
        return existing_tags

    def split_question_sections(self, html_content):
        """ENHANCED section splitting - detects ALL header formats"""
        print(f"[READING] 🔪 ENHANCED: Splitting content into question sections...")
        
        # COMPREHENSIVE patterns for ALL possible header formats
        header_patterns = [
            # Pattern 1: h3 tags with &amp;ndash; entity (for Questions 27-30, 31-35, 36-40 format)
            r'&lt;h3[^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)&amp;ndash;(\d+)&lt;/strong&gt;&lt;/h3&gt;',
            
            # Pattern 1b: h3 tags with regular dash
            r'&lt;h3[^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)[-–—](\d+)&lt;/strong&gt;&lt;/h3&gt;',
            
            # Pattern 1c: h3 tags (non-encoded)
            r'<h3[^>]*><strong>Questions?\s+(\d+)&ndash;(\d+)</strong></h3>',
            r'<h3[^>]*><strong>Questions?\s+(\d+)[-–—](\d+)</strong></h3>',
            
            # Pattern 2: h4 tags with &amp;ndash; entity
            r'&lt;h4[^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)&amp;ndash;(\d+)&lt;/strong&gt;&lt;/h4&gt;',
            
            # Pattern 3: h4 tags with regular dash
            r'&lt;h4[^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)[-–—](\d+)&lt;/strong&gt;&lt;/h4&gt;',
            
            # Pattern 4: Any h tag with &amp;ndash; entity
            r'&lt;h[1-6][^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)&amp;ndash;(\d+)&lt;/strong&gt;&lt;/h[1-6]&gt;',
            
            # Pattern 5: Any h tag with any dash type
            r'&lt;h[1-6][^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)[-–—&amp;mdash;](\d+)&lt;/strong&gt;&lt;/h[1-6]&gt;',
            
            # Pattern 6: h tag with em and strong - FOR YOUR CASE
            r'&lt;h[1-6][^&gt;]*&gt;&lt;em&gt;&lt;strong&gt;Questions?\s+(\d+)[-–—&amp;ndash;&amp;mdash;](\d+)&lt;/strong&gt;&lt;/em&gt;&lt;/h[1-6]&gt;',
            
            # Pattern 6: Strong tags without h wrapper
            r'&lt;strong&gt;Questions?\s+(\d+)&amp;ndash;(\d+)&lt;/strong&gt;',
            r'&lt;strong&gt;Questions?\s+(\d+)[-–—](\d+)&lt;/strong&gt;',
            
            # Pattern 6b: Strong tags with &ndash; entity (non-encoded)
            r'<strong>Questions?\s+(\d+)&ndash;(\d+)</strong>',
            r'<strong>Questions?\s+(\d+)[-–—](\d+)</strong>',
            
            # Pattern 7: p tags with strong
            r'&lt;p[^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)[-–—&amp;ndash;&amp;mdash;](\d+)&lt;/strong&gt;',
            r'<p[^>]*><strong>Questions?\s+(\d+)&ndash;(\d+)</strong>',
            
            # Pattern 8: Simple strong with space
            r'&lt;p[^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)[-–—&amp;ndash;&amp;mdash;](\d+)\s*&lt;/strong&gt;',
            
            # Non-encoded versions
            r'<h4[^>]*><strong>Questions?\s+(\d+)&ndash;(\d+)</strong></h4>',
            r'<h4[^>]*><strong>Questions?\s+(\d+)[-–—](\d+)</strong></h4>',
            r'<h[1-6][^>]*><strong>Questions?\s+(\d+)&ndash;(\d+)</strong></h[1-6]>',
            r'<h[1-6][^>]*><strong>Questions?\s+(\d+)[-–—&mdash;](\d+)</strong></h[1-6]>',
            r'<h[1-6][^>]*><em><strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong></em></h[1-6]>',
            r'<strong>Questions?\s+(\d+)&ndash;(\d+)</strong>',
            r'<strong>Questions?\s+(\d+)[-–—](\d+)</strong>',
            r'<p[^>]*><strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong>',
            r'<p[^>]*><strong>Questions?\s+(\d+)&ndash;(\d+)</strong></p>',

            # NEW: "Questions X and Y" patterns (HTML-encoded)
            r'&lt;h[1-6][^&gt;]*&gt;(?:&lt;em&gt;)?&lt;strong&gt;Questions?\s+(\d+)\s+and\s+(\d+)&lt;/strong&gt;(?:&lt;/em&gt;)?&lt;/h[1-6]&gt;',
            r'&lt;p[^&gt;]*&gt;(?:&lt;em&gt;)?&lt;strong&gt;Questions?\s+(\d+)\s+and\s+(\d+)&lt;/strong&gt;(?:&lt;/em&gt;)?',
            r'&lt;strong&gt;Questions?\s+(\d+)\s+and\s+(\d+)&lt;/strong&gt;',

            # NEW: "Questions X and Y" patterns (non-encoded)
            r'<h[1-6][^>]*>(?:<em>)?<strong>Questions?\s+(\d+)\s+and\s+(\d+)</strong>(?:</em>)?</h[1-6]>',
            r'<p[^>]*>(?:<em>)?<strong>Questions?\s+(\d+)\s+and\s+(\d+)</strong>(?:</em>)?',
            r'<strong>Questions?\s+(\d+)\s+and\s+(\d+)</strong>',
        ]
        
        sections = []
        all_matches = []
        
        # Try each pattern and collect ALL matches
        for i, pattern in enumerate(header_patterns):
            matches = list(re.finditer(pattern, html_content, re.IGNORECASE))
            for match in matches:
                start_num = int(match.group(1))
                end_num = int(match.group(2))
                all_matches.append({
                    'start_num': start_num,
                    'end_num': end_num,
                    'start_pos': match.start(),
                    'end_pos': match.end(),
                    'pattern_index': i,
                    'match_text': match.group(0)
                })
                print(f"[READING] 🎯 Pattern {i+1} found: Questions {start_num}-{end_num} at position {match.start()}")
            
            if matches:
                print(f"[READING] ✅ Pattern {i+1} successful: {len(matches)} matches")
        
        # CRITICAL: Remove duplicates and overlapping sections - keep ONLY FIRST occurrence
        unique_matches = []
        seen_ranges = {}  # (start_num, end_num) -> best_match
        
        for match in all_matches:
            range_key = (match['start_num'], match['end_num'])
            # If we haven't seen this range, keep it (FIRST occurrence)
            if range_key not in seen_ranges:
                seen_ranges[range_key] = match
                print(f"[READING] ✅ Keeping FIRST occurrence of section {range_key[0]}-{range_key[1]} at position {match['start_pos']}")
            else:
                # DUPLICATE - skip it completely
                existing = seen_ranges[range_key]
                print(f"[READING] 🗑️ SKIPPING duplicate section {range_key[0]}-{range_key[1]} at position {match['start_pos']} (already have at {existing['start_pos']})")
        
        unique_matches = list(seen_ranges.values())
        unique_matches.sort(key=lambda x: x['start_pos'])
        
        print(f"[READING] 📊 After duplicate removal: {len(unique_matches)} unique sections (from {len(all_matches)} total matches)")
        
        print(f"[READING] 📊 Total unique sections found: {len(unique_matches)}")
        
        # Create sections from matches
        for i, match in enumerate(unique_matches):
            section_start = match['start_pos']
            section_end = unique_matches[i + 1]['start_pos'] if i + 1 < len(unique_matches) else len(html_content)
            
            section_html = html_content[section_start:section_end]
            
            # Skip sections that are too small (likely just headers or duplicates)
            # Minimum section size: at least 100 characters (header + some content)
            if len(section_html.strip()) < 100:
                print(f"[READING] ⏭️ Skipping tiny section {match['start_num']}-{match['end_num']} ({len(section_html)} chars) - likely duplicate")
                continue
            
            sections.append({
                'start_question': match['start_num'],
                'end_question': match['end_num'],
                'html': section_html,
                'range': f"{match['start_num']}-{match['end_num']}",
                'start_pos': section_start  # Store position for later re-extraction
            })
            
            print(f"[READING] 📋 Section {len(sections)}: Questions {sections[-1]['range']} ({len(section_html)} chars)")
        
        # If no sections found, treat entire content as one section
        if not sections:
            sections.append({
                'start_question': 1,
                'end_question': 999,
                'html': html_content,
                'range': 'all'
            })
            print(f"[READING] 📋 No sections found, treating as single section")
        
        return sections

    def get_unprocessed_questions_in_section(self, section_html, existing_tags, start_q, end_q):
        """ENHANCED question detection - handles ALL formats"""
        unprocessed = []
        found_questions = set()
        
        print(f"[READING] 🔍 Enhanced question detection for range {start_q}-{end_q}")
        
        # PRIORITY 1: Check for INLINE completion patterns
        inline_patterns = [
            # HTML encoded patterns
            r'&lt;strong[^&gt;]*&gt;(\d+)\s*[\.]{3,}[^&lt;]*?&lt;/strong&gt;',
            r'&lt;strong[^&gt;]*&gt;(\d+)&amp;nbsp;&lt;/strong&gt;&lt;strong[^&gt;]*&gt;[\.]{3,}[^&lt;]*?&lt;/strong&gt;',
            r'&lt;strong[^&gt;]*&gt;(\d+)&lt;/strong&gt;&lt;strong[^&gt;]*&gt;\s*[\.]{3,}[^&lt;]*?&lt;/strong&gt;',
            r'&lt;strong[^&gt;]*&gt;(\d+)\s+[\.]{3,}(?:&amp;nbsp;)*[^&lt;]*?&lt;/strong&gt;',
            
            # Non-encoded patterns
            r'<strong[^>]*>(\d+)\s*[\.]{3,}[^<]*?</strong>',
            r'<strong[^>]*>(\d+)&nbsp;</strong><strong[^>]*>[\.]{3,}[^<]*?</strong>',
            r'<strong[^>]*>(\d+)</strong><strong[^>]*>\s*[\.]{3,}[^<]*?</strong>',
            r'<strong[^>]*>(\d+)\s+[\.]{3,}(?:&nbsp;)*[^<]*?</strong>',
        ]
        
        for pattern in inline_patterns:
            matches = re.finditer(pattern, section_html, re.DOTALL)
            for match in matches:
                q_num = int(match.group(1))
                if start_q <= q_num <= end_q:
                    found_questions.add(q_num)
                    print(f"[READING] 📍 Found INLINE completion Q{q_num}")
        
        # PRIORITY 2: Traditional question patterns
        traditional_patterns = [
            # HTML encoded patterns
            r'&lt;p[^&gt;]*&gt;&lt;strong&gt;(\d+)&lt;/strong&gt;',
            r'&lt;strong&gt;(\d+)&lt;/strong&gt;',
            r'&lt;td[^&gt;]*&gt;[^&lt;]*&lt;strong&gt;(\d+)&lt;/strong&gt;',
            r'&lt;h[1-6][^&gt;]*&gt;&lt;strong&gt;(\d+)&lt;/strong&gt;',
            r'&lt;p[^&gt;]*list-style-type:decimal[^&gt;]*&gt;.*?(\d+)\.',
            r'&lt;span[^&gt;]*&gt;(\d+)\.\s*[A-Z]',
            
            # Non-encoded patterns
            r'<p[^>]*><strong>(\d+)</strong>',
            r'<strong>(\d+)</strong>',
            r'<td[^>]*>[^<]*<strong>(\d+)</strong>',
            r'<h[1-6][^>]*><strong>(\d+)</strong>',
            r'<p[^>]*list-style-type:decimal[^>]*>.*?(\d+)\.',
            r'<span[^>]*>(\d+)\.\s*[A-Z]',
        ]
        
        for pattern in traditional_patterns:
            matches = re.finditer(pattern, section_html, re.DOTALL)
            for match in matches:
                q_num = int(match.group(1))
                if start_q <= q_num <= end_q:
                    found_questions.add(q_num)
                    print(f"[READING] 📍 Found TRADITIONAL Q{q_num}")
        
        # PRIORITY 3: Simple number detection
        if not found_questions:
            simple_patterns = [r'(\d+)']
            
            for pattern in simple_patterns:
                matches = re.finditer(pattern, section_html)
                for match in matches:
                    try:
                        q_num = int(match.group(1))
                        if start_q <= q_num <= end_q:
                            context = section_html[max(0, match.start()-50):match.end()+50]
                            if any(keyword in context.lower() for keyword in ['strong', 'question', 'answer', '.']):
                                found_questions.add(q_num)
                                print(f"[READING] 📍 Found SIMPLE Q{q_num}")
                    except ValueError:
                        continue
        
        # Filter out questions that already have tags
        for q_num in found_questions:
            if q_num not in existing_tags:
                unprocessed.append(q_num)
        
        print(f"[READING] Section {start_q}-{end_q}: Found {len(found_questions)} questions, {len(unprocessed)} unprocessed: {sorted(unprocessed)}")
        return sorted(unprocessed)

    def analyze_section_type(self, section_html, question_range, unprocessed_questions, full_content=None):
        if not unprocessed_questions:
            print(f"[READING] ⏭️ Section {question_range}: No questions to process")
            return {'skip': True}

        from bs4 import BeautifulSoup
        import re

        # Parse HTML content
        soup = BeautifulSoup(section_html, 'html.parser')
        content_text = soup.get_text(separator=' ', strip=True).lower()

        print(f"[READING] 🚀 COMPLETE NEW ANALYZER for {question_range}")
        print(f"[READING] 📄 Processing questions: {unprocessed_questions}")
        print(f"[READING] 📖 Content preview: {content_text[:180]}...")

        # Initialize detection result
        detection_result = {
            'completion': False,
            'true_false': False,
            'matching': False,
            'matching_sentence_endings': False,
            'matching_headings': False,
            'matching_information': False,
            'multiple_choice': False,
            'labelling': False,
            'labelling_table': False,
            'list_selection': False,
            'skip': False
        }
        
        # 🚨 ABSOLUTE HIGHEST PRIORITY: LIST SELECTION FORCE CHECK
        # This overrides EVERYTHING else - no exceptions
        list_selection_force_patterns = [
            r'choose\s+\w+\s+answers?\s+from\s+the\s+box',
            r'choose\s+six\s+answers?\s+from\s+the\s+box', 
            r'choose\s+seven\s+answers?\s+from\s+the\s+box',
            r'choose\s+eight\s+answers?\s+from\s+the\s+box',
            r'choose\s+nine\s+answers?\s+from\s+the\s+box',
            r'write\s+the\s+correct\s+letter.*A-[I-J]',
            r'correct\s+letter.*A-[I-J]'
        ]
        
        for pattern in list_selection_force_patterns:
            if re.search(pattern, content_text, re.IGNORECASE):
                print(f"[READING] 🚨🚨 FORCED LIST SELECTION by pattern '{pattern}' - OVERRIDING EVERYTHING")
                return {'list_selection': True}

        if detect_label_table(section_html):
            detection_result['labelling'] = True
            detection_result['labelling_table'] = True
            print(f"[READING] ✅ DETECTED: LABELLING TABLE (table-tegs compatible)")
            return detection_result

        # SUPER-GUARD: NB implies drag-drop sentence endings (repeat allowed)
        # BUT: Check for Matching Information patterns first!
        try:
            has_nb = re.search(r'\bnb\b', content_text, re.IGNORECASE) or \
                     'you may use any letter more than once' in content_text or \
                     'may use any letter more than once' in content_text or \
                     'letters may be used more than once' in content_text
            
            if has_nb:
                # Check if this is Matching Information (paragraph/section matching or table_name)
                has_paragraph_matching = 'which paragraph contains' in content_text or \
                                        'paragraph contains' in content_text or \
                                        'reading passage has' in content_text
                
                has_section_matching = 'which section contains' in content_text or \
                                      'section contains' in content_text or \
                                      'listening passage has' in content_text
                
                has_table_name = 'table_name=' in content_text or \
                                'table_name="' in content_text
                
                has_people_matching = 'list of people' in content_text or \
                                     'match each statement with the correct person' in content_text
                
                # Check for "match each statement" pattern (common with table_name)
                has_match_each_statement = 'match each statement' in content_text or \
                                          'match each' in content_text
                
                if has_paragraph_matching or has_section_matching or has_table_name or has_people_matching or has_match_each_statement:
                    detection_result['matching_information'] = True
                    print(f"[READING] ✅ DETECTED (NB Guard): MATCHING INFORMATION due to matching patterns + NB")
                    return detection_result
                else:
                    detection_result['matching_sentence_endings'] = True
                    print(f"[READING] ✅ DETECTED (NB Guard): MATCHING SENTENCE ENDINGS due to NB")
                    return detection_result
        except Exception:
            pass

        # REMOVED: This was incorrectly identifying Matching Sentence Endings as Matching Information
        # "Complete each sentence with the correct ending, A-J" is MATCHING SENTENCE ENDINGS, not Matching Information!

        # HEADINGS GUARD: Detect matching headings before sentence endings
        try:
            has_headings_context = (
                'choose the correct heading' in content_text or
                'list of headings' in content_text or
                'correct heading for each paragraph' in content_text or
                'correct heading for each section' in content_text or
                'choose the most suitable headings' in content_text or
                'most suitable headings for sections' in content_text or
                'read the paragraphs one by one to choose the correct headings' in content_text
            )
            has_roman_numerals = bool(re.search(r'\b[i-vx]+[^a-z]', content_text)) or bool(re.search(r'<strong>[i-vx]+</strong>', section_html))
            has_paragraph_reference = 'paragraph' in content_text and ('a-g' in content_text or 'A-G' in section_html or 'A-F' in section_html or 'A-E' in section_html)
            has_write_correct_number = 'write the correct number' in content_text or 'write the appropriate numbers' in content_text
            
            # Strong indicator: "choose the most suitable headings" + "write the appropriate numbers i-ix"
            strong_headings_indicators = (
                'choose the most suitable headings' in content_text and
                'write the appropriate numbers' in content_text and
                'i-ix' in content_text
            )
            
            # Additional strong indicator: "read the paragraphs one by one to choose the correct headings" + Roman numerals
            read_paragraphs_indicators = (
                'read the paragraphs one by one to choose the correct headings' in content_text and
                has_roman_numerals
            )
            
            if strong_headings_indicators or read_paragraphs_indicators or (has_headings_context and (has_roman_numerals or has_paragraph_reference) and has_write_correct_number):
                detection_result['matching_headings'] = True
                print(f"[READING] ✅ DETECTED (Headings Guard): MATCHING HEADINGS")
                return detection_result
        except Exception:
            pass

        # ========== PRIORITY 0: LABELLING (LABEL THE PLAN/MAP/DIAGRAM) ==========
        print(f"[READING] 🏷️ PRIORITY 0: Analyzing LABELLING")
        
        labelling_patterns = [
            'label the plan',
            'label the map',
            'label the diagram',
            'label the chart',
            'choose.*answers? from the box',
            'write the correct letters? next to',
        ]
        
        # Count option letters (A-Z) OR roman numerals (i-ix) for labelling
        option_letters_labelling = re.findall(r'<strong[^>]*>\s*[A-Z]\s*</strong>', section_html)
        option_roman_labelling = re.findall(r'<strong[^>]*>\s*(i{1,3}|iv|v|vi{1,3}|ix|x|xi{1,3})\s*</strong>', section_html, re.IGNORECASE)
        
        has_labelling_instruction = any(re.search(pattern, content_text, re.IGNORECASE) for pattern in labelling_patterns)
        has_letter_options_labelling = len(option_letters_labelling) >= 5 and 'choose' in content_text and 'from the box' in content_text
        has_roman_options_labelling = len(option_roman_labelling) >= 5
        has_room_labels = bool(re.search(r'room\s+\d+|building\s+\d+|area\s+\d+', content_text, re.IGNORECASE))
        has_list_of_headings = 'list of headings' in content_text
        
        print(f"  ➤ Labelling instruction: {has_labelling_instruction}")
        print(f"  ➤ Letter options: {has_letter_options_labelling} (count: {len(option_letters_labelling)})")
        print(f"  ➤ Roman options: {has_roman_options_labelling} (count: {len(option_roman_labelling)})")
        print(f"  ➤ Room/Building labels: {has_room_labels}")
        print(f"  ➤ List of headings: {has_list_of_headings}")
        
        # Detect labelling: either with explicit instruction OR with roman numerals (List of Headings pattern)
        if (has_labelling_instruction and (has_letter_options_labelling or has_roman_options_labelling)) or \
           (has_roman_options_labelling and has_list_of_headings):
            detection_result['labelling'] = True
            print(f"[READING] ✅ DETECTED: LABELLING (Priority 0)")
            return detection_result

        # ========== PRIORITY 1: MATCHING SENTENCE ENDINGS (ABSOLUTE PRIORITY) ==========
        print(f"[READING] 🥇 PRIORITY 1: Analyzing MATCHING SENTENCE ENDINGS")

        # CRITICAL: Key phrases that indicate matching sentence endings
        sentence_endings_indicators = [
            'complete each sentence with the correct ending',  # STRONGEST INDICATOR - Questions 31-35 format
            'complete each sentence with the correct ending,',  # With comma
            'complete the summary using the words',
            'complete the summary using the list of words',
            'complete the summary using the list of phrases',
            'complete the summary using the list',
            'complete the note using the words',
            'complete the note using the list of words',
            'complete the notes using the list',
            'complete the passage using the list',
            'complete the text using the list',
            'using the words',
            'using the list of phrases',
            'using the list of words',
            'choose from the list below',
            'select from the list below'
        ]

        # CRITICAL: Letter range patterns (A-J, A-K, A-L, etc.)
        letter_range_patterns = [
            r'\ba-[a-z]\b',  # a-j, a-k, a-l, etc.
            r'\b[a-z]-[a-z]\b',  # General a-z pattern
            r'\b[A-Z]-[A-Z]\b'  # General A-Z pattern
        ]

        # Check for sentence endings indicators
        has_sentence_endings_phrase = any(phrase in content_text for phrase in sentence_endings_indicators)

        # Check for letter range pattern (like A-L in your example)
        has_letter_range = any(bool(re.search(pattern, content_text)) for pattern in letter_range_patterns)

        # Count option letters (A, B, C, D, E, F, etc.)
        option_letters = re.findall(r'<strong>\s*[A-Z]\s*</strong>', section_html)
        has_multiple_options = len(option_letters) >= 4  # Lowered threshold

        # Additional context indicators
        has_summary_context = any(word in content_text for word in ['summary', 'note', 'notes', 'passage'])
        has_below_keyword = ', below' in content_text or ' below' in content_text
        has_completion_instruction = 'complete' in content_text and 'using' in content_text

        # Check for dots/blanks in questions (like .....................)
        has_question_blanks = bool(re.search(r'\.{3,}|&hellip;|…{2,}', section_html))

        # EXCLUDE matching information patterns
        has_paragraph_contains = 'which paragraph contains' in content_text or 'paragraph contains' in content_text
        
        # "write the correct letter" can be in BOTH matching sentence endings AND matching information
        # Only exclude from sentence endings if it's CLEARLY matching information (has paragraph context)
        has_write_correct_letter = False
        if ('write the correct letter' in content_text or 'write the correct letters' in content_text):
            # Only set True if it's MATCHING INFORMATION context (not sentence endings)
            if has_paragraph_contains:
                # This is matching information
                has_write_correct_letter = True
            elif 'complete each sentence' not in content_text and 'correct ending' not in content_text:
                # Has "write correct letter" but NO sentence endings context - likely matching information
                if any(x in content_text for x in ['a-e', 'a-f', 'a-g', 'a-h', 'a-i', 'a-j']):
                    has_write_correct_letter = True

        print(f"  ➤ Sentence endings phrase: {has_sentence_endings_phrase}")
        print(f"  ➤ Complete each sentence: {'complete each sentence' in content_text}")
        print(f"  ➤ Correct ending: {'correct ending' in content_text}")
        print(f"  ➤ Letter range pattern: {has_letter_range}")
        print(f"  ➤ Multiple options: {has_multiple_options} (count: {len(option_letters)})")
        print(f"  ➤ Summary context: {has_summary_context}")
        print(f"  ➤ Below keyword: {has_below_keyword}")
        print(f"  ➤ Completion instruction: {has_completion_instruction}")
        print(f"  ➤ Question blanks: {has_question_blanks}")
        print(f"  ➤ Paragraph contains: {has_paragraph_contains}")
        print(f"  ➤ Write correct letter: {has_write_correct_letter}")

        # CRITICAL: Check for "Choose the correct letter, A, B, C or D" format FIRST
        # This is ALWAYS multiple choice, NOT matching sentence endings
        has_choose_letter_abcd = bool(re.search(
            r'choose\s+the\s+correct\s+letter\s*[,:]\s*[A-Z]\s*,\s*[A-Z]\s*,\s*[A-Z]\s*(?:or|/)\s*[A-Z]',
            content_text,
            re.IGNORECASE
        ))
        
        # Check for Questions 27-30 range
        # question_range is a string like "27-30", not a tuple
        if question_range and isinstance(question_range, str):
            # Parse string format like "27-30"
            range_match = re.match(r'(\d+)\s*[-–—]\s*(\d+)', question_range)
            if range_match:
                start_q = int(range_match.group(1))
                end_q = int(range_match.group(2))
            elif question_range.isdigit():
                start_q = end_q = int(question_range)
            else:
                start_q = end_q = None
        elif question_range and isinstance(question_range, (tuple, list)) and len(question_range) == 2:
            start_q, end_q = question_range
        else:
            start_q = end_q = None
        
        is_questions_27_30 = (start_q and end_q and start_q <= 27 and end_q >= 30) or \
                           (start_q == 27 and end_q == 30)
        
        # If "Choose the correct letter, A, B, C or D" is present, EXCLUDE from matching sentence endings
        if has_choose_letter_abcd or is_questions_27_30:
            print(f"[READING] 🚫 EXCLUDED from matching sentence endings: 'Choose the correct letter, A, B, C or D' detected OR Questions 27-30 range")
            matching_endings_score = -100  # Force exclusion
        else:
            # MATCHING SENTENCE ENDINGS DETECTION - ABSOLUTE PRIORITY
            matching_endings_score = 0
                    # Core indicators (high weight)
        if has_sentence_endings_phrase:
            matching_endings_score += 3
        if 'complete each sentence' in content_text:
            matching_endings_score += 5  # STRONGEST indicator for sentence endings (Questions 31-35 format)
        if 'correct ending' in content_text:
            matching_endings_score += 3  # Strong indicator
        if 'complete each sentence with the correct ending' in content_text:
            matching_endings_score += 10  # ABSOLUTE STRONGEST - this is the exact format for Questions 31-35
        if has_letter_range:
            matching_endings_score += 3
        if has_completion_instruction and has_below_keyword:
            matching_endings_score += 2

        # Supporting indicators (medium weight)
        if has_multiple_options and has_summary_context:
            matching_endings_score += 2
        if has_question_blanks and has_multiple_options:
            matching_endings_score += 1
        if 'complete the summary' in content_text and has_multiple_options:
            matching_endings_score += 2

        # EXCLUSION: If it has paragraph contains or write correct letter patterns, it's NOT sentence endings
        # Also exclude if it has multiple choice patterns (choose two letters, A-E, etc.)
        # Also exclude if it matches the A-G sentence endings instruction (handled by guard above)
        # Also exclude if it has headings patterns
        has_multiple_choice_patterns = (
            ('choose two letters' in content_text or 'choose three letters' in content_text)
            and (
                any(x in content_text for x in ['a-d','a-e','a-f','a-g','a-h','a-i','a-j'])
                or bool(re.search(r'\ba\s*[-–]\s*j\b', content_text))
            )
        )
        
        has_headings_patterns = (
            'choose the correct heading' in content_text or
            'list of headings' in content_text or
            'correct heading for each paragraph' in content_text or
            'correct heading for each section' in content_text
        )
        
        if has_paragraph_contains or has_write_correct_letter or has_multiple_choice_patterns or has_headings_patterns:
            matching_endings_score = 0
            print(f"  ➤ EXCLUDED from sentence endings due to matching information patterns, multiple choice patterns, or headings patterns")

        print(f"  ➤ Matching endings score: {matching_endings_score}")

        # DECISION: If score >= 3, it's matching sentence endings
        if matching_endings_score >= 3:
            detection_result['matching_sentence_endings'] = True
            print(f"[READING] ✅ DETECTED: MATCHING SENTENCE ENDINGS (Priority 1 - Score: {matching_endings_score})")
            return detection_result

        # FALLBACK: Even with lower score, prioritize matching endings if key patterns exist
        if (has_completion_instruction and has_multiple_options and has_below_keyword) or \
                (has_letter_range and has_multiple_options) or \
                ('complete the summary' in content_text and has_multiple_options and len(option_letters) >= 5):
            # But still exclude if it has matching information patterns
            if not (has_paragraph_contains or has_write_correct_letter):
                detection_result['matching_sentence_endings'] = True
                print(f"[READING] ✅ DETECTED: MATCHING SENTENCE ENDINGS (Priority 1 - Fallback)")
                return detection_result

        # ========== PRIORITY 2: TRUE/FALSE/NOT GIVEN ==========
        print(f"[READING] 🥈 PRIORITY 2: Analyzing TRUE/FALSE/NOT GIVEN")

        true_false_phrases = [
            'do the following statements agree',
            'agree with the information',
            'contradicts the information',
            'yes, no or not given',
            'true, false or not given',
            'do the following statements agree with the information',
            'agree with the claims of the writer',
            'contradicts the claims of the writer',
            'if the statement agrees with the claims',
            'if the statement contradicts the claims',
            'if it is impossible to say'
        ]

        true_false_keywords = ['true', 'false', 'not given', 'yes', 'no', 'agree', 'contradicts']
        has_true_false_context = any(phrase in content_text for phrase in true_false_phrases)
        has_true_false_keywords = any(keyword in content_text for keyword in true_false_keywords)
        
        # Also check for YES/NO/NOT GIVEN pattern
        has_yes_no_pattern = bool(re.search(r'\b(yes|no|not given)\b', content_text, re.IGNORECASE))

        print(f"  ➤ True/False context: {has_true_false_context}")
        print(f"  ➤ True/False keywords: {has_true_false_keywords}")

        if (has_true_false_context and has_true_false_keywords) or has_yes_no_pattern:
            detection_result['true_false'] = True
            print(f"[READING] ✅ DETECTED: TRUE/FALSE/NOT GIVEN (Priority 2)")
            return detection_result

        # ========== PRIORITY 3: COMPLETION (SUMMARY / SENTENCE) ==========
        print(f"[READING] 🏆 PRIORITY 3: Analyzing COMPLETION")

        strict_completion_phrases = [
            'complete the table',
            'complete the diagram',
            'complete the flow chart',
            'complete the form',
            'complete the summary',
            'complete the sentences',
            'complete the notes',
            'complete the sentences below',
            'fill in the gaps',
            'choose no more than',
            'write no more than',
            'one word only',
            'two words only',
            'one word and/or a number',
            'two words and/or a number',
            'write your answers in boxes'
        ]

        has_strict_completion = any(phrase in content_text for phrase in strict_completion_phrases)
        has_completion_dots = bool(re.search(r'&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;', section_html))
        has_completion_instructions = 'complete the sentences below' in content_text or 'choose one word only' in content_text
        has_completion_blanks = has_question_blanks and not has_multiple_options

        print(f"  ➤ Strict completion phrases: {has_strict_completion}")
        print(f"  ➤ Completion dots: {has_completion_dots}")
        print(f"  ➤ Completion instructions: {has_completion_instructions}")

        if has_strict_completion or has_completion_blanks or has_completion_dots or has_completion_instructions:
            detection_result['completion'] = True
            print(f"[READING] ✅ DETECTED: COMPLETION (Priority 3)")
            return detection_result
        
        # ========== PRIORITY 4: LIST SELECTION ==========
        print(f"[READING] 🥉 PRIORITY 4: Analyzing LIST SELECTION")

        list_selection_phrases = [
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
            'choose two of the following',
            'choose three of the following',
            'choose four of the following',
            'choose five of the following',
            'choose six of the following',
            'which two',
            'which three',
            'which four',
            'which five',
            'which six',
            'write the correct letters in boxes',
            'write the correct letter in boxes',
            'correct letters in boxes',
            'correct letter in boxes'
        ]

        has_list_selection_context = any(phrase in content_text for phrase in list_selection_phrases)
        
        # Check for A-E pattern specifically (both uppercase and lowercase)
        has_letter_range = bool(re.search(r'[A-Za-z]\s*[-–]\s*[A-Za-z]', content_text))
        
        # Count option letters (A, B, C, D, E format) - use full content if available
        content_to_search = full_content if full_content else section_html
        
        # Multiple patterns to match different option formats
        option_patterns = [
            r'<strong>\s*[A-Z]\s*</strong>',
            r'<strong>[A-Z]&nbsp;</strong>',
            r'<p><strong>[A-Z]&nbsp;</strong>',
            r'<p><strong>[A-Z]</strong>',
            r'<strong>[A-Z]&nbsp;&nbsp;</strong>'
        ]
        
        option_letters = []
        for pattern in option_patterns:
            option_letters.extend(re.findall(pattern, content_to_search, re.IGNORECASE))
        
        has_options = len(option_letters) >= 2

        print(f"  ➤ List selection context: {has_list_selection_context}")
        print(f"  ➤ Letter range pattern: {has_letter_range}")
        print(f"  ➤ Options found: {len(option_letters)}")

        # CRITICAL: If "Choose SIX answers from the box" is present, it's ALWAYS list_selection
        # This should take priority over everything else
        has_choose_answers_from_box = bool(re.search(r'choose\s+\w+\s+answers?\s+from\s+the\s+box', content_text, re.IGNORECASE))
        
        if has_choose_answers_from_box:
            detection_result['list_selection'] = True
            print(f"[READING] ✅ DETECTED: LIST SELECTION (Priority 4 - 'Choose X answers from the box' format)")
            return detection_result
        
        if has_list_selection_context and has_letter_range and has_options:
            detection_result['list_selection'] = True
            print(f"[READING] ✅ DETECTED: LIST SELECTION (Priority 4)")
            return detection_result

        # ========== PRIORITY 5: MULTIPLE CHOICE ==========
        print(f"[READING] 🥉 PRIORITY 5: Analyzing MULTIPLE CHOICE")
        
        # CRITICAL: Check for "Choose the correct letter, A, B, C or D" format FIRST
        # This is ALWAYS multiple choice, should be detected FIRST
        # Support both "A, B, C or D" (4 letters) and "A, B or C" (3 letters) formats
        has_choose_letter_abcd = bool(re.search(
            r'choose\s+the\s+correct\s+letter\s*[,:]\s*[A-Z]\s*,\s*[A-Z]\s*,\s*[A-Z]\s*(?:or|/)\s*[A-Z]',
            content_text,
            re.IGNORECASE
        )) or bool(re.search(
            r'choose\s+the\s+correct\s+letter\s*[,:]\s*[A-Z]\s*,\s*[A-Z]\s*(?:or|/)\s*[A-Z]',
            content_text,
            re.IGNORECASE
        )) or bool(re.search(
            r'choose\s+the\s+correct\s+letter[^<]*<strong>[A-Z]</strong>[^<]*<strong>[A-Z]</strong>[^<]*or[^<]*<strong>[A-Z]</strong>',
            section_html,
            re.IGNORECASE
        ))
        
        # Check for Questions 27-30 range
        # question_range is a string like "27-30", not a tuple
        if question_range and isinstance(question_range, str):
            # Parse string format like "27-30"
            range_match = re.match(r'(\d+)\s*[-–—]\s*(\d+)', question_range)
            if range_match:
                start_q = int(range_match.group(1))
                end_q = int(range_match.group(2))
            elif question_range.isdigit():
                start_q = end_q = int(question_range)
            else:
                start_q = end_q = None
        elif question_range and isinstance(question_range, (tuple, list)) and len(question_range) == 2:
            start_q, end_q = question_range
        else:
            start_q = end_q = None
        
        is_questions_27_30 = (start_q and end_q and start_q <= 27 and end_q >= 30) or \
                           (start_q == 27 and end_q == 30)

        multiple_choice_phrases = [
            'choose the correct letter',
            'choose the correct letter,',
            'select the correct answer',
            'write the correct letter in boxes',
            'write the correct letter in boxes',
            'correct letter, a, b, c or d',
            'correct letter, a, b, c, or d',
            'correct letter, a, b, c and d'
        ]

        # Enhanced option letter detection for multiple formats (support A–J)
        abcd_patterns = []
        
        # Pattern 1: <strong>A</strong> format
        abcd_patterns.extend(re.findall(r'<strong>\s*[A-J]\s*</strong>', section_html, re.IGNORECASE))
        
        # Pattern 2: A, B, C, D format in text (both upper and lower case)
        abcd_patterns.extend(re.findall(r'\b[A-Ja-j]\b', content_text))
        
        # Pattern 3: A-E range format (both upper and lower case)
        if re.search(r'[A-Ja-j]\s*[-–]\s*[A-Ja-j]', content_text):
            # Add a representative set to bump the count
            abcd_patterns.extend(['A','B','C','D'])
        
        # Pattern 4: Choose TWO letters, A-E format (both upper and lower case)
        if re.search(r'choose.*letters.*[A-Ja-j]', content_text):
            abcd_patterns.extend(['A', 'B', 'C', 'D', 'E'])
        
        # Remove duplicates and count
        abcd_patterns = list(set(abcd_patterns))
        
        has_multiple_choice_context = any(phrase in content_text for phrase in multiple_choice_phrases)
        has_abcd_options = len(abcd_patterns) >= 3  # Reduced threshold

        print(f"  ➤ Multiple choice context: {has_multiple_choice_context}")
        print(f"  ➤ ABCD pattern count: {len(abcd_patterns)}")
        print(f"  ➤ Choose letter A,B,C,D format: {has_choose_letter_abcd}")
        print(f"  ➤ Questions 27-30 range: {is_questions_27_30}")

        # CRITICAL: If "Choose the correct letter, A, B, C or D" OR Questions 27-30, FORCE multiple choice
        if has_choose_letter_abcd or is_questions_27_30:
            detection_result['multiple_choice'] = True
            print(f"[READING] ✅ DETECTED: MULTIPLE CHOICE (Priority 5 - FORCED by 'Choose the correct letter, A, B, C or D' format OR Questions 27-30)")
            return detection_result

        # Also check for "Choose the correct letter, A, B or C" in HTML format
        has_choose_letter_abc_html = bool(re.search(
            r'choose\s+the\s+correct\s+letter[^<]*<strong>[A-Z]</strong>[^<]*<strong>[A-Z]</strong>[^<]*or[^<]*<strong>[A-Z]</strong>',
            section_html,
            re.IGNORECASE
        ))
        
        if has_choose_letter_abc_html:
            detection_result['multiple_choice'] = True
            print(f"[READING] ✅ DETECTED: MULTIPLE CHOICE (Priority 5 - FORCED by 'Choose the correct letter, A, B or C' HTML format)")
            return detection_result

        if has_multiple_choice_context and has_abcd_options:
            detection_result['multiple_choice'] = True
            print(f"[READING] ✅ DETECTED: MULTIPLE CHOICE (Priority 5)")
            return detection_result

        # ========== PRIORITY 6: MATCHING INFORMATION ==========
        print(f"[READING] 🏅 PRIORITY 6: Analyzing MATCHING INFORMATION")

        matching_info_phrases = [
            'which paragraph contains the following information',
            'which section contains',
            'match each statement with the correct',
            'which paragraph contains',
            'paragraph contains the following information',
            'write the correct letter',
            'correct letter, a-g',
            'correct letter, a-f',
            'correct letter, a-e',
            'correct letter, a-d',
            'correct letter, a-c',
            'correct letter, a-b',
            'boxes 14-18',
            'boxes 19-21',
            'answer sheet',
            'match each purpose',
            'timber cuts',
            'list of timber cuts',
            'match each purpose with the correct',
            'purposes and the list',
            'correct timber cut',
            'section contains',  # Add this for questions 1-3
            'match each statement',  # Add this for questions 7-13
            'match each'  # Add this for broader matching detection
        ]

        # Check for A-G, A-F, A-E, A-C patterns specifically
        letter_range_matching = bool(re.search(r'<strong>[A-G]</strong>', section_html)) or \
                               bool(re.search(r'<strong>[A-F]</strong>', section_html)) or \
                               bool(re.search(r'<strong>[A-E]</strong>', section_html)) or \
                               bool(re.search(r'<strong>[A-D]</strong>', section_html)) or \
                               bool(re.search(r'<strong>[A-C]</strong>', section_html)) or \
                               bool(re.search(r'correct letter.*[A-G]', content_text)) or \
                               bool(re.search(r'correct letter.*[A-F]', content_text)) or \
                               bool(re.search(r'correct letter.*[A-E]', content_text)) or \
                               bool(re.search(r'correct letter.*[A-D]', content_text)) or \
                               bool(re.search(r'correct letter.*[A-C]', content_text)) or \
                               bool(re.search(r'paragraphs.*[A-G]', content_text)) or \
                               bool(re.search(r'sections.*[A-F]', content_text)) or \
                               bool(re.search(r'paragraphs.*[A-F]', content_text))

        has_matching_info_context = any(phrase in content_text for phrase in matching_info_phrases)
        
        # Additional check for paragraph-based matching
        has_paragraph_context = 'paragraph' in content_text and ('contains' in content_text or 'information' in content_text)
        
        # Additional check for section-based matching
        has_section_context = 'section' in content_text and ('contains' in content_text or 'information' in content_text)
        
        # Check for timber cuts or purpose matching
        has_timber_context = 'timber' in content_text and 'cut' in content_text
        has_purpose_context = 'purpose' in content_text and 'match' in content_text
        
        # Check for table_name pattern (for questions 7-13)
        has_table_name_pattern = 'table_name=' in content_text or 'table_name="' in content_text
        
        # Check for "match each statement" pattern (for questions 7-13)
        has_match_each_pattern = 'match each statement' in content_text or 'match each' in content_text

        # Multiple choice exclusions
        multiple_choice_exclusions = [
            'choose two letters',
            'choose three letters',
            'write the correct letters in boxes',
            'write the correct letter in boxes',
            'choose the correct letter'
        ]
        
        has_multiple_choice_exclusions = any(exclusion in content_text for exclusion in multiple_choice_exclusions)
        
        print(f"  ➤ Matching info phrases: {has_matching_info_context}")
        print(f"  ➤ Letter range matching: {letter_range_matching}")
        print(f"  ➤ Paragraph context: {has_paragraph_context}")
        print(f"  ➤ Section context: {has_section_context}")
        print(f"  ➤ Timber context: {has_timber_context}")
        print(f"  ➤ Purpose context: {has_purpose_context}")
        print(f"  ➤ Table name pattern: {has_table_name_pattern}")
        print(f"  ➤ Match each pattern: {has_match_each_pattern}")
        print(f"  ➤ Multiple choice exclusions: {has_multiple_choice_exclusions}")
        
        # Only detect as matching information if it's NOT multiple choice
        if has_matching_info_context and not has_multiple_choice_exclusions and (letter_range_matching or has_paragraph_context or has_section_context or has_timber_context or has_purpose_context or has_table_name_pattern or has_match_each_pattern):
            detection_result['matching_information'] = True
            print(f"[READING] ✅ DETECTED: MATCHING INFORMATION (Priority 5)")
            return detection_result

        # ========== PRIORITY 7: MATCHING HEADINGS ==========
        print(f"[READING] 🎖️ PRIORITY 7: Analyzing MATCHING HEADINGS")

        matching_headings_phrases = [
            'choose the correct heading',
            'list of headings',
            'match each paragraph'
        ]

        has_matching_headings_context = any(phrase in content_text for phrase in matching_headings_phrases)
        has_roman_numeral = bool(re.search(r'i-x', content_text, re.IGNORECASE))
        
        # CRITICAL: Exclude list_selection patterns from matching_headings
        # "Choose SIX answers from the box" should NOT be detected as matching_headings
        list_selection_exclusions = [
            'choose.*answers from the box',
            'choose.*letters.*from the box',
            'write the correct letters in boxes',
            'write the correct letter.*next to'
        ]
        has_list_selection_exclusion = any(re.search(pattern, content_text, re.IGNORECASE) for pattern in list_selection_exclusions)

        if (has_matching_headings_context or has_roman_numeral) and not has_list_selection_exclusion:
            detection_result['matching_headings'] = True
            print(f"[READING] ✅ DETECTED: MATCHING HEADINGS (Priority 6)")
            return detection_result

        # ========== PRIORITY 8: COMPLETION (LAST RESORT) ==========
        print(f"[READING] 🏆 PRIORITY 8: Analyzing COMPLETION (LAST RESORT)")

        # Only detect completion if NO OTHER TYPE matches and has specific completion indicators
        strict_completion_phrases = [
            'complete the table',
            'complete the diagram',
            'complete the flow chart',
            'complete the form',
            'choose no more than',
            'write no more than',
            'fill in the gaps',
            'complete the sentences',
            'one word only',
            'from the passage for each answer',
            'write your answers in boxes'
        ]

        has_strict_completion = any(phrase in content_text for phrase in strict_completion_phrases)
        
        # Check for completion-specific patterns
        has_completion_dots = bool(re.search(r'&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;&hellip;', section_html))
        has_completion_instructions = 'complete the sentences below' in content_text or 'choose one word only' in content_text

        print(f"  ➤ Strict completion phrases: {has_strict_completion}")
        print(f"  ➤ Completion dots: {has_completion_dots}")
        print(f"  ➤ Completion instructions: {has_completion_instructions}")

        if has_strict_completion or (has_question_blanks and not has_multiple_options) or has_completion_dots or has_completion_instructions:
            detection_result['completion'] = True
            print(f"[READING] ✅ DETECTED: COMPLETION (Priority 7 - STRICT)")
            return detection_result

        # ========== ABSOLUTE FALLBACK ==========
        print(f"[READING] 🆘 ABSOLUTE FALLBACK")

        # If we have options A-Z, it's probably matching sentence endings
        if has_multiple_options and len(option_letters) >= 4:
            detection_result['matching_sentence_endings'] = True
            print(f"[READING] ✅ DETECTED: MATCHING SENTENCE ENDINGS (Absolute Fallback)")
            return detection_result

        # Otherwise default to completion
        detection_result['completion'] = True
        print(f"[READING] ❌ NO SPECIFIC TYPE DETECTED: Defaulting to COMPLETION")
        return detection_result

    def process_section(self, section_html, analysis, question_range, unprocessed_questions, original_html):
        """ENHANCED process section with ALL parsers including matching_information"""
        if analysis.get('skip') or not unprocessed_questions:
            print(f"[READING] ⏭️ Skipping section {question_range}")
            return original_html
        
        # CRITICAL: Check if section already has all question-input tags with proper format
        # If all questions in range already have question-input tags, preserve the section as-is
        range_match = re.match(r'(\d+)\s*[-–—]\s*(\d+)', question_range) if isinstance(question_range, str) else None
        if range_match:
            start_q = int(range_match.group(1))
            end_q = int(range_match.group(2))
            
            # Find all question numbers in this section that have question-input tags
            existing_in_section = set()
            patterns = [
                r'<question-input[^>]*data-question-number="(\d+)"[^>]*>',
                r'&lt;question-input[^&gt;]*data-question-number="(\d+)"[^&gt;]*&gt;',
                r'<drag-drop-sentence-input[^>]*data-question-number="(\d+)"[^>]*>',
                r'&lt;drag-drop-sentence-input[^&gt;]*data-question-number="(\d+)"[^&gt;]*&gt;',
            ]
            
            for pattern in patterns:
                for match in re.finditer(pattern, section_html):
                    q_num = int(match.group(1))
                    if start_q <= q_num <= end_q:
                        existing_in_section.add(q_num)
            
            # Check if all questions in range have tags
            expected_questions = set(range(start_q, end_q + 1))
            if existing_in_section.issuperset(expected_questions) or existing_in_section == expected_questions:
                print(f"[READING] ✅ Section {question_range}: All questions already have question-input tags, preserving as-is")
                return original_html
        
        print(f"[READING] 🎯 Processing section {question_range} for questions: {unprocessed_questions}")
        
        
        
        # Process LIST SELECTION (HIGHEST PRIORITY)
        # CRITICAL: Also check if this section has "Choose X answers from the box" even if not detected
        # This prevents matching_headings from incorrectly processing list_selection questions
        has_choose_answers_from_box = bool(re.search(r'choose\s+\w+\s+answers?\s+from\s+the\s+box', section_html, re.IGNORECASE))
        
        if analysis.get('list_selection', False) or has_choose_answers_from_box:
            if has_choose_answers_from_box and not analysis.get('list_selection', False):
                print(f"[READING] 🔧 FORCING LIST SELECTION for section {question_range} (detected 'Choose X answers from the box')")
            else:
                print(f"[READING] 🔧 Using LIST SELECTION parser for section {question_range}")
            try:
                from apps.reading.utils.list_selection_perfect import parse_list_selection
                processed_html = parse_list_selection(section_html)
                
                # Check for created components
                patterns = [
                    r'<list-selection-tegs[^>]*question_type="list_selection"[^>]*>',
                    r'<list-selection-tegs[^>]*data-options[^>]*>'
                ]
                
                new_components = 0
                for pattern in patterns:
                    new_components += len(re.findall(pattern, processed_html))
                
                print(f"[READING] ✅ List selection parser created {new_components} components")
                
                if new_components > 0:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[READING] ⚠️ No components created")
                    return original_html
                    
            except Exception as e:
                print(f"[READING] ❌ LIST SELECTION parsing failed: {e}")
                import traceback
                print(f"[READING] Traceback: {traceback.format_exc()}")
                return original_html
        
        # Process LABELLING (Label the plan/map/diagram)
        elif analysis.get('labelling', False):
            print(f"[READING] 🔧 Using LABELLING parser for section {question_range}")
            try:
                # Extract question numbers from range (supports -, –, —)
                start_q = end_q = None
                range_match = re.match(r'(\d+)\s*[-–—]\s*(\d+)', question_range)
                if range_match:
                    start_q = int(range_match.group(1))
                    end_q = int(range_match.group(2))
                elif question_range.isdigit():
                    value = int(question_range)
                    start_q = value
                    end_q = value
                elif unprocessed_questions:
                    start_q = min(unprocessed_questions)
                    end_q = max(unprocessed_questions)

                if start_q is None:
                    start_q = min(unprocessed_questions) if unprocessed_questions else 1
                if end_q is None:
                    end_q = max(unprocessed_questions) if unprocessed_questions else start_q

                if analysis.get('labelling_table'):
                    converted_html, table_processed = convert_to_label_table(
                        section_html,
                        start_q=start_q,
                        end_q=end_q,
                        question_type="labelling",
                    )
                    table_components = len(re.findall(r'<table-tegs[^>]*data-question-type="labelling"[^>]*>', converted_html))
                    if table_components == 0:
                        table_components = len(re.findall(r'<table-tegs[^>]*data-question-type="matching_information"[^>]*>', converted_html))

                    if table_components > 0 and table_processed:
                        print(f"[READING] ✅ Label table parser created {table_components} table-tegs components")
                        return self.direct_section_replacement(original_html, section_html, converted_html, question_range)
                    else:
                        print(f"[READING] ⚠️ Label table parser produced no components, falling back to drag-drop parser")
                
                processed_html, processed_questions = parse_labelling_questions(section_html, start_q, end_q, f"Questions {start_q}–{end_q}")
                
                # Check for created components (matching_headings format)
                patterns = [
                    r'<table-tegs[^>]*data-question-type="labelling"[^>]*>',
                    r'<table-tegs[^>]*data-question-type="matching_information"[^>]*>',
                    r'<drag-drop-matching-sentence-endings[^>]*data-question-type="matching_headings"[^>]*>',
                    r'<drag-drop-sentence-input[^>]*data-question-type="matching_headings"[^>]*>',
                ]
                
                new_components = 0
                for pattern in patterns:
                    new_components += len(re.findall(pattern, processed_html))
                
                # Count created question inputs
                tag_count = len(re.findall(r'data-question-type="matching_headings"', processed_html))
                print(f"[READING] ✅ Labelling parser created {new_components} components, {tag_count} inputs")
                
                if new_components > 0:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[READING] ⚠️ No components created")
                    return original_html
                    
            except Exception as e:
                print(f"[READING] ❌ LABELLING parsing failed: {e}")
                import traceback
                print(f"[READING] Traceback: {traceback.format_exc()}")
                return original_html
        
        # Process MULTIPLE CHOICE (SECOND PRIORITY)
        elif analysis.get('multiple_choice', False):
            print(f"[READING] 🔧 Using MULTIPLE CHOICE parser for section {question_range}")
            try:
                processed_html = parse_multiple_choice(section_html)
                
                # Convert ALL multiple_choice types to multiple_choice_with_multiple_answer
                # This ensures consistency - ALL multiple choice questions use multiple_choice_with_multiple_answer
                conversion_patterns = [
                    (r'data-question-type="multiple_choice"', 'data-question-type="multiple_choice_with_multiple_answer"'),
                    (r'data-question-type="multiple_choice_with_single_answer"', 'data-question-type="multiple_choice_with_multiple_answer"'),
                ]
                
                for old_pattern, new_replacement in conversion_patterns:
                    if re.search(old_pattern, processed_html):
                        count = len(re.findall(old_pattern, processed_html))
                        processed_html = re.sub(old_pattern, new_replacement, processed_html)
                        print(f"[READING] 🔄 Converted {count} {old_pattern} to {new_replacement}")
                
                # Convert data-options to data-question-options for question-input tags
                # This ensures compatibility with frontend renderers
                if re.search(r'<question-input[^>]*data-options=', processed_html):
                    count = len(re.findall(r'<question-input[^>]*data-options=', processed_html))
                    processed_html = re.sub(
                        r'(<question-input[^>]*)data-options=',
                        r'\1data-question-options=',
                        processed_html
                    )
                    print(f"[READING] 🔄 Converted {count} data-options to data-question-options in question-input tags")
                
                # Check for created components
                patterns = [
                    r'<question-input[^>]*data-question-type="multiple_choice_with_multiple_answer"[^>]*>',
                    r'<drag-drop-sentence-input[^>]*data-question-type="multiple_choice_with_multiple_answer"[^>]*>',
                    r'<drag-drop-matching-sentence-endings[^>]*data-options[^>]*>',
                    r'<list-selection-tegs[^>]*question_type="list_selection"[^>]*>',
                    r'<list-selection-tegs[^>]*data-options[^>]*>'
                ]
                
                new_components = 0
                for pattern in patterns:
                    new_components += len(re.findall(pattern, processed_html))
                
                print(f"[READING] ✅ Multiple choice parser created {new_components} components")
                
                if new_components > 0:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[READING] ⚠️ No components created")
                    return original_html
                    
            except Exception as e:
                print(f"[READING] ❌ MULTIPLE CHOICE parsing failed: {e}")
                import traceback
                print(f"[READING] Traceback: {traceback.format_exc()}")
                return original_html
        
        # Process MATCHING INFORMATION (NEW)
        elif analysis.get('matching_information', False):
            print(f"[READING] 🔧 Using MATCHING INFORMATION parser for section {question_range}")
            try:
                processed_html = parse_matching_information(section_html)

                # Look for both table-tegs and drag-drop components for matching_information
                patterns = [
                    r'<table-tegs[^>]*data-question-type="matching_information"[^>]*>',
                    r'<table-tegs-input[^>]*data-question-type="matching_information"[^>]*>',
                    r'<drag-drop-matching-sentence-endings[^>]*data-question-type="matching_sentence_endings"[^>]*>'
                ]
                print(f"[READING] 🏷️ Looking for table-tegs and drag-drop components")

                new_components = 0
                for pattern in patterns:
                    new_components += len(re.findall(pattern, processed_html))

                print(f"[READING] ✅ Matching information parser created {new_components} components")

                if new_components > 0:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[READING] ⚠️ No components created")
                    return original_html

            except Exception as e:
                print(f"[READING] ❌ MATCHING INFORMATION parsing failed: {e}")
                import traceback
                print(f"[READING] Traceback: {traceback.format_exc()}")
                return original_html


        # Process MATCHING SENTENCE ENDINGS
        elif analysis.get('matching_sentence_endings', False):
            # CRITICAL: Check if this is Questions 27-30 with "Choose the correct letter, A, B, C or D"
            # If so, skip matching sentence endings and use multiple choice instead
            if question_range and isinstance(question_range, str):
                range_match = re.match(r'(\d+)\s*[-–—]\s*(\d+)', question_range)
                if range_match:
                    start_q = int(range_match.group(1))
                    end_q = int(range_match.group(2))
                    is_questions_27_30 = (start_q <= 27 and end_q >= 30) or (start_q == 27 and end_q == 30)
                    
                    # Check for "Choose the correct letter, A, B, C or D" format
                    has_choose_letter_abcd = bool(re.search(
                        r'choose\s+the\s+correct\s+letter\s*[,:]\s*[A-Z]\s*,\s*[A-Z]\s*,\s*[A-Z]\s*(?:or|/)\s*[A-Z]',
                        section_html,
                        re.IGNORECASE
                    ))
                    
                    if is_questions_27_30 or has_choose_letter_abcd:
                        print(f"[READING] 🚫 SKIPPING matching sentence endings for {question_range} - this is MULTIPLE CHOICE!")
                        # Force multiple choice instead
                        analysis['matching_sentence_endings'] = False
                        analysis['multiple_choice'] = True
                        # Process as multiple choice
                        print(f"[READING] 🔧 Using MULTIPLE CHOICE parser for section {question_range} (forced)")
                        try:
                            processed_html = parse_multiple_choice(section_html)
                            
                            # Check if question-input tags were created
                            question_inputs = re.findall(r'<question-input[^>]*data-question-number="(\d+)"', processed_html)
                            if question_inputs:
                                print(f"[READING] ✅ Multiple choice parser created {len(question_inputs)} question-input tags: {question_inputs}")
                                return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                            else:
                                print(f"[READING] ⚠️ No question-input tags created")
                                return original_html
                        except Exception as e:
                            print(f"[READING] ❌ MULTIPLE CHOICE parsing failed: {e}")
                            import traceback
                            print(f"[READING] Traceback: {traceback.format_exc()}")
                            return original_html
            
            print(f"[READING] 🔧 Using MATCHING SENTENCE ENDINGS parser for section {question_range}")
            try:
                # ENHANCED SPAN & P & EXTRA DIV REMOVAL FUNCTION
                def remove_all_spans_and_outer_p_and_extra_divs(html_content):
                    """
                    Barcha span, tashqi P, va ortiqcha DIV teglarni olib tashlaydi
                    """
                    if not html_content:
                        return html_content
                        
                    try:
                        import re
                        from bs4 import BeautifulSoup
                        
                        print(f"[ENHANCED_REMOVER] 💥 Span, P, va ortiqcha DIV tozalash boshlandi...")
                        
                        # Method 1: BeautifulSoup bilan span teglarni unwrap qilish
                        soup = BeautifulSoup(html_content, 'html.parser')
                        
                        # Count initial tags
                        spans = soup.find_all('span')
                        span_count = len(spans)
                        
                        # Remove all span tags
                        for span in spans:
                            span.unwrap()
                        
                        # Method 2: Tashqi P teglarni olib tashlash
                        outer_p_tags = soup.find_all('p')
                        p_removed_count = 0
                        
                        for p_tag in outer_p_tags:
                            if p_tag.find('drag-drop-matching-sentence-endings') or (p_tag.find('div') and 'drag-drop-matching-sentence-endings' in str(p_tag)):
                                p_tag.unwrap()
                                p_removed_count += 1
                        
                        cleaned_html = str(soup)
                        
                        # Method 3: Regex bilan qolgan span teglarni tozalash
                        cleaned_html = re.sub(r'<span[^>]*>', '', cleaned_html, flags=re.IGNORECASE | re.DOTALL)
                        cleaned_html = re.sub(r'</span>', '', cleaned_html, flags=re.IGNORECASE)
                        
                        # Method 4: Ortiqcha DIV teglarni tozalash
                        # Multiple opening div'larni bitta div'ga aylantirish
                        cleaned_html = re.sub(r'(<div>\s*){2,}(<drag-drop-matching-sentence-endings)', r'<div>\2', cleaned_html)
                        
                        # Multiple closing div'larni bitta div'ga aylantirish  
                        cleaned_html = re.sub(r'(</drag-drop-matching-sentence-endings>)(\s*</div>){2,}', r'\1</div>', cleaned_html)
                        
                        # Method 5: BeautifulSoup bilan final DIV cleanup
                        final_soup = BeautifulSoup(cleaned_html, 'html.parser')
                        drag_drop = final_soup.find('drag-drop-matching-sentence-endings')
                        
                        if drag_drop:
                            # drag-drop element'ni extract qilish
                            drag_drop_html = str(drag_drop)
                            # Faqat bitta div wrapper bilan qaytarish
                            cleaned_html = f"<div>{drag_drop_html}</div>"
                        
                        # Method 6: Final regex cleanup
                        cleaned_html = re.sub(r'<p>(\s*<div><drag-drop-matching-sentence-endings)', r'\1', cleaned_html)
                        cleaned_html = re.sub(r'(</drag-drop-matching-sentence-endings></div>)\s*</p>', r'\1', cleaned_html)
                        cleaned_html = re.sub(r'<p>\s*<div>', '<div>', cleaned_html)
                        cleaned_html = re.sub(r'</div>\s*</p>', '</div>', cleaned_html)
                        cleaned_html = re.sub(r'</?span[^>]*>', '', cleaned_html, flags=re.IGNORECASE | re.DOTALL)
                        
                        # HTML entities tozalash
                        cleaned_html = re.sub(r'&nbsp;', ' ', cleaned_html)
                        cleaned_html = re.sub(r'&hellip;', '…', cleaned_html)
                        
                        # Whitespace tozalash
                        cleaned_html = re.sub(r'\s+', ' ', cleaned_html)
                        cleaned_html = cleaned_html.strip()
                        
                        # Final DIV count
                        div_count = cleaned_html.count('<div>')
                        
                        print(f"[ENHANCED_REMOVER] ✅ Tozalandi: {span_count} span, {p_removed_count} P, DIV count: {div_count}")
                        return cleaned_html
                        
                    except Exception as e:
                        print(f"[ENHANCED_REMOVER] ❌ Xatolik: {e}")
                        # Emergency fallback
                        import re
                        content = re.sub(r'<span[^>]*>|</span>', '', html_content, flags=re.IGNORECASE)
                        content = re.sub(r'<p>(\s*<div><drag-drop-matching-sentence-endings)', r'\1', content)
                        content = re.sub(r'(</drag-drop-matching-sentence-endings></div>)\s*</p>', r'\1', content)
                        content = re.sub(r'(<div>\s*){2,}(<drag-drop-matching-sentence-endings)', r'<div>\2', content)
                        content = re.sub(r'(</drag-drop-matching-sentence-endings>)(\s*</div>){2,}', r'\1</div>', content)
                        return content
                
                # Section HTML'dan span, P va ortiqcha DIV teglarni olib tashlash
                cleaned_section_html = remove_all_spans_and_outer_p_and_extra_divs(section_html)
                
                # Matching sentence endings parser'ga tozalangan HTML'ni yuborish
                processed_html = parse_matching_sentence_endings(cleaned_section_html)
                
                # Processed HTML'dan ham ortiqcha teglarni olib tashlash (quad safety)
                final_processed_html = remove_all_spans_and_outer_p_and_extra_divs(processed_html)
                
                # Check for drag-drop-sentence-input tags OR table-tegs-input
                patterns = [
                    r'&lt;drag-drop-sentence-input[^&gt;]*data-question-number="(\d+)"[^&gt;]*&gt;',
                    r'<drag-drop-sentence-input[^>]*data-question-number="(\d+)"[^>]*>'
                ]
                
                new_tags = []
                for pattern in patterns:
                    new_tags.extend([int(match.group(1)) for match in re.finditer(pattern, final_processed_html)])
                
                # Check for table-tegs-input component
                has_table_tegs = bool(re.search(r'<table-tegs-input[^>]*>', final_processed_html))
                
                if has_table_tegs:
                    # Extract question numbers from data-questions attribute
                    questions_match = re.search(r"data-questions='([^']+)'", final_processed_html)
                    if questions_match:
                        try:
                            import json
                            questions_data = json.loads(questions_match.group(1))
                            table_question_numbers = [int(q.get('question_number', 0)) for q in questions_data if q.get('question_number')]
                            new_tags.extend(table_question_numbers)
                            print(f"[READING] ✅ Found table-tegs-input with {len(table_question_numbers)} questions: {table_question_numbers}")
                        except Exception as e:
                            print(f"[READING] ⚠️ Error parsing table-tegs-input questions: {e}")
                
                successful_tags = [q for q in new_tags if q in unprocessed_questions]
                
                print(f"[READING] ✅ Enhanced matching sentence endings parser created {len(successful_tags)} tags: {successful_tags}")
                
                if successful_tags or has_table_tegs:
                    # Final result'dan ham ortiqcha teglarni olib tashlash
                    span_free_result = self.direct_section_replacement(original_html, section_html, final_processed_html, question_range)
                    return remove_all_spans_and_outer_p_and_extra_divs(span_free_result)
                else:
                    print(f"[READING] ⚠️ No successful tags created")
                    return remove_all_spans_and_outer_p_and_extra_divs(original_html)
                    
            except Exception as e:
                print(f"[READING] ❌ MATCHING SENTENCE ENDINGS parsing failed: {e}")
                import traceback
                print(f"[READING] Traceback: {traceback.format_exc()}")
                return remove_all_spans_and_outer_p_and_extra_divs(original_html)

        
        
        
        # Process MATCHING HEADINGS
        elif analysis.get('matching_headings', False):
            # CRITICAL: Double-check this is NOT list_selection before processing as matching_headings
            # "Choose SIX answers from the box" should be list_selection, not matching_headings
            list_selection_check_patterns = [
                r'choose\s+\w+\s+answers?\s+from\s+the\s+box',
                r'choose\s+\w+\s+letters?\s+from\s+the\s+box',
                r'write\s+the\s+correct\s+letters?\s+.*next\s+to'
            ]
            has_list_selection_pattern = any(re.search(pattern, section_html, re.IGNORECASE) for pattern in list_selection_check_patterns)
            
            if has_list_selection_pattern:
                print(f"[READING] ⚠️ Section {question_range} was detected as matching_headings but has list_selection pattern - switching to list_selection")
                try:
                    from apps.reading.utils.list_selection_perfect import parse_list_selection
                    processed_html = parse_list_selection(section_html)
                    patterns = [
                        r'<list-selection-tegs[^>]*question_type="list_selection"[^>]*>',
                        r'<list-selection-tegs[^>]*data-options[^>]*>'
                    ]
                    new_components = 0
                    for pattern in patterns:
                        new_components += len(re.findall(pattern, processed_html))
                    if new_components > 0:
                        return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                except Exception as e:
                    print(f"[READING] ⚠️ Failed to parse as list_selection: {e}")
            
            print(f"[READING] 🔧 Using MATCHING HEADINGS parser for section {question_range}")
            try:
                processed_html = parse_matching_headings(section_html)
                
                # Check for drag-drop-matching-sentence-endings component
                patterns = [
                    r'<drag-drop-matching-sentence-endings[^>]*data-question-type="matching_headings"[^>]*>',
                    r'&lt;drag-drop-matching-sentence-endings[^&gt;]*data-question-type="matching_headings"[^&gt;]*&gt;'
                ]
                
                new_components = 0
                for pattern in patterns:
                    new_components += len(re.findall(pattern, processed_html))
                
                print(f"[READING] ✅ Matching headings parser created {new_components} components")
                
                if new_components > 0:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[READING] ⚠️ No components created")
                    return original_html
                    
            except Exception as e:
                print(f"[READING] ❌ MATCHING HEADINGS parsing failed: {e}")
                import traceback
                print(f"[READING] Traceback: {traceback.format_exc()}")
                return original_html
        
        # Process TRUE/FALSE
        elif analysis.get('true_false', False):
            print(f"[READING] 🔧 Using TRUE/FALSE parser for section {question_range}")
            try:
                processed_html = parse_true_false_questions(section_html)
                
                # Check for question-input tags
                patterns = [
                    r'&lt;question-input[^&gt;]*data-question-number="(\d+)"[^&gt;]*&gt;',
                    r'<question-input[^>]*data-question-number="(\d+)"[^>]*>'
                ]
                
                new_tags = []
                for pattern in patterns:
                    new_tags.extend([int(match.group(1)) for match in re.finditer(pattern, processed_html)])
                
                successful_tags = [q for q in new_tags if q in unprocessed_questions]
                
                print(f"[READING] ✅ TRUE/FALSE parser created {len(successful_tags)} tags: {successful_tags}")
                
                if successful_tags:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[READING] ⚠️ No successful tags created")
                    return original_html
                    
            except Exception as e:
                print(f"[READING] ❌ TRUE/FALSE parsing failed: {e}")
                return original_html
        
        # Process COMPLETION
        elif analysis.get('completion', False):
            print(f"[READING] 🔧 Using COMPLETION parser for section {question_range}")
            try:
                processed_html = parse_completion_questions(section_html)
                
                # Check for question-input tags
                patterns = [
                    r'&lt;question-input[^&gt;]*data-question-number="(\d+)"[^&gt;]*&gt;',
                    r'<question-input[^>]*data-question-number="(\d+)"[^>]*>'
                ]
                
                new_tags = []
                for pattern in patterns:
                    new_tags.extend([int(match.group(1)) for match in re.finditer(pattern, processed_html)])
                
                successful_tags = [q for q in new_tags if q in unprocessed_questions]
                
                print(f"[READING] ✅ Completion parser created {len(successful_tags)} tags: {successful_tags}")
                
                if successful_tags:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[READING] ⚠️ No successful tags created")
                    return original_html
                    
            except Exception as e:
                print(f"[READING] ❌ COMPLETION parsing failed: {e}")
                import traceback
                print(f"[READING] Traceback: {traceback.format_exc()}")
                return original_html
        
        
        
        # Process OTHER MATCHING
        elif analysis.get('matching', False):
            print(f"[READING] 🔧 Using MATCHING parser for section {question_range}")
            try:
                # processed_html = parse_matching_questions(section_html)
                return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
            except Exception as e:
                print(f"[READING] ❌ MATCHING parsing failed: {e}")
                return original_html
        
        else:
            print(f"[READING] ⚠️ No specific parser for section {question_range}")
            return original_html

    def direct_section_replacement(self, original_html, section_html, processed_html, question_range):
        """Direct section replacement method - ENHANCED to handle updated HTML and preserve all sections"""
        print(f"[READING] 🔄 Direct section replacement for {question_range}")
        print(f"[READING] 📏 Original HTML length: {len(original_html)} chars")
        print(f"[READING] 📏 Section HTML length: {len(section_html)} chars")
        print(f"[READING] 📏 Processed HTML length: {len(processed_html)} chars")
        
        try:
            # Strategy 1: Try exact match first (only if section_html is still in original_html)
            if section_html in original_html:
                # CRITICAL: Verify we're not removing other sections
                # Check if processed_html contains question numbers from other sections
                processed_q_nums = set(re.findall(r'data-question-number="(\d+)"', processed_html))
                print(f"[READING] 🔍 Processed HTML contains questions: {sorted(processed_q_nums)}")
                
                # Check original HTML for all question numbers before replacement
                all_original_q_nums = set(re.findall(r'data-question-number="(\d+)"', original_html))
                print(f"[READING] 🔍 Original HTML contains questions: {sorted(all_original_q_nums)}")
                
                result = original_html.replace(section_html, processed_html, 1)  # Replace only first occurrence
                
                # Verify all questions are still present after replacement
                all_result_q_nums = set(re.findall(r'data-question-number="(\d+)"', result))
                print(f"[READING] 🔍 Result HTML contains questions: {sorted(all_result_q_nums)}")
                
                # Check if we lost any questions
                lost_questions = all_original_q_nums - all_result_q_nums
                if lost_questions:
                    print(f"[READING] ⚠️ WARNING: Lost questions after replacement: {sorted(lost_questions)}")
                    # Try to preserve them by appending
                    print(f"[READING] 🔧 Attempting to recover lost questions...")
                    # Don't return yet - try other strategies
                else:
                    print(f"[READING] ✅ All questions preserved after exact match replacement")
                
                # Clean up duplicate <h4> tags if present (e.g., <h4><h4> -> <h4>)
                result = re.sub(r'<h4>\s*<h4>', '<h4>', result)
                result = re.sub(r'</h4>\s*</h4>', '</h4>', result)
                
                if not lost_questions:
                    return result
                # If we lost questions, fall through to Strategy 2
            
            # Strategy 2: Find section by question range header (MOST RELIABLE)
            # Parse question range
            range_match = re.match(r'(\d+)\s*[-–—]\s*(\d+)', question_range) if isinstance(question_range, str) else None
            if range_match:
                start_q = int(range_match.group(1))
                end_q = int(range_match.group(2))
            elif '-' in question_range:
                start_q, end_q = map(int, question_range.split('-'))
            else:
                # Single question
                start_q = end_q = int(question_range)
            
            # Build comprehensive header patterns for this specific question range
            # CRITICAL: Use exact question numbers to avoid matching wrong sections
            dash_variants = r'[-–—]|&ndash;|&mdash;|&amp;ndash;|&amp;mdash;'
            
            if start_q == end_q:
                # Single question pattern
                header_patterns = [
                    rf'<h[1-6][^>]*>.*?<strong>Question\s+{start_q}</strong>.*?</h[1-6]>',
                    rf'<p[^>]*>.*?<strong>Question\s+{start_q}</strong>.*?</p>',
                    rf'<strong>Question\s+{start_q}</strong>',
                    rf'&lt;h[1-6][^&gt;]*&gt;.*?&lt;strong&gt;Question\s+{start_q}&lt;/strong&gt;.*?&lt;/h[1-6]&gt;',
                    rf'&lt;p[^&gt;]*&gt;.*?&lt;strong&gt;Question\s+{start_q}&lt;/strong&gt;.*?&lt;/p&gt;',
                    rf'&lt;strong&gt;Question\s+{start_q}&lt;/strong&gt;',
                ]
            else:
                # Question range pattern - ENHANCED with all dash variants
                # CRITICAL: Use exact start_q and end_q to match ONLY this specific range
                # Support both &ndash; and regular dash
                header_patterns = [
                    # Non-encoded patterns - match EXACT range (h3 with strong, no em)
                    rf'<h3[^>]*><strong>Questions?\s+{start_q}[-–—&ndash;&mdash;]{end_q}</strong></h3>',
                    # Non-encoded patterns - match EXACT range (h3 with em and strong)
                    rf'<h3[^>]*><em><strong>Questions?\s+{start_q}[-–—&ndash;&mdash;]{end_q}</strong></em></h3>',
                    # Non-encoded patterns - match EXACT range (any h tag)
                    rf'<h[1-6][^>]*>.*?<strong>Questions?\s+{start_q}[-–—&ndash;&mdash;]{end_q}</strong>.*?</h[1-6]>',
                    # Non-encoded patterns - match EXACT range (p tag)
                    rf'<p[^>]*>.*?<strong>Questions?\s+{start_q}[-–—&ndash;&mdash;]{end_q}</strong>.*?</p>',
                    # Non-encoded patterns - match EXACT range (strong only)
                    rf'<strong>Questions?\s+{start_q}[-–—&ndash;&mdash;]{end_q}</strong>',
                    # HTML-encoded patterns
                    rf'&lt;h3[^&gt;]*&gt;&lt;strong&gt;Questions?\s+{start_q}[-–—&amp;ndash;&amp;mdash;]{end_q}&lt;/strong&gt;&lt;/h3&gt;',
                    rf'&lt;h3[^&gt;]*&gt;&lt;em&gt;&lt;strong&gt;Questions?\s+{start_q}[-–—&amp;ndash;&amp;mdash;]{end_q}&lt;/strong&gt;&lt;/em&gt;&lt;/h3&gt;',
                    rf'&lt;h[1-6][^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+{start_q}[-–—&amp;ndash;&amp;mdash;]{end_q}&lt;/strong&gt;.*?&lt;/h[1-6]&gt;',
                    rf'&lt;p[^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+{start_q}[-–—&amp;ndash;&amp;mdash;]{end_q}&lt;/strong&gt;.*?&lt;/p&gt;',
                    rf'&lt;strong&gt;Questions?\s+{start_q}[-–—&amp;ndash;&amp;mdash;]{end_q}&lt;/strong&gt;',
                ]
            
            # Try each header pattern to find the section
            for header_pattern in header_patterns:
                header_match = re.search(header_pattern, original_html, re.IGNORECASE | re.DOTALL)
                if header_match:
                    header_start = header_match.start()
                    header_end = header_match.end()
                    
                    # CRITICAL FIX: Find the next section header with question numbers GREATER than end_q
                    # This prevents accidentally including previous sections
                    # Use simpler pattern and verify the number after matching
                    next_header_patterns = [
                        rf'<h3[^>]*>.*?<strong>Questions?\s+\d+[-–—&ndash;&mdash;]\d+</strong>.*?</h3>',
                        rf'<h[1-6][^>]*>.*?<strong>Questions?\s+\d+[-–—&ndash;&mdash;]\d+</strong>.*?</h[1-6]>',
                        rf'<p[^>]*>.*?<strong>Questions?\s+\d+[-–—&ndash;&mdash;]\d+</strong>.*?</p>',
                        rf'<strong>Questions?\s+\d+[-–—&ndash;&mdash;]\d+</strong>',
                        rf'&lt;h3[^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+\d+[-–—&amp;ndash;&amp;mdash;]\d+&lt;/strong&gt;.*?&lt;/h3&gt;',
                        rf'&lt;h[1-6][^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+\d+[-–—&amp;ndash;&amp;mdash;]\d+&lt;/strong&gt;.*?&lt;/h[1-6]&gt;',
                        rf'&lt;p[^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+\d+[-–—&amp;ndash;&amp;mdash;]\d+&lt;/strong&gt;.*?&lt;/p&gt;',
                        rf'&lt;strong&gt;Questions?\s+\d+[-–—&amp;ndash;&amp;mdash;]\d+&lt;/strong&gt;',
                    ]
                    
                    section_end = len(original_html)
                    # Search for next header after the current one
                    search_start = header_end
                    for next_pattern in next_header_patterns:
                        next_match = re.search(next_pattern, original_html[search_start:], re.IGNORECASE | re.DOTALL)
                        if next_match:
                            # Verify the matched question number is actually > end_q
                            match_text = next_match.group(0)
                            # Extract the first number from the match
                            num_match = re.search(r'Questions?\s+(\d+)', match_text, re.IGNORECASE)
                            if num_match:
                                next_start_q = int(num_match.group(1))
                                if next_start_q > end_q:
                                    potential_end = search_start + next_match.start()
                                    section_end = min(section_end, potential_end)
                                    print(f"[READING] 📍 Found next section header at position {potential_end} (Questions {next_start_q})")
                                    break  # Found valid next section, stop searching
                    
                    # Extract current section from original_html
                    current_section = original_html[header_start:section_end]
                    
                    # CRITICAL: Verify we're not accidentally including previous sections
                    # Check if current_section contains headers for questions < start_q
                    prev_section_check = re.search(rf'Questions?\s+(\d+)', current_section[:500], re.IGNORECASE)
                    if prev_section_check:
                        found_q = int(prev_section_check.group(1))
                        if found_q < start_q:
                            # We've included a previous section - adjust boundary
                            # Find the actual start of our section
                            actual_start_match = re.search(rf'Questions?\s+{start_q}', current_section, re.IGNORECASE)
                            if actual_start_match:
                                # Adjust header_start to the actual start
                                header_start = header_start + actual_start_match.start()
                                current_section = original_html[header_start:section_end]
                    
                    # CRITICAL: Check what questions exist before replacement
                    before_q_nums = set(re.findall(r'data-question-number="(\d+)"', original_html))
                    processed_q_nums = set(re.findall(r'data-question-number="(\d+)"', processed_html))
                    print(f"[READING] 📊 Before header-based replacement:")
                    print(f"[READING]   Original HTML has questions: {sorted(before_q_nums)}")
                    print(f"[READING]   Processed HTML has questions: {sorted(processed_q_nums)}")
                    
                    # Replace it
                    result = original_html[:header_start] + processed_html + original_html[section_end:]
                    print(f"[READING] ✅ Direct replacement successful (header-based) - replaced section {question_range}")
                    print(f"[READING] 📍 Section boundaries: start={header_start}, end={section_end}, length={section_end - header_start}")
                    
                    # CRITICAL: Verify all questions are still present after replacement
                    after_q_nums = set(re.findall(r'data-question-number="(\d+)"', result))
                    print(f"[READING] 📊 After header-based replacement:")
                    print(f"[READING]   Result HTML has questions: {sorted(after_q_nums)}")
                    
                    # Check if we lost any questions
                    lost_questions = before_q_nums - after_q_nums
                    if lost_questions:
                        print(f"[READING] ⚠️ CRITICAL ERROR: Lost questions after header-based replacement: {sorted(lost_questions)}")
                        print(f"[READING] 🔧 Attempting recovery by preserving original questions...")
                        # Try to recover by finding where lost questions were and preserving them
                        # For now, just log the error - the append strategy will handle it
                    else:
                        print(f"[READING] ✅ All questions preserved in header-based replacement")
                    
                    # Clean up duplicate tags
                    result = re.sub(r'<h[1-6]>\s*<h[1-6]>', r'<h3>', result)
                    result = re.sub(r'</h[1-6]>\s*</h[1-6]>', r'</h3>', result)
                    
                    if not lost_questions:
                        return result
                    # If we lost questions, fall through to append strategy
            
            # Strategy 3: Try partial matching with longer prefixes/suffixes
            section_start = section_html[:500] if len(section_html) > 500 else section_html
            section_end = section_html[-500:] if len(section_html) > 500 else section_html
            
            start_pos = original_html.find(section_start)
            if start_pos != -1:
                end_search = section_end
                end_pos = original_html.find(end_search, start_pos)
                if end_pos != -1:
                    end_pos += len(end_search)
                    result = original_html[:start_pos] + processed_html + original_html[end_pos:]
                    print(f"[READING] ✅ Partial replacement successful (longer match)")
                    
                    # Clean up duplicate <h4> tags if present
                    result = re.sub(r'<h4>\s*<h4>', '<h4>', result)
                    result = re.sub(r'</h4>\s*</h4>', '</h4>', result)
                    
                    return result
            
            # Strategy 4: If all else fails, try to insert processed_html after finding any question in the range
            # This is a last resort
            question_pattern = rf'<strong>{start_q}</strong>|&lt;strong&gt;{start_q}&lt;/strong&gt;'
            q_match = re.search(question_pattern, original_html)
            if q_match:
                # Find the start of this section (look backwards for Questions header)
                section_start_pos = original_html.rfind('Questions', 0, q_match.start())
                if section_start_pos != -1:
                    # Find end of section (next Questions header or end)
                    section_end_pos = len(original_html)
                    next_q_header = re.search(r'Questions?\s+\d+', original_html[q_match.end():], re.IGNORECASE)
                    if next_q_header:
                        section_end_pos = q_match.end() + next_q_header.start()
                    
                    result = original_html[:section_start_pos] + processed_html + original_html[section_end_pos:]
                    print(f"[READING] ✅ Fallback replacement successful (question-based)")
                    return result
            
            # CRITICAL: If all strategies fail, append processed_html to original_html
            # This ensures we don't lose any previous sections
            print(f"[READING] ⚠️ Could not find section {question_range} for replacement")
            print(f"[READING] 🔧 Checking if section already exists before appending...")
            
            # CRITICAL: Check if this section already exists in original_html
            # Extract question numbers from processed_html
            processed_questions = set(re.findall(r'data-question-number="(\d+)"', processed_html))
            
            # Check if any of these questions already exist in original_html
            existing_questions = set(re.findall(r'data-question-number="(\d+)"', original_html))
            overlap = processed_questions & existing_questions
            
            if overlap:
                print(f"[READING] ⚠️ Section {question_range} questions {sorted(overlap)} already exist in original_html")
                print(f"[READING] 🔧 Attempting to replace existing section instead of appending...")
                # Try to find and replace the existing section
                # Find the section header for this range
                range_match = re.match(r'(\d+)\s*[-–—]\s*(\d+)', question_range) if isinstance(question_range, str) else None
                if range_match:
                    start_q = int(range_match.group(1))
                    end_q = int(range_match.group(2))
                    # Try to find section header
                    header_pattern = rf'<h3[^>]*>.*?<strong>Questions?\s+{start_q}[-–—&ndash;&mdash;]{end_q}</strong>.*?</h3>'
                    header_match = re.search(header_pattern, original_html, re.IGNORECASE | re.DOTALL)
                    if header_match:
                        header_start = header_match.start()
                        # Find next section or end
                        next_header = re.search(rf'<h3[^>]*>.*?<strong>Questions?\s+\d+[-–—&ndash;&mdash;]\d+</strong>.*?</h3>', 
                                               original_html[header_match.end():], re.IGNORECASE | re.DOTALL)
                        section_end = header_match.end() + next_header.start() if next_header else len(original_html)
                        result = original_html[:header_start] + processed_html + original_html[section_end:]
                        print(f"[READING] ✅ Replaced existing section {question_range}")
                        return result
                # If can't replace, return original to preserve existing content
                return original_html
            
            print(f"[READING] 🔧 Appending processed section (no duplicates detected)")
            
            # Check what questions we have before appending
            before_q_nums = set(re.findall(r'data-question-number="(\d+)"', original_html))
            processed_q_nums = set(re.findall(r'data-question-number="(\d+)"', processed_html))
            print(f"[READING] 📊 Before append - Original has questions: {sorted(before_q_nums)}")
            print(f"[READING] 📊 Processed section has questions: {sorted(processed_q_nums)}")
            
            result = original_html + "\n\n" + processed_html
            
            # Verify all questions are present
            after_q_nums = set(re.findall(r'data-question-number="(\d+)"', result))
            print(f"[READING] 📊 After append - Result has questions: {sorted(after_q_nums)}")
            
            return result
                
        except Exception as e:
            print(f"[READING] ❌ Direct replacement failed: {e}")
            import traceback
            print(f"[READING] Traceback: {traceback.format_exc()}")
            return original_html
    
    def process_multi_type_questions(self, html_content):
        """ULTIMATE multi-type processor with ALL question types including matching_information"""
        print(f"[READING] 🏭 Starting ULTIMATE multi-type question processing...")
        
        # Step 0: Clean malformed tags FIRST
        html_content = self.clean_malformed_tags(html_content)
        
        # Step 1: Check for multiple consecutive list selection questions first
        if self.has_multiple_consecutive_list_selections(html_content):
            print(f"[READING] 🔍 Detected multiple consecutive list selection questions")
            return self.process_multiple_list_selections(html_content)
        
        # Step 2: Find existing tags
        existing_tags = self.find_existing_tags(html_content)
        
        # Step 3: Split into sections with ENHANCED detection
        sections = self.split_question_sections(html_content)
        
        # Step 4: Process each section IN ORDER (by question number, not position)
        # Sort sections by start_question to ensure correct processing order
        sections_sorted = sorted(sections, key=lambda x: x['start_question'])
        print(f"[READING] 📋 Processing sections in order: {[s['range'] for s in sections_sorted]}")
        
        result_html = html_content
        changes_made = False
        
        for section in sections_sorted:
            # CRITICAL: Always re-extract section from current result_html to get updated content
            # This ensures we're working with the latest HTML after previous replacements
            # Positions become invalid after replacements, so we always search by question range
            start_q = section['start_question']
            end_q = section['end_question']
            
            # Build comprehensive patterns to find the section header
            if start_q == end_q:
                range_patterns = [
                    rf'<h[1-6][^>]*>.*?<strong>Question\s+{start_q}</strong>.*?</h[1-6]>',
                    rf'<p[^>]*>.*?<strong>Question\s+{start_q}</strong>.*?</p>',
                    rf'<strong>Question\s+{start_q}</strong>',
                    rf'&lt;h[1-6][^&gt;]*&gt;.*?&lt;strong&gt;Question\s+{start_q}&lt;/strong&gt;.*?&lt;/h[1-6]&gt;',
                    rf'&lt;p[^&gt;]*&gt;.*?&lt;strong&gt;Question\s+{start_q}&lt;/strong&gt;.*?&lt;/p&gt;',
                    rf'&lt;strong&gt;Question\s+{start_q}&lt;/strong&gt;',
                ]
            else:
                # Build dash/and patterns that match: dash characters OR "and"
                dash_pattern = r'[-–—]|&ndash;|&mdash;|&amp;ndash;|&amp;mdash;'
                range_num_pattern_dash = rf'{start_q}(?:{dash_pattern}){end_q}'
                range_num_pattern_and = rf'{start_q}\s+(?:and|&amp;and)\s+{end_q}'
                range_patterns = [
                    # Pattern with HTML entities (most common)
                    rf'<h[1-6][^>]*>.*?<strong>Questions?\s+{range_num_pattern_dash}</strong>.*?</h[1-6]>',
                    rf'<p[^>]*>.*?<strong>Questions?\s+{range_num_pattern_dash}</strong>.*?</p>',
                    rf'<strong>Questions?\s+{range_num_pattern_dash}</strong>',
                    rf'<h[1-6][^>]*>.*?<strong>Questions?\s+{range_num_pattern_and}</strong>.*?</h[1-6]>',
                    rf'<p[^>]*>.*?<strong>Questions?\s+{range_num_pattern_and}</strong>.*?</p>',
                    rf'<strong>Questions?\s+{range_num_pattern_and}</strong>',
                    # Pattern with HTML-encoded tags
                    rf'&lt;h[1-6][^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+{range_num_pattern_dash}&lt;/strong&gt;.*?&lt;/h[1-6]&gt;',
                    rf'&lt;p[^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+{range_num_pattern_dash}&lt;/strong&gt;.*?&lt;/p&gt;',
                    rf'&lt;strong&gt;Questions?\s+{range_num_pattern_dash}&lt;/strong&gt;',
                    rf'&lt;h[1-6][^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+{range_num_pattern_and}&lt;/strong&gt;.*?&lt;/h[1-6]&gt;',
                    rf'&lt;p[^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+{range_num_pattern_and}&lt;/strong&gt;.*?&lt;/p&gt;',
                    rf'&lt;strong&gt;Questions?\s+{range_num_pattern_and}&lt;/strong&gt;',
                    # Also try without strong tag (just in case)
                    rf'<h[1-6][^>]*>.*?Questions?\s+{range_num_pattern_dash}.*?</h[1-6]>',
                    rf'Questions?\s+{range_num_pattern_dash}',
                    rf'<h[1-6][^>]*>.*?Questions?\s+{range_num_pattern_and}.*?</h[1-6]>',
                    rf'Questions?\s+{range_num_pattern_and}',
                ]
            
            # Find section header in current result_html
            # Search for the SPECIFIC section (e.g., "Questions 24-26"), not just any "Questions X-Y"
            range_match = None
            matched_pattern_idx = None
            
            # CRITICAL: Search for the EXACT text "Questions {start_q}-{end_q}" or similar
            # This prevents finding wrong sections
            search_texts = [
                f"Questions {start_q}–{end_q}",
                f"Questions {start_q}-{end_q}",
                f"Questions {start_q}—{end_q}",
                f"Questions {start_q}&ndash;{end_q}",
                f"Questions {start_q}&mdash;{end_q}",
                f"Questions {start_q} and {end_q}",
                f"Questions {start_q} &amp;and {end_q}",
                f"Questions {start_q}&nbsp;and&nbsp;{end_q}",
                f"Question {start_q}–{end_q}",
                f"Question {start_q}-{end_q}",
                f"Question {start_q} and {end_q}",
            ]
            
            # Find the position of this exact text
            for search_text in search_texts:
                pos = result_html.find(search_text)
                if pos != -1:
                    # Found it! Now find the start of the tag containing this text
                    # Look backwards for < character
                    tag_start = result_html.rfind('<', max(0, pos - 100), pos)
                    if tag_start != -1:
                        # Find the end of this tag
                        tag_end = result_html.find('>', pos) + 1
                        if tag_end > pos:
                            # Create a match object-like structure
                            class FakeMatch:
                                def __init__(self, start, end):
                                    self._start = start
                                    self._end = end
                                def start(self):
                                    return self._start
                                def end(self):
                                    return self._end
                            
                            range_match = FakeMatch(tag_start, tag_end)
                            matched_pattern_idx = 0
                            print(f"[READING] ✅ Found section {section['range']} header at position {tag_start}")
                            break
            
            if range_match:
                # Find section boundaries
                section_start = range_match.start()
                header_end = range_match.end()
                
                # Find next section header or end of content
                next_dash_pattern = r'[-–—]|&ndash;|&mdash;|&amp;ndash;|&amp;mdash;'
                next_and_pattern = r'\s+(?:and|&amp;and)\s+'
                next_range_patterns = [
                    rf'<h[1-6][^>]*>.*?<strong>Questions?\s+\d+(?:{next_dash_pattern})\d+</strong>.*?</h[1-6]>',
                    rf'<p[^>]*>.*?<strong>Questions?\s+\d+(?:{next_dash_pattern})\d+</strong>.*?</p>',
                    rf'<strong>Questions?\s+\d+(?:{next_dash_pattern})\d+</strong>',
                    rf'&lt;h[1-6][^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+\d+(?:{next_dash_pattern})\d+&lt;/strong&gt;.*?&lt;/h[1-6]&gt;',
                    rf'&lt;p[^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+\d+(?:{next_dash_pattern})\d+&lt;/strong&gt;.*?&lt;/p&gt;',
                    rf'&lt;strong&gt;Questions?\s+\d+(?:{next_dash_pattern})\d+&lt;/strong&gt;',
                    rf'Questions?\s+\d+(?:{next_dash_pattern})\d+',
                    rf'<h[1-6][^>]*>.*?<strong>Questions?\s+\d+{next_and_pattern}\d+</strong>.*?</h[1-6]>',
                    rf'<p[^>]*>.*?<strong>Questions?\s+\d+{next_and_pattern}\d+</strong>.*?</p>',
                    rf'<strong>Questions?\s+\d+{next_and_pattern}\d+</strong>',
                    rf'&lt;h[1-6][^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+\d+{next_and_pattern}\d+&lt;/strong&gt;.*?&lt;/h[1-6]&gt;',
                    rf'&lt;p[^&gt;]*&gt;.*?&lt;strong&gt;Questions?\s+\d+{next_and_pattern}\d+&lt;/strong&gt;.*?&lt;/p&gt;',
                    rf'&lt;strong&gt;Questions?\s+\d+{next_and_pattern}\d+&lt;/strong&gt;',
                    rf'Questions?\s+\d+{next_and_pattern}\d+',
                ]
                
                section_end = len(result_html)
                for next_pattern in next_range_patterns:
                    next_match = re.search(next_pattern, result_html[header_end:], re.IGNORECASE | re.DOTALL)
                    if next_match:
                        potential_end = header_end + next_match.start()
                        section_end = min(section_end, potential_end)
                
                current_section_html = result_html[section_start:section_end]
                print(f"[READING] 🔍 Re-extracted section {section['range']} from current HTML ({len(current_section_html)} chars)")
                print(f"[READING] 📍 Section boundaries: start={section_start}, end={section_end}")
                
                # CRITICAL FIX: If extracted section is too small (just header), use original section HTML
                if len(current_section_html) < 100 and 'html' in section:
                    print(f"[READING] ⚠️ Section too small ({len(current_section_html)} chars), using original HTML ({len(section['html'])} chars)")
                    current_section_html = section['html']
            else:
                # Fallback: Try to find section by searching for first question number in range
                print(f"[READING] ⚠️ Could not re-find section {section['range']} header, trying fallback...")
                # Try finding by first question number
                first_q_pattern = rf'<strong>{start_q}</strong>|&lt;strong&gt;{start_q}&lt;/strong&gt;'
                first_q_match = re.search(first_q_pattern, result_html, re.IGNORECASE)
                if first_q_match:
                    # Look backwards for Questions header
                    search_start = max(0, first_q_match.start() - 500)
                    before_text = result_html[search_start:first_q_match.start()]
                    questions_header_match = re.search(r'Questions?\s+\d+', before_text, re.IGNORECASE)
                    if questions_header_match:
                        section_start = search_start + questions_header_match.start()
                        # Find end of section
                        section_end = len(result_html)
                        next_q_header = re.search(r'Questions?\s+\d+', result_html[first_q_match.end():], re.IGNORECASE)
                        if next_q_header:
                            section_end = first_q_match.end() + next_q_header.start()
                        current_section_html = result_html[section_start:section_end]
                        print(f"[READING] ✅ Found section {section['range']} using fallback method ({len(current_section_html)} chars)")
                    else:
                        current_section_html = section['html']
                        print(f"[READING] ⚠️ Fallback failed, using original HTML")
                else:
                    # Last resort: use original section HTML
                    current_section_html = section['html']
                    print(f"[READING] ⚠️ Could not re-find section {section['range']}, using original HTML")
            
            # Update existing_tags from current result_html (tags may have been added by previous sections)
            current_existing_tags = self.find_existing_tags(result_html)
            
            # Find unprocessed questions in this section using CURRENT HTML
            unprocessed = self.get_unprocessed_questions_in_section(
                current_section_html, current_existing_tags, 
                section['start_question'], section['end_question']
            )
            
            if not unprocessed:
                print(f"[READING] ⏭️ Section {section['range']}: All questions already processed")
                continue
            
            print(f"[READING] 🎯 Processing section {section['range']} with {len(unprocessed)} unprocessed questions: {unprocessed}")
            
            # Analyze this section's type using CURRENT section HTML
            analysis = self.analyze_section_type(current_section_html, section['range'], unprocessed, result_html)
            
            # Process this section - pass CURRENT section HTML, not original
            old_result = result_html
            old_q_nums = set(re.findall(r'data-question-number="(\d+)"', old_result))
            print(f"[READING] 📊 Before processing section {section['range']}:")
            print(f"[READING]   Current result_html has questions: {sorted(old_q_nums)}")
            
            result_html = self.process_section(
                current_section_html, analysis, section['range'], 
                unprocessed, result_html
            )
            
            new_q_nums = set(re.findall(r'data-question-number="(\d+)"', result_html))
            print(f"[READING] 📊 After processing section {section['range']}:")
            print(f"[READING]   Result HTML has questions: {sorted(new_q_nums)}")
            
            # Check if we lost any questions
            lost_questions = old_q_nums - new_q_nums
            if lost_questions:
                print(f"[READING] ⚠️ CRITICAL: Lost questions after processing {section['range']}: {sorted(lost_questions)}")
                print(f"[READING] 🔧 Attempting to recover by preserving original content...")
                # Try to merge: keep old questions and add new ones
                # Find the lost questions in old_result and preserve them
                for lost_q in lost_questions:
                    # Find the question in old_result - try multiple patterns to capture full paragraph with question text
                    # Pattern 1: Full paragraph with question number, text, and question-input tag
                    lost_patterns = [
                        # Pattern 1: <p>...<strong>Q</strong> text <question-input...></p>
                        rf'<p[^>]*>.*?<strong>\s*{lost_q}\s*</strong>.*?<question-input[^>]*data-question-number="{lost_q}"[^>]*>.*?</p>',
                        # Pattern 2: <p>...<strong>Q</strong> text <question-input.../> (self-closing)
                        rf'<p[^>]*>.*?<strong>\s*{lost_q}\s*</strong>.*?<question-input[^>]*data-question-number="{lost_q}"[^>]*/>.*?</p>',
                        # Pattern 3: Just the paragraph containing the question-input tag
                        rf'<p[^>]*>.*?<question-input[^>]*data-question-number="{lost_q}"[^>]*>.*?</p>',
                        # Pattern 4: Self-closing question-input in paragraph
                        rf'<p[^>]*>.*?<question-input[^>]*data-question-number="{lost_q}"[^>]*/>.*?</p>',
                        # Pattern 5: Just the question-input tag (fallback)
                        rf'<question-input[^>]*data-question-number="{lost_q}"[^>]*>',
                        rf'<question-input[^>]*data-question-number="{lost_q}"[^>]*/>',
                    ]
                    
                    lost_match = None
                    for pattern in lost_patterns:
                        lost_match = re.search(pattern, old_result, re.DOTALL | re.IGNORECASE)
                        if lost_match:
                            break
                    
                    if lost_match:
                        # Check if it's already in result_html
                        if lost_q not in new_q_nums:
                            # Append it to result_html with the full paragraph
                            result_html = result_html + "\n\n" + lost_match.group(0)
                            print(f"[READING] ✅ Recovered question {lost_q} with full content")
                    else:
                        # Try to find by question number in paragraph
                        q_num_pattern = rf'<p[^>]*>.*?<strong>\s*{lost_q}\s*</strong>.*?</p>'
                        q_num_match = re.search(q_num_pattern, old_result, re.DOTALL | re.IGNORECASE)
                        if q_num_match and lost_q not in new_q_nums:
                            result_html = result_html + "\n\n" + q_num_match.group(0)
                            print(f"[READING] ✅ Recovered question {lost_q} by number pattern")
                # Re-check after recovery
                final_q_nums = set(re.findall(r'data-question-number="(\d+)"', result_html))
                print(f"[READING] 📊 After recovery: {sorted(final_q_nums)}")
            
            if result_html != old_result:
                changes_made = True
                print(f"[READING] ✅ Section {section['range']} processed successfully")
        
        if changes_made:
            print(f"[READING] ✅ ULTIMATE multi-type processing complete - CHANGES MADE")
            # Clean up duplicate instruction text after table-tegs components
            result_html = self.cleanup_duplicate_instruction_text(result_html)
        else:
            print(f"[READING] ⚠️ ULTIMATE multi-type processing complete - NO CHANGES")
        
        # CRITICAL: Convert ALL multiple_choice types to multiple_choice_with_multiple_answer
        # This ensures ALL multiple choice questions use multiple_choice_with_multiple_answer
        conversion_patterns = [
            (r'data-question-type="multiple_choice"', 'data-question-type="multiple_choice_with_multiple_answer"'),
            (r'data-question-type="multiple_choice_with_single_answer"', 'data-question-type="multiple_choice_with_multiple_answer"'),
        ]
        
        total_converted = 0
        for old_pattern, new_replacement in conversion_patterns:
            if re.search(old_pattern, result_html):
                count_before = len(re.findall(old_pattern, result_html))
                result_html = re.sub(old_pattern, new_replacement, result_html)
                total_converted += count_before
                print(f"[READING] 🔄 process_multi_type_questions: Converted {count_before} {old_pattern} to {new_replacement}")
        
        if total_converted > 0:
            print(f"[READING] ✅ process_multi_type_questions: Total converted {total_converted} multiple_choice types to multiple_choice_with_multiple_answer")
        
        # CRITICAL: Remove ALL duplicate sections (27-30, 31-35, 36-40)
        # Do this BEFORE final cleanup to ensure proper section removal
        result_html = self.remove_all_duplicate_sections(result_html)
        
        # FINAL CLEANUP: Remove any remaining duplicate question tags and sections
        result_html = self.final_duplicate_cleanup(result_html)
        
        # EXTRA PASS: One more time to catch any remaining duplicates
        result_html = self.remove_all_duplicate_sections(result_html)
        
        # FINAL AGGRESSIVE PASS: Remove duplicate Questions 36-40 using regex
        # This catches cases where BeautifulSoup might miss duplicates
        print(f"[READING] 🔥 FINAL AGGRESSIVE PASS: Removing duplicate Questions 36-40 sections...")
        
        # Pattern 1: Full section with all questions
        questions_36_40_pattern = r'(<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>.*?<question-input[^>]*data-question-number="40"[^>]*>.*?</p>\s*)'
        matches = list(re.finditer(questions_36_40_pattern, result_html, re.DOTALL | re.IGNORECASE))
        if len(matches) > 1:
            print(f"[READING] 🔥 Found {len(matches)} Questions 36-40 sections (pattern 1), removing {len(matches)-1} duplicates")
            # Keep first, remove all others (process from end to start to preserve positions)
            for match in reversed(matches[1:]):
                result_html = result_html[:match.start()] + result_html[match.end():]
                print(f"[READING] 🗑️ Removed duplicate Questions 36-40 at position {match.start()}")
        
        # Pattern 2: More flexible pattern
        questions_36_40_pattern2 = r'(<h3[^>]*>\s*<strong>Questions\s+36[–-]40</strong>\s*</h3>.*?<question-input[^>]*data-question-number="40"[^>]*>.*?</p>)'
        matches2 = list(re.finditer(questions_36_40_pattern2, result_html, re.DOTALL | re.IGNORECASE))
        if len(matches2) > 1:
            print(f"[READING] 🔥 Found {len(matches2)} Questions 36-40 sections (pattern 2), removing {len(matches2)-1} duplicates")
            for match in reversed(matches2[1:]):
                result_html = result_html[:match.start()] + result_html[match.end():]
                print(f"[READING] 🗑️ Removed duplicate Questions 36-40 at position {match.start()} (pattern 2)")
        
        # Final verification: Count Questions 36-40 headers
        section_36_40_count = len(re.findall(r'<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>', result_html, re.IGNORECASE))
        if section_36_40_count > 1:
            print(f"[READING] ⚠️ CRITICAL: Still {section_36_40_count} Questions 36-40 headers found!")
            # Ultra-aggressive: Find all headers and remove duplicates
            header_pattern = r'(<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>)'
            header_matches = list(re.finditer(header_pattern, result_html, re.IGNORECASE))
            if len(header_matches) > 1:
                # For each duplicate header, find and remove its entire section
                for i, header_match in enumerate(header_matches[1:], 1):  # Skip first
                    header_start = header_match.start()
                    # Find end of section
                    next_section = re.search(r'<h3[^>]*><strong>Questions\s+\d+[–-]\d+</strong></h3>', 
                                            result_html[header_match.end():], re.IGNORECASE)
                    if next_section:
                        section_end = header_match.end() + next_section.start()
                    else:
                        # Find last question 40 in this section
                        q40_matches = list(re.finditer(r'<question-input[^>]*data-question-number="40"[^>]*>', 
                                                      result_html[header_match.end():], re.IGNORECASE))
                        if q40_matches:
                            last_q40_pos = header_match.end() + q40_matches[-1].end()
                            # Find closing </p> after question 40
                            p_close = result_html.find('</p>', last_q40_pos)
                            section_end = p_close + 4 if p_close != -1 else len(result_html)
                        else:
                            section_end = len(result_html)
                    
                    # Remove this duplicate section
                    result_html = result_html[:header_start] + result_html[section_end:]
                    print(f"[READING] 🗑️ ULTRA-AGGRESSIVE: Removed duplicate Questions 36-40 section #{i+1}")
        else:
            print(f"[READING] ✅ FINAL PASS: Only 1 Questions 36-40 section - OK")
        
        return result_html
    
    def final_duplicate_cleanup(self, html_content):
        """FINAL aggressive cleanup to remove ANY remaining duplicates"""
        if not html_content:
            return html_content
        
        try:
            print(f"[READING] 🔥 FINAL duplicate cleanup...")
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Track seen questions
            seen_questions = set()
            removed = 0
            
            # Remove duplicate question-input tags - ENHANCED to preserve all unique questions
            # First pass: collect all question tags with their positions
            all_question_tags = []
            for tag in soup.find_all('question-input'):
                q_num = tag.get('data-question-number')
                if q_num:
                    # Get position in document
                    position = len(str(soup)[:soup.get_text().find(tag.get_text())])
                    all_question_tags.append({
                        'tag': tag,
                        'q_num': q_num,
                        'position': position,
                        'has_options': 'data-question-options' in str(tag)
                    })
            
            # Sort by position to keep first occurrence
            all_question_tags.sort(key=lambda x: x['position'])
            
            # Remove duplicates, keeping first occurrence
            for item in all_question_tags:
                q_num = item['q_num']
                if q_num in seen_questions:
                    # This is a duplicate - remove it
                    parent = item['tag'].find_parent('p')
                    if parent:
                        parent.decompose()
                        removed += 1
                        print(f"[READING] 🔥 Final cleanup: Removed duplicate Q{q_num}")
                    else:
                        item['tag'].decompose()
                        removed += 1
                else:
                    seen_questions.add(q_num)
            
            # Remove duplicate drag-drop-sentence-input tags - ENHANCED
            all_drag_tags = []
            for tag in soup.find_all('drag-drop-sentence-input'):
                q_num = tag.get('data-question-number')
                if q_num:
                    position = len(str(soup)[:soup.get_text().find(tag.get_text())])
                    all_drag_tags.append({
                        'tag': tag,
                        'q_num': q_num,
                        'position': position
                    })
            
            all_drag_tags.sort(key=lambda x: x['position'])
            
            for item in all_drag_tags:
                q_num = item['q_num']
                if q_num in seen_questions:
                    parent = item['tag'].find_parent('p')
                    if parent:
                        parent.decompose()
                        removed += 1
                        print(f"[READING] 🔥 Final cleanup: Removed duplicate Q{q_num}")
                    else:
                        item['tag'].decompose()
                        removed += 1
                else:
                    seen_questions.add(q_num)
            
            # Remove duplicate section headers - ENHANCED: Track position to keep first
            seen_sections = {}
            all_section_tags = []
            
            # First pass: collect all section headers with positions
            for tag in soup.find_all(['h3', 'h2', 'p']):
                text = tag.get_text(strip=True)
                match = re.search(r'Questions?\s+(\d+)[-–](\d+)', text, re.IGNORECASE)
                if match:
                    section_key = f"{match.group(1)}-{match.group(2)}"
                    start_q = int(match.group(1))
                    end_q = int(match.group(2))
                    
                    # Get position in document (use tag's position in parent)
                    try:
                        # Try to get position by finding tag in string representation
                        html_str = str(soup)
                        tag_str = str(tag)
                        position = html_str.find(tag_str)
                        if position == -1:
                            # Fallback: use index in parent
                            parent = tag.find_parent()
                            if parent:
                                position = list(parent.children).index(tag) if tag in parent.children else len(all_section_tags) * 1000
                            else:
                                position = len(all_section_tags) * 1000
                    except:
                        position = len(all_section_tags) * 1000
                    
                    all_section_tags.append({
                        'tag': tag,
                        'key': section_key,
                        'start': start_q,
                        'end': end_q,
                        'position': position
                    })
            
            # Sort by position to keep first occurrence
            all_section_tags.sort(key=lambda x: x['position'])
            
            # Remove duplicates - keep only first occurrence of each section
            for item in all_section_tags:
                section_key = item['key']
                if section_key in seen_sections:
                    # DUPLICATE - Remove this header and ALL following content until next section
                    print(f"[READING] 🔥 Final cleanup: Removing duplicate section {section_key} at position {item['position']}")
                    
                    tag = item['tag']
                    to_remove = [tag]
                    current = tag.find_next_sibling()
                    max_iterations = 1000
                    iteration = 0
                    
                    while current and iteration < max_iterations:
                        iteration += 1
                        
                        # Stop at next section header
                        if current.name in ['h3', 'h2', 'h1']:
                            current_text = current.get_text(strip=True)
                            if re.search(r'Questions?\s+\d+[-–]\d+', current_text, re.IGNORECASE):
                                print(f"[READING] 🛑 Stopped at next section header: {current_text[:50]}")
                                break
                        
                        if current.name in ['drag-drop-matching-sentence-endings', 'table-tegs', 'table-tegs-input']:
                            print(f"[READING] 🛑 Stopped at component: {current.name}")
                            break
                        
                        # Check if this paragraph contains a question number from NEXT section
                        if current.name == 'p':
                            p_text = str(current)
                            q_match = re.search(r'<strong>\s*(\d+)\s*</strong>', p_text, re.IGNORECASE)
                            if q_match:
                                q_num = int(q_match.group(1))
                                # If this question is outside the range we're removing, stop
                                if q_num > item['end']:
                                    print(f"[READING] 🛑 Stopped at question {q_num} (outside range {section_key})")
                                    break
                        
                        to_remove.append(current)
                        current = current.find_next_sibling()
                    
                    print(f"[READING] 🗑️ Removing {len(to_remove)} elements for duplicate section {section_key}")
                    for elem in to_remove:
                        elem.decompose()
                        removed += 1
                else:
                    # First occurrence - keep it
                    seen_sections[section_key] = {
                        'tag': item['tag'],
                        'start': item['start'],
                        'end': item['end'],
                        'position': item['position']
                    }
                    print(f"[READING] ✅ Keeping FIRST occurrence of section {section_key} at position {item['position']}")
            
            print(f"[READING] ✅ Final cleanup: Removed {removed} duplicate elements")
            return str(soup)
            
        except Exception as e:
            print(f"[READING] ❌ Final cleanup error: {e}")
            return html_content

    def remove_all_duplicate_sections(self, html_content):
        """Remove ALL duplicate question sections - NUCLEAR MODE"""
        if not html_content:
            return html_content
        
        try:
            print(f"[READING] 💣 NUCLEAR duplicate removal starting...")
            
            from bs4 import BeautifulSoup
            
            # STEP 1: Remove duplicate question tags (keep only first occurrence)
            soup = BeautifulSoup(html_content, 'html.parser')
            seen_questions = {}
            duplicates_removed = 0
            
            # Collect ALL question tags first
            all_tags = []
            for tag in soup.find_all('question-input'):
                q_num = tag.get('data-question-number')
                if q_num:
                    all_tags.append((int(q_num), tag))
            
            for tag in soup.find_all('drag-drop-sentence-input'):
                q_num = tag.get('data-question-number')
                if q_num:
                    all_tags.append((int(q_num), tag))
            
            # Remove duplicates
            for q_num, tag in all_tags:
                if q_num in seen_questions:
                    parent = tag.find_parent('p')
                    if parent:
                        parent.decompose()
                        duplicates_removed += 1
                        print(f"[READING] 🗑️ Removed duplicate Q{q_num} paragraph")
                    else:
                        tag.decompose()
                        duplicates_removed += 1
                        print(f"[READING] 🗑️ Removed duplicate Q{q_num} tag")
                else:
                    seen_questions[q_num] = tag
            
            # STEP 2: Remove duplicate section headers - ENHANCED to preserve all unique sections
            # Find ALL section headers with their question content
            all_headers = []
            for tag in soup.find_all(['h3', 'h2', 'p']):
                text = tag.get_text(strip=True)
                match = re.search(r'Questions?\s+(\d+)[-–](\d+)', text, re.IGNORECASE)
                if match:
                    start_q = int(match.group(1))
                    end_q = int(match.group(2))
                    
                    # Check if this section has actual question content
                    has_questions = False
                    # Look for question-input or drag-drop tags in this section
                    current = tag.find_next_sibling()
                    max_check = 50  # Check next 50 siblings
                    check_count = 0
                    while current and check_count < max_check:
                        check_count += 1
                        # Check for question tags
                        if current.name == 'question-input' or current.name == 'drag-drop-sentence-input':
                            has_questions = True
                            break
                        # Check for question numbers in paragraphs
                        if current.name == 'p':
                            q_match = re.search(r'<strong>\s*(\d+)\s*</strong>', str(current), re.IGNORECASE)
                            if q_match:
                                q_num = int(q_match.group(1))
                                if start_q <= q_num <= end_q:
                                    has_questions = True
                                    break
                        # Stop at next section
                        if current.name in ['h3', 'h2', 'h1']:
                            next_text = current.get_text(strip=True)
                            if re.search(r'Questions?\s+\d+[-–]\d+', next_text, re.IGNORECASE):
                                break
                        current = current.find_next_sibling()
                    
                    all_headers.append({
                        'tag': tag,
                        'start': start_q,
                        'end': end_q,
                        'key': f"{start_q}-{end_q}",
                        'text': text,
                        'has_questions': has_questions,
                        'position': len(all_headers)  # Track order
                    })
            
            # Group by section key
            sections_by_key = {}
            for header in all_headers:
                key = header['key']
                if key not in sections_by_key:
                    sections_by_key[key] = []
                sections_by_key[key].append(header)
            
            # Remove ONLY true duplicates - CRITICAL: Keep first occurrence, remove all others
            for key, headers in sections_by_key.items():
                if len(headers) > 1:
                    print(f"[READING] 💣 Found {len(headers)} instances of section {key}")
                    
                    # CRITICAL: Use actual document order, not position index
                    # Get the actual position in the HTML string
                    html_str = str(soup)
                    for header in headers:
                        tag_str = str(header['tag'])
                        actual_pos = html_str.find(tag_str)
                        if actual_pos == -1:
                            # Fallback: use position index
                            actual_pos = header['position'] * 1000
                        header['actual_position'] = actual_pos
                    
                    # Sort by actual position to keep the FIRST one
                    headers_sorted = sorted(headers, key=lambda x: x['actual_position'])
                    keep_header = headers_sorted[0]  # Keep FIRST occurrence
                    to_remove = headers_sorted[1:]  # Remove ALL others
                    
                    print(f"[READING] ✅ Keeping FIRST section {key} at position {keep_header['actual_position']} (has_questions={keep_header['has_questions']})")
                    
                    # Remove ALL duplicate sections (keep only first)
                    for header in to_remove:
                        print(f"[READING] 🗑️ Removing duplicate section {key} at position {header['actual_position']}")
                        tag = header['tag']
                        
                        # Collect ALL content after this header until next section or end of parent
                        to_remove_elems = [tag]
                        current = tag.find_next_sibling()
                        max_iterations = 1000
                        iteration = 0
                        
                        # Also check parent to find where section ends
                        parent = tag.find_parent(['div', 'body', None])
                        
                        while current and iteration < max_iterations:
                            iteration += 1
                            
                            # Stop at next section header
                            if current.name in ['h3', 'h2', 'h1']:
                                current_text = current.get_text(strip=True)
                                if re.search(r'Questions?\s+\d+[-–]\d+', current_text, re.IGNORECASE):
                                    print(f"[READING] 🛑 Stopped at next section header: {current_text[:50]}")
                                    break
                            
                            # Stop at component (different section)
                            if current.name in ['drag-drop-matching-sentence-endings', 'table-tegs', 'table-tegs-input']:
                                print(f"[READING] 🛑 Stopped at component: {current.name}")
                                break
                            
                            # Stop if question from next section
                            if current.name == 'p':
                                q_match = re.search(r'<strong>\s*(\d+)\s*</strong>', str(current), re.IGNORECASE)
                                if q_match:
                                    q_num = int(q_match.group(1))
                                    if q_num > header['end']:
                                        print(f"[READING] 🛑 Stopped at question {q_num} (outside range {key})")
                                        break
                            
                            # Stop if we hit the end of parent div
                            if parent and current == parent.find_all(recursive=False)[-1] if parent.find_all(recursive=False) else False:
                                print(f"[READING] 🛑 Stopped at end of parent")
                                break
                            
                            to_remove_elems.append(current)
                            current = current.find_next_sibling()
                            
                            # Safety: if no next sibling, we've reached the end
                            if not current:
                                break
                        
                        # Remove ALL duplicate section content
                        print(f"[READING] 🗑️ Removing {len(to_remove_elems)} elements for duplicate section {key}")
                        for elem in to_remove_elems:
                            try:
                                elem.decompose()
                                duplicates_removed += 1
                            except Exception as e:
                                print(f"[READING] ⚠️ Error removing element: {e}")
                                # Try to remove from parent
                                try:
                                    if elem.parent:
                                        elem.parent.decompose()
                                except:
                                    pass
            
            result_html = str(soup)
            print(f"[READING] ✅ NUCLEAR removal complete: {duplicates_removed} elements removed")
            
            # STEP 3: ULTRA-AGGRESSIVE regex-based duplicate Questions 36-40 removal
            # This catches duplicates that BeautifulSoup might miss
            print(f"[READING] 🔥 ULTRA-AGGRESSIVE regex duplicate removal for Questions 36-40...")
            
            # Count Questions 36-40 sections BEFORE removal
            section_36_40_count_before = len(re.findall(r'<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>', result_html, re.IGNORECASE))
            print(f"[READING] 📊 Found {section_36_40_count_before} Questions 36-40 sections before removal")
            
            if section_36_40_count_before > 1:
                # Pattern 1: Full section from header to last question
                questions_36_40_pattern = r'(<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>.*?<question-input[^>]*data-question-number="40"[^>]*>.*?</p>\s*)'
                matches = list(re.finditer(questions_36_40_pattern, result_html, re.DOTALL | re.IGNORECASE))
                
                if len(matches) > 1:
                    print(f"[READING] 🔥 Found {len(matches)} Questions 36-40 full sections, removing {len(matches)-1} duplicates")
                    # Keep first, remove all others (process from end to start)
                    for i, match in enumerate(reversed(matches[1:]), 1):
                        result_html = result_html[:match.start()] + result_html[match.end():]
                        print(f"[READING] 🗑️ Removed duplicate Questions 36-40 section #{len(matches)-i} at position {match.start()}")
                
                # Pattern 2: More flexible - catch any Questions 36-40 section
                questions_36_40_pattern2 = r'(<h3[^>]*>\s*<strong>Questions\s+36[–-]40</strong>\s*</h3>.*?<question-input[^>]*data-question-number="40"[^>]*>.*?</p>)'
                matches2 = list(re.finditer(questions_36_40_pattern2, result_html, re.DOTALL | re.IGNORECASE))
                if len(matches2) > 1:
                    print(f"[READING] 🔥 Found {len(matches2)} Questions 36-40 sections (pattern 2), removing {len(matches2)-1} duplicates")
                    for i, match in enumerate(reversed(matches2[1:]), 1):
                        result_html = result_html[:match.start()] + result_html[match.end():]
                        print(f"[READING] 🗑️ Removed duplicate Questions 36-40 section #{len(matches2)-i} at position {match.start()} (pattern 2)")
                
                # Final check: Count again
                section_36_40_count_after = len(re.findall(r'<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>', result_html, re.IGNORECASE))
                if section_36_40_count_after > 1:
                    print(f"[READING] ⚠️ CRITICAL: Still {section_36_40_count_after} Questions 36-40 headers after regex removal!")
                    # Ultra-aggressive: Remove by header position
                    header_pattern = r'(<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>)'
                    header_matches = list(re.finditer(header_pattern, result_html, re.IGNORECASE))
                    if len(header_matches) > 1:
                        # Remove all but first header and its content
                        for i, header_match in enumerate(header_matches[1:], 1):  # Skip first
                            header_start = header_match.start()
                            # Find end of this section
                            next_header = re.search(r'<h3[^>]*><strong>Questions\s+\d+[–-]\d+</strong></h3>', 
                                                   result_html[header_match.end():], re.IGNORECASE)
                            if next_header:
                                section_end = header_match.end() + next_header.start()
                            else:
                                # Find last question 40
                                q40_matches = list(re.finditer(r'<question-input[^>]*data-question-number="40"[^>]*>', 
                                                              result_html[header_match.end():], re.IGNORECASE))
                                if q40_matches:
                                    last_q40_pos = header_match.end() + q40_matches[-1].end()
                                    p_close = result_html.find('</p>', last_q40_pos)
                                    section_end = p_close + 4 if p_close != -1 else len(result_html)
                                else:
                                    section_end = len(result_html)
                            
                            result_html = result_html[:header_start] + result_html[section_end:]
                            print(f"[READING] 🗑️ ULTRA-AGGRESSIVE: Removed duplicate Questions 36-40 section #{i+1} (header-based)")
                else:
                    print(f"[READING] ✅ Questions 36-40 duplicate removal successful: {section_36_40_count_before} -> {section_36_40_count_after}")
            else:
                print(f"[READING] ✅ Only 1 Questions 36-40 section found - no duplicates")
            
            # STEP 4: Final verification - count remaining questions
            final_soup = BeautifulSoup(result_html, 'html.parser')
            final_questions = {}
            
            for tag in final_soup.find_all('question-input'):
                q_num = tag.get('data-question-number')
                if q_num:
                    q_num_int = int(q_num)
                    if q_num_int in final_questions:
                        print(f"[READING] ⚠️ WARNING: Q{q_num} still appears multiple times!")
                    else:
                        final_questions[q_num_int] = 1
            
            for tag in final_soup.find_all('drag-drop-sentence-input'):
                q_num = tag.get('data-question-number')
                if q_num:
                    q_num_int = int(q_num)
                    if q_num_int in final_questions:
                        print(f"[READING] ⚠️ WARNING: Q{q_num} still appears multiple times!")
                    else:
                        final_questions[q_num_int] = 1
            
            # Final count of Questions 36-40 sections
            final_section_36_40_count = len(re.findall(r'<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>', result_html, re.IGNORECASE))
            if final_section_36_40_count > 1:
                print(f"[READING] ❌ CRITICAL ERROR: Still {final_section_36_40_count} Questions 36-40 sections after all removal attempts!")
            else:
                print(f"[READING] ✅ Final verification: {len(final_questions)} unique questions, {final_section_36_40_count} Questions 36-40 section")
            
            return result_html
            
        except Exception as e:
            print(f"[READING] ❌ Error in nuclear duplicate removal: {e}")
            import traceback
            print(f"[READING] Traceback: {traceback.format_exc()}")
            return html_content
    
    def cleanup_duplicate_instruction_text(self, html_content):
        """Clean up duplicate instruction text that appears after table-tegs components"""
        if not html_content:
            return html_content
        
        try:
            print(f"[READING] 🧹 Cleaning up duplicate instruction text...")
            
            # Find all table-tegs components
            table_tegs_pattern = r'<table-tegs[^>]*></table-tegs>'
            matches = list(re.finditer(table_tegs_pattern, html_content, re.IGNORECASE | re.DOTALL))
            
            if not matches:
                print(f"[READING] ℹ️ No table-tegs components found")
                return html_content
            
            result_html = html_content
            
            # Process each table-tegs component from the end to avoid position shifting
            for match in reversed(matches):
                table_tegs_end = match.end()
                
                # Get the content after this table-tegs component
                after_table_tegs = result_html[table_tegs_end:]
                
                # Remove duplicate instruction text patterns that appear after table-tegs
                # Only remove if it's a standalone paragraph (not part of the component)
                duplicate_patterns = [
                    r'<p><em>Look at the following statements[^<]*and the list of[^<]*below\.</em></p>',
                    r'<p><em>Look at the following statements.*?and the list of.*?below\.</em></p>',
                ]
                
                after_cleaned = after_table_tegs
                for pattern in duplicate_patterns:
                    after_cleaned = re.sub(pattern, '', after_cleaned, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
                
                # Reconstruct the HTML
                result_html = result_html[:table_tegs_end] + after_cleaned
            
            # Additional cleanup: Remove any remaining duplicate instruction text that appears after table-tegs
            # Only remove standalone paragraphs, not text that's part of the component
            result_html = re.sub(
                r'</table-tegs>\s*<p><em>Look at the following statements[^<]*and the list of[^<]*below\.</em></p>',
                '</table-tegs>', 
                result_html, 
                flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
            )
            
            print(f"[READING] ✅ Duplicate instruction text cleanup complete")
            return result_html
            
        except Exception as e:
            print(f"[READING] ❌ Error cleaning up duplicate text: {e}")
            return html_content

    def has_multiple_consecutive_list_selections(self, html_content):
        """Check if there are multiple consecutive list selection questions"""
        # Look for multiple "Questions X and Y" patterns followed by "Choose TWO letters" or "Write the correct letters in boxes"
        question_pattern = r'<p><em><strong>Questions?\s+\d+\s+and\s+\d+</strong></em></p>'
        choose_pattern = r'Choose.*?TWO.*?letters.*?A-E'
        write_pattern = r'Write the correct letters in boxes'
        
        # Also look for questions with A-E options (even without explicit instructions)
        option_pattern = r'<p><strong>[A-Z]&nbsp;</strong>&nbsp;&nbsp;'
        
        question_matches = list(re.finditer(question_pattern, html_content, re.IGNORECASE))
        choose_matches = list(re.finditer(choose_pattern, html_content, re.IGNORECASE))
        write_matches = list(re.finditer(write_pattern, html_content, re.IGNORECASE))
        option_matches = list(re.finditer(option_pattern, html_content, re.IGNORECASE))
        
        # Check if we have multiple question sections with choose, write, or option patterns
        if len(question_matches) >= 2 and (len(choose_matches) >= 2 or len(write_matches) >= 2 or len(option_matches) >= 10):
            print(f"[READING] 🔍 Found {len(question_matches)} question sections and {len(choose_matches)} choose patterns and {len(write_matches)} write patterns")
            return True
        
        return False

    def process_multiple_list_selections(self, html_content):
        """Process multiple consecutive list selection questions"""
        print(f"[READING] 🔧 Processing multiple list selection questions...")
        
        from apps.reading.utils.list_selection_perfect import parse_list_selection
        
        # Clean corrupted HTML first
        cleaned_html = self.clean_corrupted_html(html_content)
        
        # Find all "Write the correct letters in boxes X and Y" patterns
        write_patterns = [
            r'<p><em>Write the correct letters in boxes\s+(\d+)\s+and\s+(\d+)\s+on your answer sheet\.</em></p>',
            r'Write the correct letters in boxes\s+(\d+)\s+and\s+(\d+)\s+on your answer sheet'
        ]
        
        write_matches = []
        for pattern in write_patterns:
            matches = list(re.finditer(pattern, cleaned_html, re.IGNORECASE))
            write_matches.extend(matches)
        
        # Also find questions without write instructions but with A-E options
        question_pattern = r'<p><em><strong>Questions?\s+(\d+)\s+and\s+(\d+)</strong></em></p>'
        question_matches = list(re.finditer(question_pattern, cleaned_html, re.IGNORECASE))
        
        # For questions without write instructions, check if they have A-E options
        for match in question_matches:
            start_q = int(match.group(1))
            end_q = int(match.group(2))
            
            # Check if this question range already has a write instruction
            has_write = any(int(w.group(1)) == start_q and int(w.group(2)) == end_q for w in write_matches)
            if not has_write:
                # Look for A-E options in the content after this question header
                start_pos = match.end()
                # Find the next question header or end of content
                next_question = re.search(r'<p><em><strong>Questions?', cleaned_html[start_pos:], re.IGNORECASE)
                if next_question:
                    end_pos = start_pos + next_question.start()
                else:
                    end_pos = len(cleaned_html)
                
                section_content = cleaned_html[start_pos:end_pos]
                
                # Check if this section has A-E options
                option_patterns = [
                    r'<p><strong>[A-Z]&nbsp;</strong>&nbsp;&nbsp;',
                    r'<p><strong>[A-Z]&nbsp;&nbsp;</strong>',
                    r'<p><strong>[A-Z]&nbsp;&nbsp;</strong>&nbsp;'
                ]
                
                option_matches = []
                for pattern in option_patterns:
                    matches = list(re.finditer(pattern, section_content, re.IGNORECASE))
                    option_matches.extend(matches)
                
                if len(option_matches) >= 5:  # At least 5 options (A-E)
                    # Create a fake write match for this question range
                    fake_match = type('obj', (object,), {
                        'group': lambda x: [str(start_q), str(end_q)][x-1],
                        'start': lambda: match.start(),
                        'end': lambda: match.end()
                    })
                    write_matches.append(fake_match)
        
        # Remove duplicates and sort by position
        write_matches = sorted(list(set(write_matches)), key=lambda x: x.start())
        
        # Filter out overlapping matches (keep only the first match for each question range)
        filtered_matches = []
        seen_ranges = set()
        for match in write_matches:
            start_q = int(match.group(1))
            end_q = int(match.group(2))
            range_key = (start_q, end_q)
            if range_key not in seen_ranges:
                filtered_matches.append(match)
                seen_ranges.add(range_key)
        
        write_matches = filtered_matches
        
        if not write_matches:
            print(f"[READING] ❌ No write instruction patterns found")
            return html_content
        
        print(f"[READING] 🔍 Found {len(write_matches)} write instruction patterns")
        
        # Process each write instruction section
        result_html = cleaned_html
        changes_made = False
        
        # Process sections in reverse order to avoid position shifting issues
        for i in reversed(range(len(write_matches))):
            match = write_matches[i]
            start_q = int(match.group(1))
            end_q = int(match.group(2))
            start_pos = match.start()
            
            # Find the end of this question section
            if i + 1 < len(write_matches):
                # Next question section starts here
                next_start = write_matches[i + 1].start()
                section_html = cleaned_html[start_pos:next_start]
            else:
                # This is the last section, go to the end
                section_html = cleaned_html[start_pos:]
            
            print(f"[READING] 🔧 Processing section Q{start_q}-{end_q}...")
            
            # Process this section with the list selection parser
            processed_section = parse_list_selection(section_html)
            
            if processed_section and processed_section != section_html:
                # Replace the section in the result
                if i + 1 < len(write_matches):
                    next_start = write_matches[i + 1].start()
                    result_html = result_html[:start_pos] + processed_section + result_html[next_start:]
                else:
                    result_html = result_html[:start_pos] + processed_section
                
                changes_made = True
                print(f"[READING] ✅ Section Q{start_q}-{end_q} processed successfully")
            else:
                print(f"[READING] ⚠️ Section Q{start_q}-{end_q} not processed (no changes or error)")
        
        if changes_made:
            print(f"[READING] ✅ Multiple list selection processing complete - CHANGES MADE")
        else:
            print(f"[READING] ⚠️ Multiple list selection processing complete - NO CHANGES")
        
        return result_html

    def clean_corrupted_html(self, html_content):
        """Clean corrupted HTML tags and remove duplicates"""
        # Fix common corrupted tags
        cleaned = html_content
        
        # Fix <l<p> -> <p>
        cleaned = re.sub(r'<l<p>', '<p>', cleaned)
        
        # Fix other common corruptions
        cleaned = re.sub(r'<l<', '<', cleaned)
        cleaned = re.sub(r'<l\s*<', '<', cleaned)
        
        # Fix specific corrupted patterns
        cleaned = re.sub(r'<st<p>', '<p>', cleaned)
        cleaned = re.sub(r'<st<', '<', cleaned)
        
        # Fix more complex corrupted patterns
        cleaned = re.sub(r'<st<p><em><strong>', '<p><em><strong>', cleaned)
        cleaned = re.sub(r'<st<em><strong>', '<em><strong>', cleaned)
        
        # Fix broken tags like "lett<p><em><strong>"
        cleaned = re.sub(r'lett<p><em><strong>', 'letters,&nbsp;<strong>', cleaned)
        cleaned = re.sub(r'lett<em><strong>', 'letters,&nbsp;<strong>', cleaned)
        
        # Fix specific corrupted pattern: "Choose&nbsp;<strong>TWO</strong>&nbsp;lett<p><em><strong>Questions"
        cleaned = re.sub(r'Choose&nbsp;<strong>TWO</strong>&nbsp;lett<p><em><strong>Questions', 
                        'Choose&nbsp;<strong>TWO</strong>&nbsp;letters,&nbsp;<strong>A-E</strong>.</em></p>\n\n<p><em><strong>Questions', 
                        cleaned)
        
        # Fix malformed content like "ers,&nbsp;<strong>A-E</strong>.</em></p>"
        cleaned = re.sub(r'ers,&nbsp;<strong>A-E</strong>\.</em></p>', '', cleaned)
        
        # Fix the specific corrupted pattern: "lett<p><em><strong>Questions"
        # Handle both \r\n and \n line endings
        cleaned = re.sub(r'lett<p><em><strong>Questions\s+\d+\s+and\s+\d+</strong></em></p>', 
                        'letters,&nbsp;<strong>A-E</strong>.</em></p>', cleaned)
        
        # Also handle the pattern with \r\n
        cleaned = re.sub(r'lett<p><em><strong>Questions\s+\d+\s+and\s+\d+</strong></em></p>\r?\n', 
                        'letters,&nbsp;<strong>A-E</strong>.</em></p>\r\n', cleaned)
        
        # Remove orphaned text fragments like "ers,&nbsp;<strong>A-E</strong>.</em></p>"
        cleaned = re.sub(r'ers,&nbsp;<strong>A-E</strong>\.</em></p>', '', cleaned)
        
        # Fix the specific pattern: "Choose&nbsp;<strong>TWO</strong>&nbsp;letters,&nbsp;<strong>Questions 23 and 24</strong></em></p>"
        cleaned = re.sub(r'Choose&nbsp;<strong>TWO</strong>&nbsp;letters,&nbsp;<strong>Questions\s+\d+\s+and\s+\d+</strong></em></p>', 
                        'Choose&nbsp;<strong>TWO</strong>&nbsp;letters,&nbsp;<strong>A-E</strong>.</em></p>', cleaned)
        
        # Fix incomplete "Choose&nbsp;<strong>TWO</strong>&nbsp;lett" patterns
        cleaned = re.sub(r'<p><em>Choose&nbsp;<strong>TWO</strong>&nbsp;lett\s*</p>', '', cleaned)
        
        # Fix malformed structure for Questions 25 and 26
        cleaned = re.sub(r'<p><em>Write the correct letters in boxes 25 and 26 on your answer sheet\.</em></p>\r?\n<p><em><strong>Questions 25 and 26</strong></em></p>', 
                        '<p><em><strong>Questions 25 and 26</strong></em></p>\r\n\r\n<p><em>Choose&nbsp;<strong>TWO</strong>&nbsp;letters,&nbsp;<strong>A-E</strong>.</em></p>\r\n\r\n<p><em>Write the correct letters in boxes 25 and 26 on your answer sheet.</em></p>', 
                        cleaned)
        
        # Remove duplicate question headers that appear in the middle of text
        # Pattern: "Questions X and Y" followed by "Choose" and then another "Questions X and Y"
        cleaned = re.sub(r'(<p><em><strong>Questions\s+\d+\s+and\s+\d+</strong></em></p>.*?<p><em>Choose.*?</p>.*?)(<p><em><strong>Questions\s+\d+\s+and\s+\d+</strong></em></p>)', 
                        r'\1', cleaned, flags=re.DOTALL)
        
        # Clean up extra whitespace and empty paragraphs
        cleaned = re.sub(r'<p>\s*</p>\s*<p>\s*</p>', '<p>&nbsp;</p>', cleaned)
        cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
        
        # Additional cleanup for the specific user case
        # Remove any remaining incomplete "Choose" patterns
        cleaned = re.sub(r'<p><em>Choose&nbsp;<strong>TWO</strong>&nbsp;lett\s*</p>', '', cleaned)
        
        # Fix any remaining broken patterns
        cleaned = re.sub(r'<p><em>Choose&nbsp;<strong>TWO</strong>&nbsp;lett\s*$', '', cleaned, flags=re.MULTILINE)
        
        # Remove any orphaned text that might remain
        cleaned = re.sub(r'ers,&nbsp;<strong>A-E</strong>\.</em></p>', '', cleaned)
        
        # Clean up any remaining incomplete patterns
        cleaned = re.sub(r'<p><em>Choose&nbsp;<strong>TWO</strong>&nbsp;lett\s*</p>', '', cleaned)
        
        return cleaned

    def cleanup_duplicate_sections(self, html_content):
        """Remove duplicate question sections and keep only the best version of each question"""
        if not html_content:
            return html_content
        
        print(f"[READING] 🧹 Cleaning up duplicate sections...")
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all question numbers and their positions
            question_pattern = r'data-question-number="(\d+)"'
            all_questions = {}
            
            # Find all question-input tags and their context
            question_inputs = soup.find_all(attrs={'data-question-number': True})
            
            for q_input in question_inputs:
                q_num = q_input.get('data-question-number')
                if not q_num:
                    continue
                
                q_num = int(q_num)
                
                # Find the paragraph containing this question
                parent_p = q_input.find_parent('p')
                if parent_p:
                    # Get full paragraph HTML with question text
                    p_html = str(parent_p)
                    
                    # Check if this is a better version (has question text, not just tag)
                    has_text = bool(parent_p.get_text(strip=True).replace(str(q_num), '').strip())
                    
                    if q_num not in all_questions:
                        all_questions[q_num] = {
                            'html': p_html,
                            'has_text': has_text,
                            'element': parent_p
                        }
                    else:
                        # Keep the version with more text
                        current_has_text = all_questions[q_num]['has_text']
                        if has_text and not current_has_text:
                            all_questions[q_num] = {
                                'html': p_html,
                                'has_text': has_text,
                                'element': parent_p
                            }
            
            # Remove duplicate "Questions X-Y" headers
            # Find all section headers
            section_header_pattern = r'<p[^>]*><strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong></p>'
            headers = list(re.finditer(section_header_pattern, html_content, re.IGNORECASE))
            
            # Keep only unique section headers (by range)
            seen_ranges = set()
            headers_to_remove = []
            
            for header in headers:
                start_q = int(header.group(1))
                end_q = int(header.group(2))
                range_key = f"{start_q}-{end_q}"
                
                if range_key in seen_ranges:
                    headers_to_remove.append(header)
                else:
                    seen_ranges.add(range_key)
            
            # Remove duplicate headers (from end to start to preserve positions)
            result_html = html_content
            for header in reversed(headers_to_remove):
                result_html = result_html[:header.start()] + result_html[header.end():]
                print(f"[READING] 🗑️ Removed duplicate header: Questions {header.group(1)}-{header.group(2)}")
            
            # ENHANCED: Remove duplicate question paragraphs and sections
            # Strategy: Keep the first complete version of each question, remove ALL duplicates
            soup = BeautifulSoup(result_html, 'html.parser')
            seen_question_nums = set()
            paragraphs_to_remove = []
            
            # First pass: identify all question paragraphs with their content signatures
            question_paragraphs = {}
            question_content_signatures = {}  # Track content to detect exact duplicates
            
            for p in soup.find_all('p'):
                # Check if this paragraph contains a question number
                strong_tags = p.find_all('strong')
                for strong in strong_tags:
                    strong_text = strong.get_text(strip=True)
                    # Check if it's a question number
                    if strong_text.replace('&nbsp;', '').replace('\u00a0', '').strip().isdigit():
                        q_num = int(strong_text.replace('&nbsp;', '').replace('\u00a0', '').strip())
                        
                        # Check if this paragraph has a question-input tag
                        has_input = bool(p.find(attrs={'data-question-number': str(q_num)}))
                        
                        # CRITICAL FIX: Also check for drag-drop-sentence-input and other question tags
                        has_any_input = has_input or bool(p.find(attrs={'data-question-number': str(q_num)})) or \
                                       bool(p.find('question-input', attrs={'data-question-number': str(q_num)})) or \
                                       bool(p.find('drag-drop-sentence-input', attrs={'data-question-number': str(q_num)})) or \
                                       bool(p.find('drag-drop-matching-sentence-endings'))
                        
                        p_text = p.get_text(strip=True)
                        # Check if this paragraph has actual question text (not just number and tag)
                        has_question_text = len(p_text.replace(str(q_num), '').strip()) > 10
                        
                        # Create content signature for duplicate detection
                        # Normalize text for comparison (remove extra spaces, normalize entities)
                        normalized_text = re.sub(r'\s+', ' ', p_text)
                        normalized_text = re.sub(r'&nbsp;', ' ', normalized_text)
                        normalized_text = normalized_text.strip()
                        content_signature = normalized_text.lower()
                        
                        # CRITICAL: Keep paragraphs with question-input tags OR paragraphs with question text
                        # This ensures we don't remove questions that haven't been processed yet
                        if has_any_input or has_question_text:
                            # Check if we've seen this exact content before (exact duplicate)
                            if q_num in question_content_signatures:
                                if content_signature in question_content_signatures[q_num]:
                                    # Exact duplicate - mark for removal
                                    paragraphs_to_remove.append(p)
                                    print(f"[READING] 🗑️ Marked exact duplicate paragraph for Q{q_num}")
                                    continue
                                else:
                                    # Same question number but different content - track it
                                    question_content_signatures[q_num].add(content_signature)
                            else:
                                question_content_signatures[q_num] = {content_signature}
                            
                            if q_num not in question_paragraphs:
                                question_paragraphs[q_num] = {
                                    'paragraph': p,
                                    'has_text': has_question_text,
                                    'has_input': has_any_input,
                                    'text_length': len(p_text),
                                    'position': len(question_paragraphs)  # Track order
                                }
                            else:
                                # Keep the version with input tag OR more text OR earlier position
                                current = question_paragraphs[q_num]
                                # Priority: has_input > has_text > text_length > position
                                should_replace = False
                                if has_any_input and not current['has_input']:
                                    should_replace = True
                                elif has_any_input == current['has_input']:
                                    if has_question_text and not current['has_text']:
                                        should_replace = True
                                    elif has_question_text == current['has_text']:
                                        if len(p_text) > current['text_length']:
                                            should_replace = True
                                        elif len(p_text) == current['text_length'] and current['position'] > question_paragraphs[q_num]['position']:
                                            # Same length, keep earlier one
                                            should_replace = False
                                
                                if should_replace:
                                    # Mark old one for removal
                                    paragraphs_to_remove.append(current['paragraph'])
                                    question_paragraphs[q_num] = {
                                        'paragraph': p,
                                        'has_text': has_question_text,
                                        'has_input': has_any_input,
                                        'text_length': len(p_text),
                                        'position': current['position']
                                    }
                                else:
                                    # Mark this one for removal
                                    paragraphs_to_remove.append(p)
                                    print(f"[READING] 🗑️ Marked duplicate paragraph for Q{q_num}")
            
            # CRITICAL: Before removing, check if we're removing questions that don't have input tags yet
            # This prevents removing questions that haven't been processed
            safe_paragraphs_to_remove = []
            for p in paragraphs_to_remove:
                p_text = p.get_text(strip=True)
                # Check if this paragraph contains a question number
                strong_tags = p.find_all('strong')
                has_question_num = False
                q_num = None
                
                for strong in strong_tags:
                    strong_text = strong.get_text(strip=True)
                    if strong_text.replace('&nbsp;', '').replace('\u00a0', '').strip().isdigit():
                        q_num = int(strong_text.replace('&nbsp;', '').replace('\u00a0', '').strip())
                        has_question_num = True
                        break
                
                # Only remove if:
                # 1. It doesn't have a question number, OR
                # 2. It has a question number BUT we have a better version in question_paragraphs
                if not has_question_num:
                    safe_paragraphs_to_remove.append(p)
                elif q_num in question_paragraphs:
                    # We have a better version, safe to remove
                    safe_paragraphs_to_remove.append(p)
                else:
                    # This is a question paragraph without input tag, but we don't have a better version
                    # DON'T remove it - it might be a question that hasn't been processed yet
                    print(f"[READING] ⚠️ Keeping Q{q_num} paragraph (no input tag but no better version found)")
            
            # Remove only safe paragraphs
            for p in safe_paragraphs_to_remove:
                p.decompose()
            
            # Remove duplicate "Questions X-Y" sections completely
            # Find sections that are completely duplicated
            result_html = str(soup)
            
            # ENHANCED: Pattern to match complete "Questions X-Y" sections including h3 headers
            section_patterns = [
                r'(<p[^>]*><strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong></p>.*?)(?=<p[^>]*><strong>Questions?\s+\d+[-–—&ndash;&mdash;]\d+</strong></p>|<h3[^>]*><strong>Questions?\s+\d+[-–—&ndash;&mdash;]\d+</strong></h3>|$)',
                r'(<h3[^>]*><strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong></h3>.*?)(?=<p[^>]*><strong>Questions?\s+\d+[-–—&ndash;&mdash;]\d+</strong></p>|<h3[^>]*><strong>Questions?\s+\d+[-–—&ndash;&mdash;]\d+</strong></h3>|$)',
            ]
            
            all_sections = []
            for pattern in section_patterns:
                sections = list(re.finditer(pattern, result_html, re.IGNORECASE | re.DOTALL))
                all_sections.extend(sections)
            
            # Sort sections by start position
            all_sections.sort(key=lambda x: x.start())
            
            seen_section_content = {}
            sections_to_remove = []
            
            for section in all_sections:
                section_content = section.group(1)
                # Normalize whitespace for comparison
                normalized = re.sub(r'\s+', ' ', section_content)
                normalized = re.sub(r'&nbsp;', ' ', normalized)
                normalized = re.sub(r'<[^>]+>', '', normalized)  # Remove HTML tags for comparison
                normalized = normalized.strip()
                
                # Extract question range
                start_q = section.group(2) if len(section.groups()) >= 2 else None
                end_q = section.group(3) if len(section.groups()) >= 3 else None
                range_key = f"{start_q}-{end_q}" if start_q and end_q else None
                
                # Check if we've seen this exact content before
                if normalized in seen_section_content:
                    # This is a duplicate - mark for removal
                    sections_to_remove.append(section)
                    print(f"[READING] 🗑️ Marked duplicate section: Questions {range_key}")
                else:
                    # First time seeing this content - keep it
                    seen_section_content[normalized] = {
                        'section': section,
                        'range': range_key,
                        'position': section.start()
                    }
            
            # Remove duplicate sections (from end to start to preserve positions)
            for section in reversed(sections_to_remove):
                result_html = result_html[:section.start()] + result_html[section.end():]
                print(f"[READING] 🗑️ Removed duplicate section at position {section.start()}")
            
            # Remove duplicate instruction paragraphs (Choose the correct letter, etc.)
            # Keep only the first occurrence of instruction paragraphs
            instruction_patterns = [
                r'<p><em>Choose the correct letter[^<]*</em></p>',
                r'<p><em>Write the correct letter[^<]*</em></p>',
                r'<p><em>Complete each sentence[^<]*</em></p>',
                r'<p><em>Do the following statements[^<]*</em></p>',
                r'<p><em>In boxes[^<]*</em></p>',
            ]
            
            seen_instructions = set()
            instruction_matches = []
            for pattern in instruction_patterns:
                matches = list(re.finditer(pattern, result_html, re.IGNORECASE | re.DOTALL))
                instruction_matches.extend(matches)
            
            # Sort by position (keep first occurrence)
            instruction_matches.sort(key=lambda x: x.start())
            
            for match in instruction_matches:
                # Normalize instruction text for comparison
                instruction_text = re.sub(r'\s+', ' ', match.group(0))
                instruction_text = re.sub(r'&nbsp;', ' ', instruction_text)
                instruction_text = re.sub(r'<[^>]+>', '', instruction_text)  # Remove HTML tags for comparison
                instruction_text = instruction_text.strip().lower()
                
                if instruction_text in seen_instructions:
                    # Duplicate - remove it
                    result_html = result_html[:match.start()] + result_html[match.end():]
                    print(f"[READING] 🗑️ Removed duplicate instruction paragraph: {instruction_text[:50]}...")
                else:
                    # First occurrence - keep it
                    seen_instructions.add(instruction_text)
            
            # CRITICAL: Remove drag-drop-matching-sentence-endings tags for Questions 27-30
            # These should be multiple choice, not matching sentence endings
            # Pattern to match drag-drop tags (including nested content)
            drag_drop_pattern = r'<drag-drop-matching-sentence-endings[^>]*>.*?</drag-drop-matching-sentence-endings>'
            drag_drop_matches = list(re.finditer(drag_drop_pattern, result_html, re.IGNORECASE | re.DOTALL))
            
            for match in reversed(drag_drop_matches):
                tag_content = match.group(0)
                # Check if this tag is BEFORE Questions 27-30 or contains Questions 27-30 context
                # Look for "Choose the correct letter, A, B, C or D" pattern nearby
                start_pos = match.start()
                end_pos = match.end()
                
                # Check context before and after the tag
                context_before = result_html[max(0, start_pos - 500):start_pos]
                context_after = result_html[end_pos:min(len(result_html), end_pos + 500)]
                full_context = context_before + tag_content + context_after
                
                # Check if Questions 27-30 is mentioned nearby
                has_questions_27_30 = bool(re.search(r'Questions?\s+27[–-]30', full_context, re.IGNORECASE))
                
                # Check if "Choose the correct letter, A, B, C or D" is present
                has_choose_letter_abcd = bool(re.search(
                    r'choose\s+the\s+correct\s+letter\s*[,:]\s*[A-Z]\s*,\s*[A-Z]\s*,\s*[A-Z]\s*(?:or|/)\s*[A-Z]',
                    full_context,
                    re.IGNORECASE
                ))
                
                # Check if tag contains Questions 31-35 (this should be kept)
                has_questions_31_35 = bool(re.search(r'Questions?\s+31[–-]35', tag_content, re.IGNORECASE))
                
                # Remove if it's Questions 27-30 context with "Choose the correct letter" but NOT Questions 31-35
                if (has_questions_27_30 or has_choose_letter_abcd) and not has_questions_31_35:
                    # This is Questions 27-30 with multiple choice format - remove the drag-drop tag
                    result_html = result_html[:match.start()] + result_html[match.end():]
                    print(f"[READING] 🗑️ Removed drag-drop-matching-sentence-endings tag for Questions 27-30 (should be multiple choice)")
            
            # FINAL PASS: Remove any remaining duplicate content blocks
            # This catches cases where entire question blocks are duplicated
            soup = BeautifulSoup(result_html, 'html.parser')
            
            # Find all paragraphs and check for duplicate question blocks
            all_paragraphs = soup.find_all('p')
            seen_blocks = {}
            blocks_to_remove = []
            
            # Group consecutive paragraphs that form a question block
            current_block = []
            current_block_start = None
            
            for i, p in enumerate(all_paragraphs):
                p_text = p.get_text(strip=True)
                p_html = str(p)
                
                # Check if this is a question paragraph (has question number or question-input tag)
                has_question = bool(re.search(r'data-question-number="(\d+)"', p_html)) or \
                              bool(re.search(r'<strong>\s*(\d+)\s*</strong>', p_html))
                
                # Also check for question numbers in drag-drop tags
                if not has_question:
                    has_question = bool(re.search(r'data-question-number="(\d+)"', p_html)) or \
                                  bool(p.find(attrs={'data-question-number': True}))
                
                if has_question:
                    if not current_block:
                        current_block_start = i
                    current_block.append(p)
                else:
                    # End of current block
                    if len(current_block) > 0:
                        # Create signature for this block
                        block_signature = ' '.join([p.get_text(strip=True) for p in current_block])
                        block_signature = re.sub(r'\s+', ' ', block_signature).strip().lower()
                        
                        if block_signature in seen_blocks:
                            # Duplicate block - mark for removal
                            blocks_to_remove.extend(current_block)
                            print(f"[READING] 🗑️ Marked duplicate question block (signature: {block_signature[:50]}...)")
                        else:
                            seen_blocks[block_signature] = current_block
                        
                        current_block = []
                        current_block_start = None
            
            # Handle last block if exists
            if len(current_block) > 0:
                block_signature = ' '.join([p.get_text(strip=True) for p in current_block])
                block_signature = re.sub(r'\s+', ' ', block_signature).strip().lower()
                
                if block_signature in seen_blocks:
                    blocks_to_remove.extend(current_block)
                    print(f"[READING] 🗑️ Marked duplicate question block (last block)")
            
            # Remove duplicate blocks
            for block_p in blocks_to_remove:
                if block_p and block_p.parent:
                    block_p.decompose()
            
            result_html = str(soup)
            
            # CRITICAL: Remove duplicate question-input tags for same question number
            # Find all question-input tags and keep only the first occurrence of each question number
            question_input_pattern = r'<question-input[^>]*data-question-number="(\d+)"[^>]*>'
            question_inputs = list(re.finditer(question_input_pattern, result_html, re.IGNORECASE))
            
            seen_question_numbers = {}
            duplicates_to_remove = []
            
            for match in question_inputs:
                q_num = match.group(1)
                tag_html = match.group(0)
                
                if q_num in seen_question_numbers:
                    # Duplicate question number - mark for removal
                    duplicates_to_remove.append(match)
                    print(f"[READING] 🗑️ Marked duplicate question-input tag for Q{q_num}")
                else:
                    # First occurrence - keep it
                    seen_question_numbers[q_num] = match
            
            # Remove duplicate question-input tags (from end to start to preserve positions)
            for match in reversed(duplicates_to_remove):
                result_html = result_html[:match.start()] + result_html[match.end():]
                print(f"[READING] 🗑️ Removed duplicate question-input tag at position {match.start()}")
            
            # Clean up extra whitespace and empty paragraphs
            result_html = re.sub(r'<p>\s*</p>\s*<p>\s*</p>', '<p>&nbsp;</p>', result_html)
            result_html = re.sub(r'\n\s*\n\s*\n+', '\n\n', result_html)
            
            # Final cleanup: Remove any remaining duplicate headers that might have been missed
            # Pattern for headers in various formats
            header_patterns = [
                r'(<p[^>]*><strong>Questions?\s+\d+[-–—&ndash;&mdash;]\d+</strong></p>)',
                r'(<h3[^>]*><strong>Questions?\s+\d+[-–—&ndash;&mdash;]\d+</strong></h3>)',
            ]
            
            seen_headers = set()
            for pattern in header_patterns:
                matches = list(re.finditer(pattern, result_html, re.IGNORECASE))
                for match in reversed(matches):
                    header_text = match.group(1)
                    normalized_header = re.sub(r'\s+', ' ', header_text).strip().lower()
                    
                    if normalized_header in seen_headers:
                        # Duplicate header - remove it
                        result_html = result_html[:match.start()] + result_html[match.end():]
                        print(f"[READING] 🗑️ Removed duplicate header")
                    else:
                        seen_headers.add(normalized_header)
            
            print(f"[READING] ✅ Cleanup complete - removed duplicates")
            return result_html
            
        except Exception as e:
            print(f"[READING] ⚠️ Cleanup error: {e}")
            import traceback
            print(f"[READING] Traceback: {traceback.format_exc()}")
            return html_content

    def reorder_sections_by_question_number(self, html_content):
        """Reorder sections by question number (27-30, 31-35, 36-40, etc.)"""
        if not html_content:
            return html_content
        
        print(f"[READING] 🔄 Reordering sections by question number...")
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all sections by looking for question ranges
            sections = []
            
            # Pattern 1: Find "Questions X-Y" headers in various formats
            header_patterns = [
                r'<p[^>]*><strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong></p>',
                r'<h3[^>]*><strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong></h3>',
                r'<h3[^>]*>.*?<strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong>.*?</h3>',
            ]
            
            # Find all question ranges and their positions
            question_ranges = []
            for pattern in header_patterns:
                for match in re.finditer(pattern, html_content, re.IGNORECASE):
                    start_q = int(match.group(1))
                    end_q = int(match.group(2))
                    question_ranges.append({
                        'start_q': start_q,
                        'end_q': end_q,
                        'header_pos': match.start(),
                        'header_end': match.end()
                    })
            
            # Also find drag-drop sections
            drag_drop_matches = list(re.finditer(r'<drag-drop-matching-sentence-endings[^>]*>', html_content, re.IGNORECASE))
            for match in drag_drop_matches:
                # Find the closing tag
                content_start = match.start()
                # Find closing tag
                remaining = html_content[content_start:]
                closing_match = re.search(r'</drag-drop-matching-sentence-endings>', remaining, re.IGNORECASE)
                if closing_match:
                    content_end = content_start + closing_match.end()
                    section_content = html_content[content_start:content_end]
                    
                    # Extract question numbers
                    q_nums = re.findall(r'data-question-number="(\d+)"', section_content)
                    if q_nums:
                        start_q = min(int(q) for q in q_nums)
                        end_q = max(int(q) for q in q_nums)
                        question_ranges.append({
                            'start_q': start_q,
                            'end_q': end_q,
                            'header_pos': content_start,
                            'header_end': content_end,
                            'is_drag_drop': True
                        })
            
            # Extract sections: from one header to the next (or end)
            question_ranges_sorted = sorted(question_ranges, key=lambda x: x['header_pos'])
            
            for i, range_info in enumerate(question_ranges_sorted):
                start_pos = range_info['header_pos']
                
                # Find end position (next section start or end of content)
                if i + 1 < len(question_ranges_sorted):
                    end_pos = question_ranges_sorted[i + 1]['header_pos']
                else:
                    end_pos = len(html_content)
                
                section_content = html_content[start_pos:end_pos]
                
                sections.append({
                    'start_q': range_info['start_q'],
                    'end_q': range_info['end_q'],
                    'content': section_content,
                    'position': start_pos
                })
                print(f"[READING] 📍 Found section {range_info['start_q']}-{range_info['end_q']} at position {start_pos}")
            
            # If no sections found, return original
            if not sections:
                print(f"[READING] ℹ️ No sections found to reorder")
                return html_content
            
            # Sort sections by start_question number
            sections_sorted = sorted(sections, key=lambda x: x['start_q'])
            section_ranges = [f"{s['start_q']}-{s['end_q']}" for s in sections_sorted]
            print(f"[READING] 📋 Sections will be reordered to: {section_ranges}")
            
            # Check if already in correct order
            if all(sections[i]['start_q'] == sections_sorted[i]['start_q'] for i in range(len(sections))):
                print(f"[READING] ✅ Sections already in correct order")
                return html_content
            
            # Extract content before first section
            first_section_pos = min(s['position'] for s in sections)
            content_before = html_content[:first_section_pos].rstrip()
            
            # Extract content after last section
            last_section = max(sections, key=lambda x: x['position'])
            last_section_end = last_section['position'] + len(last_section['content'])
            content_after = html_content[last_section_end:].lstrip()
            
            # Build new HTML with sections in correct order
            reordered_sections_html = '\n\n'.join(s['content'].strip() for s in sections_sorted)
            
            # Combine parts
            if content_before and content_after:
                result_html = content_before + '\n\n' + reordered_sections_html + '\n\n' + content_after
            elif content_before:
                result_html = content_before + '\n\n' + reordered_sections_html
            elif content_after:
                result_html = reordered_sections_html + '\n\n' + content_after
            else:
                result_html = reordered_sections_html
            
            print(f"[READING] ✅ Sections reordered successfully")
            return result_html
            
        except Exception as e:
            print(f"[READING] ⚠️ Reorder error: {e}")
            import traceback
            print(f"[READING] Traceback: {traceback.format_exc()}")
            return html_content

    def _is_course_worksheet_questions(self, html_content):
        """Numbered comprehension / quiz-item HTML must not go through IELTS parsers."""
        if not html_content:
            return False
        if re.search(r'class="quiz-item"|data-number=|quiz-list', html_content):
            return True
        if re.search(r'<question-input|drag-drop-|table-tegs|list-selection-tegs', html_content):
            return False
        if re.search(r'Questions?\s+\d+\s*[-–]\s*\d+', html_content, re.I):
            return False
        has_abcd = bool(re.search(r'(?:^|>)\s*[A-D]\)\s+', html_content))
        has_numbered = bool(re.search(r'(?:^|>)\s*\d+\.\s+\S', html_content)) or bool(
            re.search(r'<ol[\s>]', html_content, re.I)
        )
        return has_numbered and not has_abcd

    def save(self, *args, **kwargs):
        """ULTIMATE UNIVERSAL QUESTION PROCESSOR - PRESERVES ALL CONTENT"""
        print(f"[READING] 🚀 Processing Reading: {self.title or 'Untitled'}")

        if self.questions and self._is_course_worksheet_questions(self.questions):
            if not self.questions_raw:
                self.questions_raw = self.questions
            print("[READING] Course worksheet/comprehension — skip IELTS parser")
            super().save(*args, **kwargs)
            return
        
        if self.questions:
            # Store original questions before parsing (only if not already stored and questions are unparsed)
            if not self.questions_raw:
                # Check if questions have been parsed (contain question-input tags)
                has_parsed_tags = bool(re.search(r'<question-input|data-question-number=|drag-drop-|table-tegs|list-selection-tegs', self.questions))
                if not has_parsed_tags:
                    # Store original unparsed questions
                    self.questions_raw = self.questions
                    print(f"[READING] 💾 Stored original unparsed questions in questions_raw")
            
            original_questions = self.questions
            original_length = len(original_questions)
            print(f"[READING] 📏 Original questions length: {original_length} chars")
            
            # Count questions in original
            original_q_nums = set(re.findall(r'data-question-number="(\d+)"', original_questions))
            print(f"[READING] 📊 Original questions field contains: {sorted(original_q_nums)}")
            
            try:
                # Use the ultimate multi-type processor
                self.questions = self.process_multi_type_questions(self.questions)
                
                # Convert ALL multiple_choice types to multiple_choice_with_multiple_answer
                # This ensures ALL multiple choice questions use multiple_choice_with_multiple_answer
                conversion_patterns = [
                    (r'data-question-type="multiple_choice"', 'data-question-type="multiple_choice_with_multiple_answer"'),
                    (r'data-question-type="multiple_choice_with_single_answer"', 'data-question-type="multiple_choice_with_multiple_answer"'),
                ]
                
                total_converted = 0
                for old_pattern, new_replacement in conversion_patterns:
                    if re.search(old_pattern, self.questions):
                        count_before = len(re.findall(old_pattern, self.questions))
                        self.questions = re.sub(old_pattern, new_replacement, self.questions)
                        total_converted += count_before
                        print(f"[READING] 🔄 Converted {count_before} {old_pattern} to {new_replacement}")
                
                if total_converted > 0:
                    print(f"[READING] ✅ Total converted: {total_converted} multiple_choice types to multiple_choice_with_multiple_answer")
                
                # CRITICAL: Check for missing question-input tags before cleanup
                # Find all question numbers mentioned in HTML but without question-input tags
                all_mentioned_q_nums = set(re.findall(r'<strong>\s*(\d+)\s*</strong>', self.questions))
                all_processed_q_nums = set(re.findall(r'data-question-number="(\d+)"', self.questions))
                missing_q_nums = {int(q) for q in all_mentioned_q_nums if q.isdigit()} - {int(q) for q in all_processed_q_nums if q.isdigit()}
                
                if missing_q_nums:
                    print(f"[READING] ⚠️ Found {len(missing_q_nums)} questions without question-input tags: {sorted(missing_q_nums)}")
                    print(f"[READING] 🔧 Attempting to process missing questions...")
                    
                    # Try to process missing questions using multiple choice parser
                    for missing_q in sorted(missing_q_nums):
                        # Find the section containing this question
                        section_pattern = rf'<p[^>]*><strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong></p>'
                        sections = list(re.finditer(section_pattern, self.questions, re.IGNORECASE))
                        
                        for section in sections:
                            start_q = int(section.group(1))
                            end_q = int(section.group(2))
                            if start_q <= missing_q <= end_q:
                                # Extract section HTML
                                section_start = section.start()
                                # Find end of section (next section or end of content)
                                next_section = re.search(rf'<p[^>]*><strong>Questions?\s+\d+[-–—&ndash;&mdash;]\d+</strong></p>', 
                                                        self.questions[section.end():], re.IGNORECASE)
                                section_end = section.end() + next_section.start() if next_section else len(self.questions)
                                section_html = self.questions[section_start:section_end]
                                
                                # Try to process with multiple choice parser
                                try:
                                    from apps.reading.utils.multiple_choice_perfect import parse_multiple_choice
                                    processed_section = parse_multiple_choice(section_html)
                                    
                                    # Check if question was created
                                    if re.search(rf'data-question-number="{missing_q}"', processed_section):
                                        print(f"[READING] ✅ Successfully processed missing Q{missing_q}")
                                        self.questions = self.questions[:section_start] + processed_section + self.questions[section_end:]
                                        break
                                except Exception as e:
                                    print(f"[READING] ⚠️ Failed to process Q{missing_q}: {e}")
                
                # Clean up duplicate content and sections
                self.questions = self.cleanup_duplicate_sections(self.questions)
                
                # Reorder sections by question number (27-30, 31-35, 36-40)
                self.questions = self.reorder_sections_by_question_number(self.questions)
                
                # CRITICAL FINAL PASS: Remove duplicate Questions 36-40 sections - AGGRESSIVE
                print(f"[READING] 🔥 FINAL PASS: Removing duplicate Questions 36-40 sections...")
                questions_36_40_pattern = r'(<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>.*?<question-input[^>]*data-question-number="40"[^>]*>.*?</p>)'
                matches = list(re.finditer(questions_36_40_pattern, self.questions, re.DOTALL | re.IGNORECASE))
                
                if len(matches) > 1:
                    print(f"[READING] 🔥 Found {len(matches)} Questions 36-40 sections, removing {len(matches)-1} duplicates")
                    # Keep first, remove all others (process from end to start to preserve positions)
                    for match in reversed(matches[1:]):
                        self.questions = self.questions[:match.start()] + self.questions[match.end():]
                        print(f"[READING] 🗑️ Removed duplicate Questions 36-40 at position {match.start()}")
                
                # Also check for Questions 36-40 with newlines between
                questions_36_40_pattern2 = r'(<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>.*?<question-input[^>]*data-question-number="40"[^>]*>.*?</p>\s*)'
                matches2 = list(re.finditer(questions_36_40_pattern2, self.questions, re.DOTALL | re.IGNORECASE))
                if len(matches2) > 1:
                    print(f"[READING] 🔥 Found {len(matches2)} Questions 36-40 sections (pattern 2), removing {len(matches2)-1} duplicates")
                    for match in reversed(matches2[1:]):
                        self.questions = self.questions[:match.start()] + self.questions[match.end():]
                        print(f"[READING] 🗑️ Removed duplicate Questions 36-40 at position {match.start()} (pattern 2)")
                
                # Final check: Count Questions 36-40 headers
                section_36_40_count = len(re.findall(r'<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>', self.questions, re.IGNORECASE))
                if section_36_40_count > 1:
                    print(f"[READING] ⚠️ CRITICAL: Still found {section_36_40_count} Questions 36-40 headers after removal!")
                    # Ultra-aggressive: Remove all but first occurrence
                    pattern = r'(<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>)'
                    header_matches = list(re.finditer(pattern, self.questions, re.IGNORECASE))
                    if len(header_matches) > 1:
                        # Find the end of each section
                        for i, header_match in enumerate(header_matches[1:], 1):  # Skip first
                            header_start = header_match.start()
                            # Find end of this section (next Questions header or end)
                            next_header = re.search(r'<h3[^>]*><strong>Questions\s+\d+[–-]\d+</strong></h3>', 
                                                   self.questions[header_match.end():], re.IGNORECASE)
                            if next_header:
                                section_end = header_match.end() + next_header.start()
                            else:
                                # Find last question 40
                                last_q40 = list(re.finditer(r'<question-input[^>]*data-question-number="40"[^>]*>', 
                                                           self.questions[header_match.end():], re.IGNORECASE))
                                if last_q40:
                                    # Find the paragraph end
                                    q40_end = header_match.end() + last_q40[-1].end()
                                    # Find </p> after question 40
                                    p_end = self.questions.find('</p>', q40_end)
                                    section_end = p_end + 4 if p_end != -1 else len(self.questions)
                                else:
                                    section_end = len(self.questions)
                            
                            # Remove this duplicate section
                            self.questions = self.questions[:header_start] + self.questions[section_end:]
                            print(f"[READING] 🗑️ ULTRA-AGGRESSIVE: Removed duplicate Questions 36-40 section #{i+1} (header-based)")
                else:
                    print(f"[READING] ✅ FINAL PASS: Only 1 Questions 36-40 section found - OK")
                
                # CRITICAL: Verify we didn't lose any content
                final_length = len(self.questions)
                final_q_nums = set(re.findall(r'data-question-number="(\d+)"', self.questions))
                print(f"[READING] 📏 Final questions length: {final_length} chars")
                print(f"[READING] 📊 Final questions field contains: {sorted(final_q_nums)}")
                
                # Check if we lost any questions
                lost_questions = original_q_nums - final_q_nums
                if lost_questions:
                    print(f"[READING] ⚠️ WARNING: Lost questions during processing: {sorted(lost_questions)}")
                    print(f"[READING] 🔧 Attempting to recover lost questions from original...")
                    
                    # Try to recover from original
                    for lost_q in sorted(lost_questions):
                        # Find the question in original
                        lost_pattern = rf'<p[^>]*>.*?<strong>\s*{lost_q}\s*</strong>.*?</p>'
                        lost_match = re.search(lost_pattern, original_questions, re.DOTALL | re.IGNORECASE)
                        if lost_match and lost_q not in final_q_nums:
                            # Check if it has question-input tag
                            if re.search(rf'data-question-number="{lost_q}"', lost_match.group(0)):
                                # Append to questions
                                self.questions += "\n\n" + lost_match.group(0)
                                print(f"[READING] ✅ Recovered Q{lost_q} from original")
                    
                    # Re-check after recovery
                    final_q_nums = set(re.findall(r'data-question-number="(\d+)"', self.questions))
                    lost_questions = original_q_nums - final_q_nums
                    
                    if lost_questions:
                        print(f"[READING] ⚠️ Still missing questions: {sorted(lost_questions)}")
                        print(f"[READING] 🔧 Restoring original questions to prevent data loss...")
                        self.questions = original_questions
                elif self.questions != original_questions:
                    print(f"[READING] ✅ SUCCESS: Questions processed successfully - all questions preserved")
                else:
                    print(f"[READING] ⚠️ No changes made")
                    
            except Exception as e:
                print(f"[READING] 💥 ERROR: {str(e)}")
                import traceback
                print(f"[READING] Full traceback: {traceback.format_exc()}")
                print(f"[READING] 🔧 Restoring original questions due to error...")
                self.questions = original_questions
        
        # Process content for matching headings
        if self.content:
            try:
                processed_content = self.content.replace('&nbsp;', ' ')
                pattern = r'([A-Za-z])\s*\((\d+)-matching_headings\)\s*'
                
                def replace_matching_headings_func(match):
                    paragraph_letter = match.group(1)
                    question_number = match.group(2)
                    return f'{paragraph_letter}&lt;question-input data-question-type="matching_headings" data-question-number="{question_number}"&gt;&lt;/question-input&gt;'
                
                self.content = re.sub(pattern, replace_matching_headings_func, processed_content, flags=re.DOTALL)
                print(f"[READING] Content processed for matching headings")
                
            except Exception as e:
                print(f"[READING] Content processing error: {str(e)}")
        
        # FINAL FINAL CHECK: Ensure Questions 36-40 is NEVER duplicated before saving
        if self.questions:
            print(f"[READING] 🔥 FINAL FINAL CHECK: Verifying Questions 36-40 is not duplicated...")
            section_36_40_count = len(re.findall(r'<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>', self.questions, re.IGNORECASE))
            if section_36_40_count > 1:
                print(f"[READING] ❌ CRITICAL: Found {section_36_40_count} Questions 36-40 sections RIGHT BEFORE SAVE!")
                # Last resort: Remove all but first using ultra-aggressive method
                pattern = r'(<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>.*?<question-input[^>]*data-question-number="40"[^>]*>.*?</p>)'
                matches = list(re.finditer(pattern, self.questions, re.DOTALL | re.IGNORECASE))
                if len(matches) > 1:
                    print(f"[READING] 🔥 LAST RESORT: Removing {len(matches)-1} duplicate Questions 36-40 sections")
                    for match in reversed(matches[1:]):  # Keep first, remove rest
                        self.questions = self.questions[:match.start()] + self.questions[match.end():]
                        print(f"[READING] 🗑️ LAST RESORT: Removed duplicate Questions 36-40 at position {match.start()}")
                
                # Verify again
                final_count = len(re.findall(r'<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>', self.questions, re.IGNORECASE))
                if final_count > 1:
                    print(f"[READING] ❌❌❌ CRITICAL ERROR: Still {final_count} Questions 36-40 sections after LAST RESORT removal!")
                    # Emergency: Remove by finding all headers and keeping only first
                    header_pattern = r'(<h3[^>]*><strong>Questions\s+36[–-]40</strong></h3>)'
                    header_matches = list(re.finditer(header_pattern, self.questions, re.IGNORECASE))
                    if len(header_matches) > 1:
                        for header_match in reversed(header_matches[1:]):
                            # Find section end
                            next_header = re.search(r'<h3[^>]*><strong>Questions\s+\d+[–-]\d+</strong></h3>', 
                                                   self.questions[header_match.end():], re.IGNORECASE)
                            if next_header:
                                section_end = header_match.end() + next_header.start()
                            else:
                                # Find last </p> after question 40
                                q40_pos = self.questions.find('data-question-number="40"', header_match.end())
                                if q40_pos != -1:
                                    p_close = self.questions.find('</p>', q40_pos)
                                    section_end = p_close + 4 if p_close != -1 else len(self.questions)
                                else:
                                    section_end = len(self.questions)
                            
                            self.questions = self.questions[:header_match.start()] + self.questions[section_end:]
                            print(f"[READING] 🗑️ EMERGENCY: Removed duplicate Questions 36-40 section")
                else:
                    print(f"[READING] ✅ LAST RESORT successful: Questions 36-40 count reduced to {final_count}")
            else:
                print(f"[READING] ✅ FINAL CHECK: Only {section_36_40_count} Questions 36-40 section - OK")
        
        super().save(*args, **kwargs)
        print(f"[READING] 💾 Saved successfully with ID: {self.id}")
        
        # Print the questions field content to terminal - FULL DETAILED OUTPUT
        if self.questions:
            print(f"\n{'=' * 100}")
            print(f"[READING] 📄 ========== SAVED QUESTIONS FIELD CONTENT ==========")
            print(f"{'=' * 100}")
            print(f"[READING] 📏 Questions field length: {len(self.questions)} chars")
            
            # Extract all question numbers
            question_numbers = sorted(set(re.findall(r'data-question-number="(\d+)"', self.questions)))
            print(f"[READING] 📋 Questions found: {question_numbers}")
            print(f"[READING] 📊 Total questions: {len(question_numbers)}")
            
            # Extract question types
            question_types = set(re.findall(r'data-question-type="([^"]+)"', self.questions))
            print(f"[READING] 🔧 Question types found: {sorted(question_types)}")
            
            # Count each type
            for q_type in sorted(question_types):
                count = len(re.findall(rf'data-question-type="{re.escape(q_type)}"', self.questions))
                print(f"[READING]   - {q_type}: {count}")
            
            print(f"\n[READING] 📝 ========== FULL QUESTIONS FIELD CONTENT ==========")
            print(f"{'=' * 100}")
            print(self.questions)
            print(f"{'=' * 100}")
            print(f"[READING] 📄 ========== END OF QUESTIONS FIELD ==========")
            print(f"{'=' * 100}\n")



class ReadingAnswer(models.Model):
    reading = models.ForeignKey(
        Reading,
        on_delete=models.CASCADE,
        related_name='answers',
        related_query_name='answer'
    )
    question_number = models.PositiveIntegerField(verbose_name="Question Number", default=1)
    question = models.TextField(
        verbose_name="Question",
        blank=True,
        default="",
        help_text="Write the question. For MCQ put options on new lines, e.g. A) ... B) ... C) ... D) ...",
    )
    true_answer = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Correct Answer's with (;)",
        help_text="MCQ: A. Open-ended: key phrases separated by ; . Personal/opinion: leave empty or write OPINION.",
    )
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ['reading', 'question_number']
        unique_together = ('reading', 'question_number')
        verbose_name = 'Reading Question'
        verbose_name_plural = 'Reading Questions'
    
    def __str__(self):
        return f"Question {self.question_number}"
   
class ReadingUserAnswer(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='reading_user_answers')
    reading = models.ForeignKey(Reading, on_delete=models.CASCADE, related_name='user_answers') 
    question_number = models.PositiveIntegerField()
    answer = models.CharField(max_length=200, null=True, blank=True, verbose_name="User Answer")
    is_true = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'reading', 'question_number')
        verbose_name = 'Reading Answer'
        verbose_name_plural = 'Reading Answers'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        try:
            correct_answer_obj = ReadingAnswer.objects.get(
                reading=self.reading,
                question_number=self.question_number
            )
            raw_true_answer = (correct_answer_obj.true_answer or "").strip()
            if raw_true_answer.upper() in ("", "OPINION", "OPEN", "-"):
                self.is_true = False
            elif correct_answer_obj.true_answer is not None:
                # Normalize user answer: remove extra spaces, convert to lowercase
                user_answer = re.sub(r'\s+', ' ', (self.answer or '').strip().lower())
                valid_answers = []
                
                for answer in raw_true_answer.split(';'):
                    # Normalize each valid answer the same way
                    normalized_answer = re.sub(r'\s+', ' ', answer.strip().lower())
                    if normalized_answer:
                        valid_answers.append(normalized_answer)
                
                self.is_true = user_answer in valid_answers
                # Open-ended: accept if a key phrase (8+ chars) appears in the student answer
                if not self.is_true and user_answer:
                    for va in valid_answers:
                        if len(va) >= 8 and va in user_answer:
                            self.is_true = True
                            break
            else:
                self.is_true = False
        except ReadingAnswer.DoesNotExist:
            self.is_true = False
        super().save(*args, **kwargs)

