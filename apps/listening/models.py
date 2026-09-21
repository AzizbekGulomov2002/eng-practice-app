from bs4 import BeautifulSoup
from django.db import models
from ckeditor.fields import RichTextField
import re
from apps.app.models import Users
from apps.listening.utils.completion_parser import parse_completion_questions
from apps.listening.utils.matching_parser import parse_matching_headings, parse_matching_information, parse_matching_sentence_endings
from apps.listening.utils.multiple_choice_perfect import parse_multiple_choice
from apps.listening.utils.true_false_parser import parse_true_false_questions
from apps.listening.utils.list_selection_perfect import parse_list_selection
from apps.listening.utils.labelling_parser import parse_labelling_questions
from apps.listening.utils.label_table import convert_to_label_table, detect_label_table

class ListeningMaterial(models.Model):
    test_material = models.ForeignKey("app.TestMaterial", on_delete=models.CASCADE,related_name="listening_materials")
    title = models.CharField(max_length=200, null=True,blank=True)
    answer_time = models.PositiveIntegerField(default=3600, verbose_name="Answer Time (seconds)", help_text="Answer time (seconds)")

    def __str__(self):
        return f"{self.title if self.title else self.test_material.test.title}"

class Listening(models.Model):
    LISTENING_CHOICES = (
        (1, 'Part 1'),
        (2, 'Part 2'),
        (3, 'Part 3'),
        (4, 'Part 4'),
    )
    
    listening_material = models.ForeignKey(ListeningMaterial, on_delete=models.CASCADE, related_name='listening_sections')
    questions = RichTextField(blank=True)
    questions_raw = RichTextField(verbose_name="Original Questions (Unparsed)", blank=True, null=True, help_text="Stores original questions before parsing")
    title = models.CharField(null=True, blank=True, max_length=200)
    audio = models.FileField(upload_to='listening_audios/', null=True, blank=True)
    audioscript = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_script = models.BooleanField(
        default=False,
        verbose_name="Show transcript",
        help_text="If enabled, the audio transcript is shown on the left side of the student exam.",
    )
    listening_section = models.IntegerField(choices=LISTENING_CHOICES)

    class Meta:
        verbose_name = 'Listenings'
        verbose_name_plural = 'Listenings'
        unique_together = ('listening_material', 'listening_section') 
        
    def __str__(self):
        return f"Listening Section {self.listening_section} for {self.listening_material}"
    
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
            r'<table-tegs[^>]*data-question-type="([^"]*)"[^>]*>',  # NEW - for specific table names
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
            print(f"[LISTENING] 🔍 Looking for drag-drop-matching-sentence-endings tags...")
            matches = list(re.finditer(r'<drag-drop-matching-sentence-endings[^>]*data-question-type="([^"]*)"[^>]*>', html_content))
            print(f"[LISTENING] Found {len(matches)} drag-drop-matching-sentence-endings tags")
            
            for m in matches:
                qtype = m.group(1)
                print(f"[LISTENING] Found drag-drop tag with type: {qtype}")
                # Find all question numbers within this tag
                tag_content = m.group(0)
                print(f"[LISTENING] Tag content: {tag_content[:200]}...")
                for num_match in re.finditer(r'data-question-number="(\d+)"', tag_content):
                    try:
                        question_number = int(num_match.group(1))
                        existing_tags[question_number] = qtype
                        print(f"[LISTENING] Added question {question_number} with type {qtype}")
                    except Exception as e:
                        print(f"[LISTENING] Error processing question number: {e}")
                        continue
        except Exception as e:
            print(f"[LISTENING] Error in drag-drop detection: {e}")
            pass
            
        print(f"[LISTENING] 🏷️ Found {len(existing_tags)} existing question-input tags: {existing_tags}")
        return existing_tags

    def split_question_sections(self, html_content):
        """ENHANCED section splitting - detects ALL header formats"""
        print(f"[LISTENING] 🔪 ENHANCED: Splitting content into question sections...")
        
        # COMPREHENSIVE patterns for ALL possible header formats
        header_patterns = [
            # Pattern 0: NEW - p tags with Questions X-Y followed by <br /> (MOST COMMON FORMAT)
            r'<p[^>]*>Questions?\s+(\d+)\s*[-–]\s*(\d+)\s*<br\s*/?>',
            r'<p[^>]*>Questions?\s+(\d+)\s*[-–]\s*(\d+)\s*<br\s+/>',
            r'<p[^>]*>Questions?\s+(\d+)\s*[-–]\s*(\d+)\s*<br>',
            # Pattern 0b: With strong tags and <br />
            r'<p[^>]*><strong>Questions?\s+(\d+)\s*[-–]\s*(\d+)</strong>\s*<br\s*/?>',
            r'<p[^>]*><strong>Questions?\s+(\d+)\s*[-–]\s*(\d+)</strong>\s*<br\s+/>',
            r'<p[^>]*><strong>Questions?\s+(\d+)\s*[-–]\s*(\d+)</strong>\s*<br>',
            # Pattern 0c: Simple text pattern - Questions X-Y anywhere (fallback)
            r'Questions?\s+(\d+)\s*[-–]\s*(\d+)(?:\s*<br|</p>|$)',
            
            # Pattern 1: h4 tags with &amp;ndash; entity
            r'&lt;h4[^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)&amp;ndash;(\d+)&lt;/strong&gt;&lt;/h4&gt;',
            
            # Pattern 2: h4 tags with regular dash (with optional spaces)
            r'&lt;h4[^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)\s*[-–—]\s*(\d+)&lt;/strong&gt;&lt;/h4&gt;',
            
            # Pattern 2b: p tags with strong Questions X - Y (with spaces around dash)
            r'&lt;p[^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)\s*[-–—]\s*(\d+)&lt;/strong&gt;&lt;/p&gt;',
            
            # Pattern 3: Any h tag with &amp;ndash; entity
            r'&lt;h[1-6][^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)&amp;ndash;(\d+)&lt;/strong&gt;&lt;/h[1-6]&gt;',
            
            # Pattern 4: Any h tag with any dash type
            r'&lt;h[1-6][^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)[-–—&amp;mdash;](\d+)&lt;/strong&gt;&lt;/h[1-6]&gt;',
            
            # Pattern 5: h tag with em and strong - FOR YOUR CASE
            r'&lt;h[1-6][^&gt;]*&gt;&lt;em&gt;&lt;strong&gt;Questions?\s+(\d+)[-–—&amp;ndash;&amp;mdash;](\d+)&lt;/strong&gt;&lt;/em&gt;&lt;/h[1-6]&gt;',
            
            # Pattern 6: Strong tags without h wrapper
            r'&lt;strong&gt;Questions?\s+(\d+)&amp;ndash;(\d+)&lt;/strong&gt;',
            r'&lt;strong&gt;Questions?\s+(\d+)[-–—](\d+)&lt;/strong&gt;',
            
            # Pattern 7: p tags with strong
            r'&lt;p[^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)[-–—&amp;ndash;&amp;mdash;](\d+)&lt;/strong&gt;',
            
            # Pattern 8: Simple strong with space
            r'&lt;p[^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)[-–—&amp;ndash;&amp;mdash;](\d+)\s*&lt;/strong&gt;',
            
            # Non-encoded versions
            r'<h4[^>]*><strong>Questions?\s+(\d+)&ndash;(\d+)</strong></h4>',
            r'<h4[^>]*><strong>Questions?\s+(\d+)\s*[-–—]\s*(\d+)</strong></h4>',
            r'<p[^>]*><strong>Questions?\s+(\d+)\s*[-–—]\s*(\d+)</strong></p>',
            r'<h[1-6][^>]*><strong>Questions?\s+(\d+)&ndash;(\d+)</strong></h[1-6]>',
            r'<h[1-6][^>]*><strong>Questions?\s+(\d+)[-–—&mdash;](\d+)</strong></h[1-6]>',
            r'<h[1-6][^>]*><em><strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong></em></h[1-6]>',
            r'<strong>Questions?\s+(\d+)&ndash;(\d+)</strong>',
            r'<strong>Questions?\s+(\d+)[-–—](\d+)</strong>',
            r'<p[^>]*><strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong>',
            r'<p[^>]*><strong>Questions?\s+(\d+)&ndash;(\d+)</strong></p>',
            
            # Additional patterns for HTML entities
            r'<h4[^>]*><strong>Questions?\s+(\d+)\s*&ndash;\s*(\d+)</strong></h4>',
            r'<h4[^>]*><strong>Questions?\s+(\d+)\s*&amp;ndash;\s*(\d+)</strong></h4>',
            r'<h[1-6][^>]*><strong>Questions?\s+(\d+)\s*&ndash;\s*(\d+)</strong></h[1-6]>',
            r'<h[1-6][^>]*><strong>Questions?\s+(\d+)\s*&amp;ndash;\s*(\d+)</strong></h[1-6]>',
            r'<strong>Questions?\s+(\d+)\s*&ndash;\s*(\d+)</strong>',
            r'<strong>Questions?\s+(\d+)\s*&amp;ndash;\s*(\d+)</strong>',
            
            # Patterns for "Questions X and Y" format
            r'<p[^>]*>Questions?\s+(\d+)\s+and\s+(\d+)\s*<br\s*/?>',  # NEW - with <br />
            r'<p[^>]*><strong>Questions?\s+(\d+)\s+and\s+(\d+)</strong></p>',
            r'<p[^>]*><strong>Questions?\s+(\d+)\s+and\s+(\d+)</strong>\s*<br\s*/?>',  # NEW - strong with <br />
            r'<strong>Questions?\s+(\d+)\s+and\s+(\d+)</strong>',
            r'<h[1-6][^>]*><strong>Questions?\s+(\d+)\s+and\s+(\d+)</strong></h[1-6]>',
            r'<h[1-6][^>]*><em><strong>Questions?\s+(\d+)\s+and\s+(\d+)</strong></em></h[1-6]>',
            r'<p[^>]*><em><strong>Questions?\s+(\d+)\s+and\s+(\d+)</strong></em></p>',
            r'<em><strong>Questions?\s+(\d+)\s+and\s+(\d+)</strong></em>',
            
            # HTML encoded versions for "Questions X and Y"
            r'&lt;p[^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)\s+and\s+(\d+)&lt;/strong&gt;&lt;/p&gt;',
            r'&lt;strong&gt;Questions?\s+(\d+)\s+and\s+(\d+)&lt;/strong&gt;',
            r'&lt;h[1-6][^&gt;]*&gt;&lt;strong&gt;Questions?\s+(\d+)\s+and\s+(\d+)&lt;/strong&gt;&lt;/h[1-6]&gt;',
            r'&lt;h[1-6][^&gt;]*&gt;&lt;em&gt;&lt;strong&gt;Questions?\s+(\d+)\s+and\s+(\d+)&lt;/strong&gt;&lt;/em&gt;&lt;/h[1-6]&gt;',
            r'&lt;p[^&gt;]*&gt;&lt;em&gt;&lt;strong&gt;Questions?\s+(\d+)\s+and\s+(\d+)&lt;/strong&gt;&lt;/em&gt;&lt;/p&gt;',
            r'&lt;em&gt;&lt;strong&gt;Questions?\s+(\d+)\s+and\s+(\d+)&lt;/strong&gt;&lt;/em&gt;',
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
                print(f"[LISTENING] 🎯 Pattern {i+1} found: Questions {start_num}-{end_num} at position {match.start()}")
            
            if matches:
                print(f"[LISTENING] ✅ Pattern {i+1} successful: {len(matches)} matches")
        
        # Remove duplicates (same position) and sort by position
        unique_matches = []
        seen_positions = set()
        
        for match in all_matches:
            pos_key = (match['start_pos'], match['end_pos'])
            if pos_key not in seen_positions:
                unique_matches.append(match)
                seen_positions.add(pos_key)
        
        unique_matches.sort(key=lambda x: x['start_pos'])
        
        print(f"[LISTENING] 📊 Total unique sections found: {len(unique_matches)}")
        
        # Create sections from matches
        for i, match in enumerate(unique_matches):
            section_start = match['start_pos']
            section_end = unique_matches[i + 1]['start_pos'] if i + 1 < len(unique_matches) else len(html_content)
            
            section_html = html_content[section_start:section_end]
            
            sections.append({
                'start_question': match['start_num'],
                'end_question': match['end_num'],
                'html': section_html,
                'range': f"{match['start_num']}-{match['end_num']}"
            })
            
            print(f"[LISTENING] 📋 Section {i+1}: Questions {sections[-1]['range']} ({len(section_html)} chars)")
        
        # If no sections found, try a more lenient approach
        if not sections:
            # Try to find "Questions X-Y" patterns in plain text
            simple_patterns = [
                r'Questions?\s+(\d+)\s*[-–]\s*(\d+)',
                r'Questions?\s+(\d+)\s+and\s+(\d+)',
            ]
            
            for pattern in simple_patterns:
                matches = list(re.finditer(pattern, html_content, re.IGNORECASE))
                if matches:
                    print(f"[LISTENING] 🔍 Found {len(matches)} sections using simple pattern: {pattern}")
                    for i, match in enumerate(matches):
                        start_num = int(match.group(1))
                        end_num = int(match.group(2))
                        section_start = match.start()
                        section_end = matches[i + 1].start() if i + 1 < len(matches) else len(html_content)
                        section_html = html_content[section_start:section_end]
                        
                        sections.append({
                            'start_question': start_num,
                            'end_question': end_num,
                            'html': section_html,
                            'range': f"{start_num}-{end_num}"
                        })
                        print(f"[LISTENING] 📋 Section {len(sections)}: Questions {start_num}-{end_num} ({len(section_html)} chars)")
                    break
        
        # If still no sections found, treat entire content as one section
        if not sections:
            sections.append({
                'start_question': 1,
                'end_question': 999,
                'html': html_content,
                'range': 'all'
            })
            print(f"[LISTENING] 📋 No sections found, treating as single section")
        
        return sections

    def get_unprocessed_questions_in_section(self, section_html, existing_tags, start_q, end_q):
        """ENHANCED question detection - handles ALL formats"""
        unprocessed = []
        found_questions = set()
        
        print(f"[LISTENING] 🔍 Enhanced question detection for range {start_q}-{end_q}")
        
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
                    print(f"[LISTENING] 📍 Found INLINE completion Q{q_num}")
        
        # PRIORITY 2: Traditional question patterns
        traditional_patterns = [
            # HTML encoded patterns
            r'&lt;p[^&gt;]*&gt;&lt;strong&gt;(\d+)&lt;/strong&gt;',
            r'&lt;strong&gt;(\d+)&lt;/strong&gt;',
            r'&lt;td[^&gt;]*&gt;[^&lt;]*&lt;strong&gt;(\d+)&lt;/strong&gt;',
            r'&lt;h[1-6][^&gt;]*&gt;&lt;strong&gt;(\d+)&lt;/strong&gt;',
            r'&lt;p[^&gt;]*list-style-type:decimal[^&gt;]*&gt;.*?(\d+)\.',
            r'&lt;span[^&gt;]*&gt;(\d+)\.\s*[A-Z]',
            
            # Special pattern for split Q20 - MUST BE FIRST to avoid conflicts
            r'<strong>\s*2\s*</strong>\s*<strong>\s*0\s*</strong>',
            # Non-encoded patterns
            r'<p[^>]*><strong>(\d+)</strong>',
            r'<strong>(\d+)</strong>',
            r'<td[^>]*>[^<]*<strong>(\d+)</strong>',
            r'<h[1-6][^>]*><strong>(\d+)</strong>',
            r'<p[^>]*list-style-type:decimal[^>]*>.*?(\d+)\.',
            r'<span[^>]*>(\d+)\.\s*[A-Z]',
        ]
        
        for i, pattern in enumerate(traditional_patterns):
            matches = re.finditer(pattern, section_html, re.DOTALL)
            for match in matches:
                # Special handling for Q20 split pattern 
                if '<strong>\\s*2\\s*</strong>' in pattern:
                    # This is the Q20 split pattern
                    q_num = 20
                    if start_q <= q_num <= end_q:
                        found_questions.add(q_num)
                        print(f"[LISTENING] 📍 Found TRADITIONAL Q{q_num} (split format)")
                else:
                    # Regular pattern with capture group
                    try:
                        q_num = int(match.group(1))
                        if start_q <= q_num <= end_q:
                            found_questions.add(q_num)
                            print(f"[LISTENING] 📍 Found TRADITIONAL Q{q_num}")
                    except (ValueError, IndexError):
                        continue
        
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
                                print(f"[LISTENING] 📍 Found SIMPLE Q{q_num}")
                    except ValueError:
                        continue
        
        # Filter out questions that already have tags
        for q_num in found_questions:
            if q_num not in existing_tags:
                unprocessed.append(q_num)
        
        print(f"[LISTENING] Section {start_q}-{end_q}: Found {len(found_questions)} questions, {len(unprocessed)} unprocessed: {sorted(unprocessed)}")
        return sorted(unprocessed)

    def analyze_section_type(self, section_html, question_range, unprocessed_questions):
        """COMPLETE FIXED: Enhanced section analysis with ALL question types"""
        if not unprocessed_questions:
            print(f"[LISTENING] ⏭️ Section {question_range}: All questions already processed")
            return {'skip': True}
            
        soup = BeautifulSoup(section_html, 'html.parser')
        plain_text = soup.get_text(separator=' ', strip=True).lower()
        content_text = plain_text
        
        print(f"[LISTENING] 🧠 ANALYZING section {question_range} for questions: {unprocessed_questions}")
        print(f"[LISTENING] 📝 Section content preview: {plain_text[:200]}...")
        
        detection_result = {
            'completion': False,
            'true_false': False,
            'matching_sentence_endings': False,
            'matching_headings': False,
            'matching_information': False,
            'multiple_choice': False,
            'list_selection': False,
            'listening_matching_headings': False,  # Special flag for listening matching
            'labelling': False,
            'labelling_table': False,
            'skip': False
        }

        # QUICK CHECK: table-tegs compatible labelling (Questions X-Y with short lines)
        if detect_label_table(section_html):
            detection_result['labelling'] = True
            detection_result['labelling_table'] = True
            print(f"[LISTENING] ✅ DETECTED: LABELLING TABLE (table-tegs compatible)")
            return detection_result
        
        # ========== PRIORITY 0: LABELLING (Label the plan/map/diagram) - HIGHEST PRIORITY ==========
        print(f"[LISTENING] 🏷️ PRIORITY 0: Analyzing LABELLING")
        
        labelling_patterns = [
            'label the plan',
            'label the map',
            'label the diagram',
            'label the chart',
        ]
        
        # Count option letters (A-Z) OR roman numerals (i-ix) for labelling
        option_letters_labelling = re.findall(r'<strong[^>]*>\s*[A-Z]\s*</strong>', section_html)
        option_roman_labelling = re.findall(r'<strong[^>]*>\s*(i{1,3}|iv|v|vi{1,3}|ix|x|xi{1,3})\s*</strong>', section_html, re.IGNORECASE)
        
        has_labelling_instruction = any(re.search(pattern, content_text, re.IGNORECASE) for pattern in labelling_patterns)
        has_letter_options_labelling = len(option_letters_labelling) >= 5
        has_roman_options_labelling = len(option_roman_labelling) >= 5
        has_choose_from_box = 'choose' in content_text and 'from the box' in content_text
        has_list_of_headings = 'list of headings' in content_text
        
        print(f"  ➤ Labelling instruction: {has_labelling_instruction}")
        print(f"  ➤ Letter options: {has_letter_options_labelling} (count: {len(option_letters_labelling)})")
        print(f"  ➤ Roman options: {has_roman_options_labelling} (count: {len(option_roman_labelling)})")
        print(f"  ➤ Choose from box: {has_choose_from_box}")
        print(f"  ➤ List of headings: {has_list_of_headings}")
        
        # Detect labelling: either with explicit instruction OR with roman numerals (List of Headings pattern)
        if (has_labelling_instruction and (has_letter_options_labelling or has_roman_options_labelling) and has_choose_from_box) or \
           (has_roman_options_labelling and has_list_of_headings):
            detection_result['labelling'] = True
            print(f"[LISTENING] ✅ DETECTED: LABELLING (Priority 0)")
            return detection_result
        
        # ========== PRIORITY 0.5: LISTENING MATCHING HEADINGS (Special Case) ==========
        # Check this AFTER labelling!
        # BUT: EXCLUDE multiple choice patterns first!
        print(f"[LISTENING] 🎯 PRIORITY 0.5: Analyzing LISTENING MATCHING HEADINGS (Special Case)")
        
        # CRITICAL: Exclude multiple choice and list selection patterns
        # If "choose the correct letter" and "write the correct letter in boxes" are present, this is multiple choice
        # If "choose two letters" and "write the correct letters in boxes" are present, this is list selection
        multiple_choice_exclusion_patterns = [
            'choose the correct letter' in content_text and 'write the correct letter in boxes' in content_text,
            'choose the correct letter' in content_text and 'write the correct letter' in content_text and 'boxes' in content_text,
            'choose the correct letter' in content_text and re.search(r'write.{0,30}correct.{0,30}letter.{0,30}boxes', content_text, re.IGNORECASE),
        ]
        
        list_selection_exclusion_patterns = [
            'choose two letters' in content_text and 'write the correct letters in boxes' in content_text,
            'choose three letters' in content_text and 'write the correct letters in boxes' in content_text,
            'choose four letters' in content_text and 'write the correct letters in boxes' in content_text,
            'choose five letters' in content_text and 'write the correct letters in boxes' in content_text,
            re.search(r'choose\s+(two|three|four|five)\s+letters', content_text, re.IGNORECASE) and 'write the correct letters in boxes' in content_text,
        ]
        
        # CRITICAL: Exclude labelling patterns
        labelling_exclusion_patterns = [
            'label the plan' in content_text,
            'label the map' in content_text,
            'label the diagram' in content_text,
            'label the chart' in content_text,
        ]
        
        has_multiple_choice_exclusion = any(multiple_choice_exclusion_patterns)
        has_list_selection_exclusion = any(list_selection_exclusion_patterns)
        has_labelling_exclusion = any(labelling_exclusion_patterns)
        
        if has_labelling_exclusion:
            print(f"  ➤ Labelling exclusion: TRUE - skipping listening matching headings")
            # Skip - this is labelling
        elif has_list_selection_exclusion:
            print(f"  ➤ List selection exclusion: TRUE - skipping listening matching headings")
            # Skip listening matching headings detection, continue to list selection
        elif has_multiple_choice_exclusion:
            print(f"  ➤ Multiple choice exclusion: TRUE - skipping listening matching headings")
            # Skip listening matching headings detection, continue to multiple choice
        else:
            # Check for listening-specific matching pattern: "What does/tells...about each of the following"
            # OR "In what time period can...help with the following things?"
            # OR "Which ... matches each description?" with A–E options
            # OR "What problems do the speakers identify for each experiment?"
            # OR presence of "List of Headings" in a listening context (A–H options)
            listening_matching_indicators = [
                'what does' in content_text and 'about each of the following' in content_text,
                'what tells' in content_text and 'about each of the following' in content_text,
                'tell' in content_text and 'about each of the following' in content_text,
                'in what time period' in content_text and 'help with the following' in content_text,
                'in what time period' in content_text and 'following things' in content_text,
                'in what' in content_text and 'help with the following' in content_text,
                'in what' in content_text and 'following things' in content_text,
                # New patterns (hotel/description matching)
                'which hotel matches each description' in content_text,
                ('matches each description' in content_text and 'which' in content_text),
                ('write the correct letter' in content_text and re.search(r'\b[a-e]\b', content_text) is not None and 'choose the correct letter' not in content_text),
                # New pattern: "What problems do the speakers identify"
                'what problems do the speakers identify' in content_text and 'experiment' in content_text,
                'what problems' in content_text and 'identify' in content_text and 'experiment' in content_text,
                'speakers identify' in content_text and 'experiment' in content_text,
                # New pattern: Treat "List of Headings" in listening with A–H as matching drag-drop
                ('list of headings' in content_text and bool(re.search(r'<strong>\s*[A-H]\s*</strong>', section_html))),
                # New pattern: "Which feature is related to each of the following..."
                ('which feature is related to each of the following' in content_text)
            ]
            
            has_listening_matching = any(listening_matching_indicators)
            has_write_letter_pattern = bool(re.search(r'write.{0,20}correct.{0,20}letter.{0,20}[a-z]', content_text, re.IGNORECASE))
            has_options_abc = bool(re.search(r'<strong>\s*[A-H]\s*</strong>', section_html))  # Support A-H
            has_question_dots = bool(re.search(r'<strong>\d+[\.]?\s*</strong>[^<]+&hellip;|\.{3,}|\.{2,}', section_html))
            
            print(f"  ➤ Listening matching indicators: {has_listening_matching}")
            print(f"  ➤ Write letter pattern: {has_write_letter_pattern}")
            print(f"  ➤ Options A-C: {has_options_abc}")
            print(f"  ➤ Question dots: {has_question_dots}")
            
            if has_listening_matching and has_write_letter_pattern and has_options_abc:
                detection_result['matching_sentence_endings'] = True  # Use matching_sentence_endings type
                detection_result['listening_matching_headings'] = True  # Special flag
                print(f"[LISTENING] ✅ DETECTED: LISTENING MATCHING HEADINGS (Priority 0.5)")
                return detection_result

        # SUPER-GUARD: NB implies drag-drop sentence endings (repeat allowed)
        # BUT: Check for Matching Information patterns first!
        try:
            has_nb = re.search(r'\bnb\b', content_text, re.IGNORECASE) or \
                     'you may use any letter more than once' in content_text or \
                     'may use any letter more than once' in content_text or \
                     'letters may be used more than once' in content_text or \
                     'you may choose any letter more than once' in content_text or \
                     'may choose any letter more than once' in content_text
            
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
                
                if has_paragraph_matching or has_section_matching or has_table_name or has_people_matching:
                    detection_result['matching_information'] = True
                    print(f"[LISTENING] ✅ DETECTED (NB Guard): MATCHING INFORMATION due to matching patterns + NB")
                    return detection_result
                else:
                    detection_result['matching_sentence_endings'] = True
                    print(f"[LISTENING] ✅ DETECTED (NB Guard): MATCHING SENTENCE ENDINGS due to NB")
                    return detection_result
        except Exception:
            pass
        
        # ========== PRIORITY 1: MATCHING SENTENCE ENDINGS ==========
        print(f"[LISTENING] 🥇 PRIORITY 1: Analyzing MATCHING SENTENCE ENDINGS")
        
        # Check for sentence endings patterns
        sentence_endings_phrases = [
            'complete each sentence with the correct ending',
            'complete the summary using the list of phrases',
            'complete the summary using the list of words',
            'using the list of phrases',
            'using the list of words',
            'correct ending',
            'sentence endings'
        ]
        
        has_sentence_endings_phrase = any(phrase in content_text for phrase in sentence_endings_phrases)
        has_complete_each_sentence = 'complete each sentence' in content_text
        has_correct_ending = 'correct ending' in content_text
        has_letter_range_pattern = bool(re.search(r'write.{0,20}correct.{0,20}letter.{0,20}[a-z][-–][a-z]', content_text))
        
        # Check for multiple options (A-J, A-G, etc.)
        option_letters = re.findall(r'<strong>\s*([A-Z])\s*</strong>', section_html)
        has_multiple_options = len(option_letters) >= 4
        
        # Check for summary context
        has_summary_context = 'summary' in content_text and ('complete' in content_text or 'using' in content_text)
        
        # Check for "below" keyword
        has_below_keyword = 'below' in content_text
        
        # Check for completion instruction
        has_completion_instruction = 'complete' in content_text and ('sentence' in content_text or 'summary' in content_text)
        
        # Check for question blanks
        has_question_blanks = bool(re.search(r'\.{3,}|&hellip;|…', section_html))
        
        # Check for paragraph contains (exclusion)
        has_paragraph_contains = 'paragraph contains' in content_text
        
        # Check for write correct letter
        has_write_correct_letter = 'write the correct letter' in content_text
        
        # EXCLUDED from sentence endings due to matching information patterns, multiple choice patterns, or headings patterns
        matching_info_exclusions = [
            'which paragraph contains',
            'paragraph contains',
            'reading passage has',
            'paragraphs,',
            'which section',
            'which section contains',
            'section contains',
        ]
        
        multiple_choice_exclusions = [
            'choose the correct letter',
            'select the correct answer',
            'write the correct letter in boxes'
        ]
        
        headings_exclusions = [
            'choose the correct heading',
            'list of headings',
            'write the correct number'
        ]
        
        has_matching_info_exclusions = any(exclusion in content_text for exclusion in matching_info_exclusions)
        has_multiple_choice_exclusions = any(exclusion in content_text for exclusion in multiple_choice_exclusions)
        has_headings_exclusions = any(exclusion in content_text for exclusion in headings_exclusions)
        
        print(f"  ➤ Sentence endings phrase: {has_sentence_endings_phrase}")
        print(f"  ➤ Complete each sentence: {has_complete_each_sentence}")
        print(f"  ➤ Correct ending: {has_correct_ending}")
        print(f"  ➤ Letter range pattern: {has_letter_range_pattern}")
        print(f"  ➤ Multiple options: {has_multiple_options} (count: {len(option_letters)})")
        print(f"  ➤ Summary context: {has_summary_context}")
        print(f"  ➤ Below keyword: {has_below_keyword}")
        print(f"  ➤ Completion instruction: {has_completion_instruction}")
        print(f"  ➤ Question blanks: {has_question_blanks}")
        print(f"  ➤ Paragraph contains: {has_paragraph_contains}")
        print(f"  ➤ Write correct letter: {has_write_correct_letter}")
        print(f"  ➤ EXCLUDED from sentence endings due to matching information patterns, multiple choice patterns, or headings patterns")
        print(f"  ➤ Matching endings score: 0")
        
        if (has_sentence_endings_phrase or has_complete_each_sentence or has_correct_ending) and \
           has_letter_range_pattern and has_multiple_options and has_summary_context and \
           not has_matching_info_exclusions and not has_multiple_choice_exclusions and not has_headings_exclusions:
            detection_result['matching_sentence_endings'] = True
            print(f"[LISTENING] ✅ DETECTED: MATCHING SENTENCE ENDINGS (Priority 1)")
            return detection_result

        # ========== PRIORITY 2: TRUE/FALSE/NOT GIVEN ==========
        print(f"[LISTENING] 🥈 PRIORITY 2: Analyzing TRUE/FALSE/NOT GIVEN")
        
        true_false_indicators = [
            'do the following statements agree',
            'agree with the information',
            'contradicts the information', 
            'statement agrees',
            'statement contradicts',
            'yes, no or not given',
            'true, false or not given'
        ]
        
        tf_keywords = ['true', 'false', 'not given', 'yes', 'no']
        
        has_tf_context = any(indicator in content_text for indicator in true_false_indicators)
        has_tf_keywords = any(keyword in content_text for keyword in tf_keywords)
        
        print(f"  ➤ True/False context: {has_tf_context}")
        print(f"  ➤ True/False keywords: {has_tf_keywords}")
        
        if has_tf_context and has_tf_keywords:
            detection_result['true_false'] = True
            print(f"[LISTENING] ✅ DETECTED: TRUE/FALSE/NOT GIVEN (Priority 2)")
            return detection_result

        # ========== PRIORITY 3: LIST SELECTION ==========
        print(f"[LISTENING] 🥉 PRIORITY 3: Analyzing LIST SELECTION")
        
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
            'select two letters',
            'select three letters',
            'write the correct letters in boxes',
            'write the correct letter in boxes',
        ]
        
        has_list_selection_context = any(indicator in content_text for indicator in list_selection_indicators)
        
        # STRONG list selection indicator: "choose two letters" AND "write the correct letters in boxes"
        has_strong_list_selection = (
            re.search(r'choose\s+(two|three|four|five)\s+letters', content_text, re.IGNORECASE) and 
            'write the correct letters in boxes' in content_text
        )
        
        # Check for A-I range (expanded from A-G to support A-I)
        has_ag_in_html = bool(re.search(r'[A-I]', section_html))
        has_ag_in_text = bool(re.search(r'letters?\s*[A-I]', content_text, re.IGNORECASE)) or bool(re.search(r'[A-I]', content_text, re.IGNORECASE))
        has_ag_range = has_ag_in_html and has_ag_in_text
        
        # Check for "Questions X-Y" format (range format)
        has_questions_range_format = bool(re.search(r'[Qq]uestions?\s+\d+[-–]\d+', content_text))
        
        # Check for "Questions X and Y" format
        has_questions_and_format = bool(re.search(r'[Qq]uestions?\s+\d+\s+and\s+\d+', content_text))
        
        # Check for multiple options (A, B, C, D, E, F, G, H, I)
        # Including nested spans format and <br /> format
        option_patterns = [
            # Pattern 0: <br /> format: "A &nbsp; &nbsp;altitude<br />"
            r'[A-I]\s*(?:&nbsp;){1,}[^<]+<br',
            # Pattern 1: Nested spans format: <p><span...><span...><strong>A </strong></span></span></span></p>
            r'<p[^>]*>(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\s*[A-I]\s*(?:&nbsp;)*\s*</strong>(?:</span>)*(?:</span>)*(?:</span>)*(?:</p>)',
            # Pattern 2: Standard format
            r'<strong>\s*[A-I]\s*</strong>',
            r'<em>[^<]*<strong>\s*[A-I]\s*</strong>',
            r'<strong>\s*[A-I][^>]*</strong>',
            # Pattern 3: Plain text format: "A    altitude" or "A &nbsp; altitude"
            r'[A-I](?:\s|&nbsp;){2,}[a-z]',
        ]
        
        option_count = 0
        for pattern in option_patterns:
            matches = re.findall(pattern, section_html, re.IGNORECASE)
            option_count += len(matches)
        
        has_multiple_options = option_count >= 2  # Reduced threshold for nested spans
        
        print(f"  ➤ List selection context: {has_list_selection_context}")
        print(f"  ➤ Strong list selection: {has_strong_list_selection}")
        print(f"  ➤ A-G range: {has_ag_range}")
        print(f"  ➤ Questions range format: {has_questions_range_format}")
        print(f"  ➤ Questions and format: {has_questions_and_format}")
        print(f"  ➤ Multiple options: {has_multiple_options} ({option_count})")
        
        # CRITICAL: If "Choose SIX answers from the box" is present, it's ALWAYS list_selection
        # This should take priority over everything else
        has_choose_answers_from_box = bool(re.search(r'choose\s+\w+\s+answers?\s+from\s+the\s+box', content_text, re.IGNORECASE))
        
        if has_choose_answers_from_box:
            detection_result['list_selection'] = True
            print(f"[LISTENING] ✅ DETECTED: LIST SELECTION (Priority 3 - 'Choose X answers from the box' format)")
            return detection_result
        
        # If strong list selection indicators are present, prioritize it even with fewer options
        if has_strong_list_selection and (has_questions_range_format or has_questions_and_format) and has_multiple_options:
            detection_result['list_selection'] = True
            print(f"[LISTENING] ✅ DETECTED: LIST SELECTION (Priority 3 - Strong indicators)")
            return detection_result
        
        # Relaxed condition: if we have "choose X letters" and A-F range, it's likely list selection
        if has_list_selection_context and has_ag_range and (has_questions_range_format or has_questions_and_format):
            # Even if has_multiple_options is False, if we have the context and range, it's list selection
            if has_multiple_options or option_count >= 1:  # Reduced threshold
                detection_result['list_selection'] = True
                print(f"[LISTENING] ✅ DETECTED: LIST SELECTION (Priority 3)")
                return detection_result

        # ========== PRIORITY 4: MULTIPLE CHOICE ==========
        print(f"[LISTENING] 🏆 PRIORITY 4: Analyzing MULTIPLE CHOICE")
        
        choice_indicators = [
            'choose the correct letter',
            'select the correct answer',
            'write the correct letter in boxes',
        ]
        
        has_choice_context = any(indicator in content_text for indicator in choice_indicators)
        
        # CRITICAL: Check for "Choose the correct letter, A, B, C or D" format FIRST
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
        
        # STRONG multiple choice indicator: "choose the correct letter" AND "write the correct letter in boxes"
        has_strong_multiple_choice = (
            'choose the correct letter' in content_text and 
            ('write the correct letter in boxes' in content_text or 
             re.search(r'write.{0,30}correct.{0,30}letter.{0,30}boxes', content_text, re.IGNORECASE))
        )
        
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
        
        has_abcd_pattern = len(abcd_patterns) >= 3  # Reduced threshold
        
        print(f"  ➤ Multiple choice context: {has_choice_context}")
        print(f"  ➤ Strong multiple choice: {has_strong_multiple_choice}")
        print(f"  ➤ Choose letter A,B,C format: {has_choose_letter_abcd}")
        print(f"  ➤ ABCD pattern count: {len(abcd_patterns)}")
        
        # CRITICAL: If "Choose the correct letter, A, B, C or D" format detected, FORCE multiple choice
        if has_choose_letter_abcd:
            detection_result['multiple_choice'] = True
            print(f"[LISTENING] ✅ DETECTED: MULTIPLE CHOICE (Priority 4 - FORCED by 'Choose the correct letter, A, B, C or D' format)")
            return detection_result
        
        # If strong multiple choice indicators are present, prioritize it even with fewer ABCD patterns
        if has_strong_multiple_choice and has_abcd_pattern:
            detection_result['multiple_choice'] = True
            print(f"[LISTENING] ✅ DETECTED: MULTIPLE CHOICE (Priority 4 - Strong indicators)")
            return detection_result
        
        if has_choice_context and has_abcd_pattern:
            detection_result['multiple_choice'] = True
            print(f"[LISTENING] ✅ DETECTED: MULTIPLE CHOICE (Priority 4)")
            return detection_result

        # ========== PRIORITY 4: COMPLETION ==========
        print(f"[LISTENING] 🏆 PRIORITY 4: Analyzing COMPLETION")
        
        completion_phrases = [
            'complete the table', 'complete the summary', 'complete the note',
            'choose no more than', 'write no more than', 'complete the sentences',
            'fill in the gaps', 'complete the diagram', 'complete the flow chart',
            'complete the form', 'label the diagram'
        ]
        
        has_strict_completion = any(phrase in content_text for phrase in completion_phrases)
        has_completion_dots = bool(re.search(r'\.{3,}|&hellip;|…', section_html))
        has_completion_instructions = 'complete' in content_text and ('table' in content_text or 'summary' in content_text or 'note' in content_text)
        
        print(f"  ➤ Strict completion phrases: {has_strict_completion}")
        print(f"  ➤ Completion dots: {has_completion_dots}")
        print(f"  ➤ Completion instructions: {has_completion_instructions}")

        if has_strict_completion or (has_question_blanks and not has_multiple_options) or has_completion_dots or has_completion_instructions:
            detection_result['completion'] = True
            print(f"[LISTENING] ✅ DETECTED: COMPLETION (Priority 4)")
            return detection_result

        # ========== PRIORITY 5: MATCHING HEADINGS ==========
        print(f"[LISTENING] 🎖️ PRIORITY 5: Analyzing MATCHING HEADINGS")
        
        headings_indicators = [
            'choose the correct heading',
            'list of headings',
            'correct heading for each paragraph',
            'correct heading for each section',
            'write the correct number'
        ]
        
        has_headings_context = any(indicator in content_text for indicator in headings_indicators)
        has_roman_numerals = bool(re.search(r'\b[i-vx]+[^a-z]', content_text)) or bool(re.search(r'<strong>[i-vx]+</strong>', section_html))
        has_paragraph_reference = 'paragraph' in content_text and ('a-g' in content_text or 'A-G' in section_html or 'a-i' in content_text or 'A-I' in section_html)
        has_write_correct_number = 'write the correct number' in content_text
        
        # CRITICAL: Exclude list_selection patterns from matching_headings
        # "Choose SIX answers from the box" should NOT be detected as matching_headings
        list_selection_exclusions = [
            r'choose\s+\w+\s+answers?\s+from\s+the\s+box',
            r'choose\s+\w+\s+letters?\s+from\s+the\s+box',
            r'write\s+the\s+correct\s+letters?\s+.*next\s+to'
        ]
        has_list_selection_exclusion = any(re.search(pattern, content_text, re.IGNORECASE) for pattern in list_selection_exclusions)
        
        # STRONG matching headings indicator: Roman numerals + Paragraph references (even without instruction text)
        # Pattern: <strong>iv</strong> ... <strong>1</strong> Paragraph <strong>A</strong>
        has_strong_matching_headings = (
            has_roman_numerals and 
            bool(re.search(r'paragraph\s+<strong>[A-G]</strong>', section_html, re.IGNORECASE)) and
            bool(re.search(r'<strong>\d+</strong>', section_html))
        )
        
        print(f"  ➤ Headings context: {has_headings_context}")
        print(f"  ➤ Roman numerals: {has_roman_numerals}")
        print(f"  ➤ Paragraph reference: {has_paragraph_reference}")
        print(f"  ➤ Write correct number: {has_write_correct_number}")
        print(f"  ➤ Strong matching headings: {has_strong_matching_headings}")
        print(f"  ➤ List selection exclusion: {has_list_selection_exclusion}")
        
        # If strong matching headings indicators are present, prioritize it even without instruction text
        # BUT exclude if it's list_selection
        if has_strong_matching_headings and not has_list_selection_exclusion:
            detection_result['matching_headings'] = True
            print(f"[LISTENING] ✅ DETECTED: MATCHING HEADINGS (Priority 5 - Strong indicators)")
            return detection_result
        
        if has_headings_context and (has_roman_numerals or has_paragraph_reference) and has_write_correct_number and not has_list_selection_exclusion:
            detection_result['matching_headings'] = True
            print(f"[LISTENING] ✅ DETECTED: MATCHING HEADINGS (Priority 5)")
            return detection_result

        # ========== PRIORITY 6: MATCHING INFORMATION ==========
        print(f"[LISTENING] 🏅 PRIORITY 6: Analyzing MATCHING INFORMATION")

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
            'correct timber cut'
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

        # Multiple choice exclusions
        multiple_choice_exclusions = [
            'choose the correct letter',
            'select the correct answer',
            'write the correct letter in boxes'
        ]
        
        has_multiple_choice_exclusions = any(exclusion in content_text for exclusion in multiple_choice_exclusions)
        
        print(f"  ➤ Matching info phrases: {has_matching_info_context}")
        print(f"  ➤ Letter range matching: {letter_range_matching}")
        print(f"  ➤ Paragraph context: {has_paragraph_context}")
        print(f"  ➤ Section context: {has_section_context}")
        print(f"  ➤ Timber context: {has_timber_context}")
        print(f"  ➤ Purpose context: {has_purpose_context}")
        print(f"  ➤ Multiple choice exclusions: {has_multiple_choice_exclusions}")
        
        # Only detect as matching information if it's NOT multiple choice
        if has_matching_info_context and not has_multiple_choice_exclusions and (letter_range_matching or has_paragraph_context or has_section_context or has_timber_context or has_purpose_context):
            detection_result['matching_information'] = True
            print(f"[LISTENING] ✅ DETECTED: MATCHING INFORMATION (Priority 6)")
            return detection_result


        # ========== PRIORITY 7: COMPLETION (LAST RESORT) ==========
        print(f"[LISTENING] 🏆 PRIORITY 7: Analyzing COMPLETION (LAST RESORT)")
        
        has_strict_completion = any(phrase in content_text for phrase in completion_phrases)
        has_completion_dots = bool(re.search(r'\.{3,}|&hellip;|…', section_html))
        has_completion_instructions = 'complete' in content_text and ('table' in content_text or 'summary' in content_text or 'note' in content_text)
        
        print(f"  ➤ Strict completion phrases: {has_strict_completion}")
        print(f"  ➤ Completion dots: {has_completion_dots}")
        print(f"  ➤ Completion instructions: {has_completion_instructions}")

        if has_strict_completion or has_completion_dots or has_completion_instructions:
            detection_result['completion'] = True
            print(f"[LISTENING] ✅ DETECTED: COMPLETION (Priority 7)")
            return detection_result
        
        # ========== ABSOLUTE FALLBACK ==========
        print(f"[LISTENING] 🆘 ABSOLUTE FALLBACK")

        # Check for multiple options
        option_letters = re.findall(r'<strong>\s*([A-Z])\s*</strong>', section_html)
        has_multiple_options = len(option_letters) >= 4

        # If we have options A-Z, it's probably matching sentence endings
        if has_multiple_options and len(option_letters) >= 4:
            detection_result['matching_sentence_endings'] = True
            print(f"[LISTENING] ✅ DETECTED: MATCHING SENTENCE ENDINGS (Absolute Fallback)")
            return detection_result

        # Final fallback - default to completion
        print(f"[LISTENING] ❌ NO SPECIFIC TYPE DETECTED: Defaulting to COMPLETION")
        detection_result['completion'] = True
        return detection_result

    def process_section(self, section_html, analysis, question_range, unprocessed_questions, original_html):
        """Process section with the appropriate parser"""
        if analysis.get('skip') or not unprocessed_questions:
            print(f"[LISTENING] ⏭️ Skipping section {question_range}")
            return original_html
        
        print(f"[LISTENING] 🎯 Processing section {question_range} for questions: {unprocessed_questions}")
        
        # Process LABELLING (Label the plan/map/diagram)
        if analysis.get('labelling', False):
            print(f"[LISTENING] 🔧 Using LABELLING parser for section {question_range}")
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
                        print(f"[LISTENING] ✅ Label table parser created {table_components} table-tegs components")
                        return self.direct_section_replacement(original_html, section_html, converted_html, question_range)
                    else:
                        print(f"[LISTENING] ⚠️ Label table parser produced no components, falling back to drag-drop parser")
                
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
                print(f"[LISTENING] ✅ Labelling parser created {new_components} components, {tag_count} inputs")
                
                if new_components > 0:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[LISTENING] ⚠️ No components created")
                    return original_html
                    
            except Exception as e:
                print(f"[LISTENING] ❌ LABELLING parsing failed: {e}")
                import traceback
                print(f"[LISTENING] Traceback: {traceback.format_exc()}")
                return original_html
        
        # Process TRUE/FALSE
        elif analysis['true_false']:
            print(f"[LISTENING] 🔧 Using TRUE/FALSE parser for section {question_range}")
            try:
                processed_html = parse_true_false_questions(section_html)
                
                # Check for question-input tags
                patterns = [
                    r'<question-input[^>]*data-question-type="true_false_not_given"[^>]*>',
                    r'<question-input[^>]*data-question-type="yes_no_not_given"[^>]*>'
                ]
                
                new_tags = []
                for pattern in patterns:
                    matches = re.finditer(pattern, processed_html)
                    for match in matches:
                        q_num_match = re.search(r'data-question-number="(\d+)"', match.group(0))
                        if q_num_match:
                            new_tags.append(int(q_num_match.group(1)))
                
                successful_tags = [q for q in new_tags if q in unprocessed_questions]
                
                print(f"[LISTENING] ✅ TRUE/FALSE parser created {len(successful_tags)} tags: {successful_tags}")
                
                if successful_tags:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[LISTENING] ⚠️ No successful tags created")
                    return original_html
                    
            except Exception as e:
                print(f"[LISTENING] ❌ TRUE/FALSE parsing failed: {e}")
                return original_html
        
        # Process LIST SELECTION
        # CRITICAL: Also check if this section has "Choose X answers from the box" even if not detected
        # This prevents matching_headings from incorrectly processing list_selection questions
        has_choose_answers_from_box = bool(re.search(r'choose\s+\w+\s+answers?\s+from\s+the\s+box', section_html, re.IGNORECASE))
        
        if analysis.get('list_selection', False) or has_choose_answers_from_box:
            if has_choose_answers_from_box and not analysis.get('list_selection', False):
                print(f"[LISTENING] 🔧 FORCING LIST SELECTION for section {question_range} (detected 'Choose X answers from the box')")
            else:
                print(f"[LISTENING] 🔧 Using LIST SELECTION parser for section {question_range}")
            try:
                from apps.listening.utils.list_selection_parser import ListSelectionParser
                parser = ListSelectionParser()
                processed_html = parser.parse_and_insert_inputs(section_html)
                
                # Check for both drag-drop and list-selection tags
                patterns = [
                    r'<drag-drop-matching-sentence-endings[^>]*data-options[^>]*>',
                    r'<drag-drop-matching-sentence-endings[^>]*data-question-type="matching_headings"[^>]*>',
                    r'<list-selection-tegs[^>]*data-options[^>]*>',
                    r'<list-selection-tegs[^>]*question_type="list_selection"[^>]*>'
                ]
                
                new_components = 0
                for pattern in patterns:
                    new_components += len(re.findall(pattern, processed_html))
                
                print(f"[LISTENING] ✅ List selection parser created {new_components} components")
                
                if new_components > 0:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[LISTENING] ⚠️ No components created")
                    return original_html
                    
            except Exception as e:
                print(f"[LISTENING] ❌ LIST SELECTION parsing failed: {e}")
                import traceback
                print(f"[LISTENING] Traceback: {traceback.format_exc()}")
                return original_html
        
        # Process MULTIPLE CHOICE
        elif analysis.get('multiple_choice', False):
            print(f"[LISTENING] 🔧 Using MULTIPLE CHOICE parser for section {question_range}")
            try:
                processed_html = parse_multiple_choice(section_html)
                
                # Convert ALL multiple_choice types to multiple_choice_with_multiple_answer
                # This ensures ALL multiple choice questions use multiple_choice_with_multiple_answer
                conversion_patterns = [
                    (r'data-question-type="multiple_choice"', 'data-question-type="multiple_choice_with_multiple_answer"'),
                    (r'data-question-type="multiple_choice_with_single_answer"', 'data-question-type="multiple_choice_with_multiple_answer"'),
                    (r'data-question-type="multiple_choice_multiple_answers"', 'data-question-type="multiple_choice_with_multiple_answer"'),
                ]
                
                for old_pattern, new_replacement in conversion_patterns:
                    if re.search(old_pattern, processed_html):
                        count = len(re.findall(old_pattern, processed_html))
                        processed_html = re.sub(old_pattern, new_replacement, processed_html)
                        print(f"[LISTENING] 🔄 Converted {count} {old_pattern} to {new_replacement}")
                
                # Convert data-options to data-question-options for question-input tags
                # This ensures compatibility with frontend renderers
                if re.search(r'<question-input[^>]*data-options=', processed_html):
                    count = len(re.findall(r'<question-input[^>]*data-options=', processed_html))
                    processed_html = re.sub(
                        r'(<question-input[^>]*)data-options=',
                        r'\1data-question-options=',
                        processed_html
                    )
                    print(f"[LISTENING] 🔄 Converted {count} data-options to data-question-options in question-input tags")
                
                # Check for question-input tags
                patterns = [
                    r'<question-input[^>]*data-question-type="multiple_choice_with_multiple_answer"[^>]*>',
                    r'<question-input[^>]*data-question-type="multiple_choice"[^>]*>',
                    r'<question-input[^>]*data-question-type="multiple_choice_multiple_answers"[^>]*>',
                    r'<drag-drop-sentence-input[^>]*data-question-type="multiple_choice_with_multiple_answer"[^>]*>',
                    r'<drag-drop-sentence-input[^>]*data-question-type="multiple_choice"[^>]*>',
                    r'<drag-drop-sentence-input[^>]*data-question-type="multiple_choice_multiple_answers"[^>]*>',
                    r'<drag-drop-matching-sentence-endings[^>]*data-options[^>]*>',
                    r'<list-selection-tegs[^>]*>',
                    r'<list-selection-input[^>]*>'
                ]
                
                new_components = 0
                for pattern in patterns:
                    new_components += len(re.findall(pattern, processed_html))
                
                print(f"[LISTENING] ✅ Multiple choice parser created {new_components} components")
                
                if new_components > 0:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[LISTENING] ⚠️ No components created")
                    return original_html
                    
            except Exception as e:
                print(f"[LISTENING] ❌ MULTIPLE CHOICE parsing failed: {e}")
                return original_html
        
        
        # Process LISTENING MATCHING HEADINGS (Special Case)
        elif analysis.get('listening_matching_headings') and analysis['matching_sentence_endings']:
            print(f"[LISTENING] 🔧 Using LISTENING MATCHING HEADINGS parser for section {question_range}")
            try:
                from apps.listening.utils.matching_parser import parse_listening_matching_headings
                processed_html = parse_listening_matching_headings(section_html)
                
                # Remove any wrapping div tags from processed_html
                processed_html = processed_html.strip()
                if processed_html.startswith('<div>'):
                    processed_html = processed_html[5:].strip()
                if processed_html.startswith('<div '):
                    processed_html = re.sub(r'^<div[^>]*>', '', processed_html, flags=re.IGNORECASE).strip()
                if processed_html.endswith('</div>'):
                    processed_html = processed_html[:-6].strip()
                
                # Check for drag-drop-sentence-input tags OR table-tegs-input (handle both single and double quotes, with flexible spacing)
                patterns = [
                    r'<drag-drop-sentence-input[^>]*data-question-number\s*=\s*["\'](\d+)["\'][^>]*>',
                    r'<drag-drop-sentence-input[^>]*data-question-number\s*=\s*(\d+)[\s>]',
                    r'data-question-number\s*=\s*["\']?(\d+)["\']?'
                ]
                
                new_tags = []
                for pattern in patterns:
                    matches = re.finditer(pattern, processed_html, re.IGNORECASE)
                    for match in matches:
                        try:
                            tag_num = int(match.group(1))
                            if tag_num not in new_tags:  # Avoid duplicates
                                new_tags.append(tag_num)
                        except (ValueError, IndexError):
                            continue
                
                # Check for table-tegs-input component
                has_table_tegs = bool(re.search(r'<table-tegs-input[^>]*>', processed_html))
                
                if has_table_tegs:
                    # Extract question numbers from data-questions attribute
                    questions_match = re.search(r"data-questions=['\"]([^'\"]+)['\"]", processed_html)
                    if questions_match:
                        try:
                            import json
                            questions_data = json.loads(questions_match.group(1))
                            table_question_numbers = [int(q.get('question_number', 0)) for q in questions_data if q.get('question_number')]
                            new_tags.extend(table_question_numbers)
                            print(f"[LISTENING] ✅ Found table-tegs-input with {len(table_question_numbers)} questions: {table_question_numbers}")
                        except Exception as e:
                            print(f"[LISTENING] ⚠️ Error parsing table-tegs-input questions: {e}")
                
                print(f"[LISTENING] 🔍 Found {len(new_tags)} tags in processed HTML: {new_tags}")
                print(f"[LISTENING] 🔍 Processed HTML preview: {processed_html[:300]}...")
                
                successful_tags = [q for q in new_tags if q in unprocessed_questions]
                
                print(f"[LISTENING] ✅ Listening matching headings parser created {len(successful_tags)} tags: {successful_tags}")
                
                if successful_tags or has_table_tegs:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[LISTENING] ⚠️ No successful tags created (found {len(new_tags)} tags total, but {len(unprocessed_questions)} unprocessed questions)")
                    return original_html
                    
            except Exception as e:
                print(f"[LISTENING] ❌ LISTENING MATCHING HEADINGS parsing failed: {e}")
                import traceback
                print(f"[LISTENING] Traceback: {traceback.format_exc()}")
                return original_html
        
        # Process MATCHING SENTENCE ENDINGS
        elif analysis['matching_sentence_endings']:
            print(f"[LISTENING] 🔧 Using MATCHING SENTENCE ENDINGS parser for section {question_range}")
            try:
                processed_html = parse_matching_sentence_endings(section_html)
                
                # Check for drag-drop-sentence-input tags OR table-tegs-input
                patterns = [
                    r'<drag-drop-sentence-input[^>]*data-question-number="(\d+)"[^>]*>'
                ]
                
                new_tags = []
                for pattern in patterns:
                    new_tags.extend([int(match.group(1)) for match in re.finditer(pattern, processed_html)])
                
                # Check for table-tegs-input component
                has_table_tegs = bool(re.search(r'<table-tegs-input[^>]*>', processed_html))
                
                if has_table_tegs:
                    # Extract question numbers from data-questions attribute
                    questions_match = re.search(r"data-questions=['\"]([^'\"]+)['\"]", processed_html)
                    if questions_match:
                        try:
                            import json
                            questions_data = json.loads(questions_match.group(1))
                            table_question_numbers = [int(q.get('question_number', 0)) for q in questions_data if q.get('question_number')]
                            new_tags.extend(table_question_numbers)
                            print(f"[LISTENING] ✅ Found table-tegs-input with {len(table_question_numbers)} questions: {table_question_numbers}")
                        except Exception as e:
                            print(f"[LISTENING] ⚠️ Error parsing table-tegs-input questions: {e}")
                
                successful_tags = [q for q in new_tags if q in unprocessed_questions]
                
                print(f"[LISTENING] ✅ Matching sentence endings parser created {len(successful_tags)} tags: {successful_tags}")
                
                if successful_tags or has_table_tegs:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[LISTENING] ⚠️ No successful tags created")
                    return original_html
                    
            except Exception as e:
                print(f"[LISTENING] ❌ MATCHING SENTENCE ENDINGS parsing failed: {e}")
                return original_html
        
        # Process COMPLETION
        elif analysis['completion']:
            print(f"[LISTENING] 🔧 Using COMPLETION parser for section {question_range}")
            try:
                processed_html = parse_completion_questions(section_html)
                
                # Check for question-input tags
                patterns = [
                    r'<question-input[^>]*data-question-type="completion"[^>]*>',
                    r'<question-input[^>]*data-question-type="sentence_completion"[^>]*>'
                ]
                
                new_tags = []
                for pattern in patterns:
                    matches = re.finditer(pattern, processed_html)
                    for match in matches:
                        q_num_match = re.search(r'data-question-number="(\d+)"', match.group(0))
                        if q_num_match:
                            new_tags.append(int(q_num_match.group(1)))
                
                successful_tags = [q for q in new_tags if q in unprocessed_questions]
                
                print(f"[LISTENING] ✅ Completion parser created {len(successful_tags)} tags: {successful_tags}")
                
                if successful_tags:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[LISTENING] ⚠️ No successful tags created")
                    return original_html
                    
            except Exception as e:
                print(f"[LISTENING] ❌ COMPLETION parsing failed: {e}")
                return original_html
        
        # Process MATCHING INFORMATION
        elif analysis['matching_information']:
            print(f"[LISTENING] 🔧 Using MATCHING INFORMATION parser for section {question_range}")
            try:
                processed_html = parse_matching_information(section_html)
                
                # Check for both table-tegs-input and table-tegs components
                patterns = [
                    r'<table-tegs-input[^>]*data-question-type="matching_information"[^>]*>',
                    r'<table-tegs[^>]*data-question-type="matching_information"[^>]*>'
                ]
                
                new_components = 0
                for pattern in patterns:
                    new_components += len(re.findall(pattern, processed_html))
                
                print(f"[LISTENING] ✅ Matching information parser created {new_components} components")
                
                if new_components > 0:
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[LISTENING] ⚠️ No components created")
                    return original_html
                    
            except Exception as e:
                print(f"[LISTENING] ❌ MATCHING INFORMATION parsing failed: {e}")
                return original_html
        
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
                print(f"[LISTENING] ⚠️ Section {question_range} was detected as matching_headings but has list_selection pattern - switching to list_selection")
                try:
                    from apps.listening.utils.list_selection_parser import ListSelectionParser
                    parser = ListSelectionParser()
                    processed_html = parser.parse_and_insert_inputs(section_html)
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
                    print(f"[LISTENING] ⚠️ Failed to parse as list_selection: {e}")
            
            print(f"[LISTENING] 🔧 Using MATCHING HEADINGS parser for section {question_range}")
            try:
                processed_html = parse_matching_headings(section_html)
                
                # Check for matching headings components
                patterns = [
                    r'<drag-drop-matching-headings[^>]*>',
                    r'<table-tegs-input[^>]*data-question-type="matching_headings"[^>]*>',
                    r'<drag-drop-matching-sentence-endings[^>]*data-question-type="matching_headings"[^>]*>'
                ]
                
                new_components = 0
                for pattern in patterns:
                    new_components += len(re.findall(pattern, processed_html))
                
                print(f"[LISTENING] ✅ Matching headings parser created {new_components} components")
                
                if new_components > 0:
                    # Keep parser output as-is (preserve wrapping elements like <div>)
                    return self.direct_section_replacement(original_html, section_html, processed_html, question_range)
                else:
                    print(f"[LISTENING] ⚠️ No components created")
                    return original_html
                    
            except Exception as e:
                print(f"[LISTENING] ❌ MATCHING HEADINGS parsing failed: {e}")
                return original_html
        
        # Fallback
        print(f"[LISTENING] ⚠️ No specific parser matched for section {question_range}")
        return original_html

    def direct_section_replacement(self, original_html, section_html, processed_html, question_range):
        """Direct section replacement method"""
        print(f"[LISTENING] 🔄 Direct section replacement for {question_range}")
        
        try:
            # Find the section in original HTML and replace it with processed version
            if section_html in original_html:
                result = original_html.replace(section_html, processed_html)
                print(f"[LISTENING] ✅ Direct replacement successful")
                return result
            else:
                # If exact match not found, try partial matching
                section_start = section_html[:200]
                section_end = section_html[-200:] if len(section_html) > 200 else section_html
                
                start_pos = original_html.find(section_start)
                if start_pos != -1:
                    end_search = section_end
                    end_pos = original_html.find(end_search, start_pos)
                    if end_pos != -1:
                        end_pos += len(end_search)
                        result = original_html[:start_pos] + processed_html + original_html[end_pos:]
                        print(f"[LISTENING] ✅ Partial replacement successful")
                        return result
                
                print(f"[LISTENING] ⚠️ Could not find section for replacement, returning processed")
                return processed_html
                
        except Exception as e:
            print(f"[LISTENING] ❌ Direct replacement failed: {e}")
            return original_html
    
    def process_multi_type_questions(self, html_content):
        """ULTIMATE multi-type processor with ALL question types including matching_information"""
        print(f"[LISTENING] 🏭 Starting ULTIMATE multi-type question processing...")
        
        # Step 1: Find existing tags
        existing_tags = self.find_existing_tags(html_content)
        
        # Step 2: Split into sections with ENHANCED detection
        sections = self.split_question_sections(html_content)
        
        # Step 3: Process each section
        result_html = html_content
        changes_made = False
        
        for section in sections:
            # Check if this section actually has any tags
            section_has_tags = bool(re.search(
                r'<question-input|<list-selection-tegs|<drag-drop-matching-sentence-endings|<table-tegs',
                section['html'],
                re.IGNORECASE
            ))
            
            # If section has no tags, it needs processing (even if existing_tags says otherwise)
            if not section_has_tags:
                print(f"[LISTENING] 🔄 Section {section['range']}: No tags found, will process")
                # Clear existing tags for this section's range to force processing
                for q_num in range(section['start_question'], section['end_question'] + 1):
                    if q_num in existing_tags:
                        del existing_tags[q_num]
            
            # Find unprocessed questions in this section
            unprocessed = self.get_unprocessed_questions_in_section(
                section['html'], existing_tags, 
                section['start_question'], section['end_question']
            )
            
            if not unprocessed:
                print(f"[LISTENING] ⏭️ Section {section['range']}: All questions already processed")
                continue
            
            # Analyze this section's type
            analysis = self.analyze_section_type(section['html'], section['range'], unprocessed)
            
            # Process this section
            old_result = result_html
            result_html = self.process_section(
                section['html'], analysis, section['range'], 
                unprocessed, result_html
            )
            
            if result_html != old_result:
                changes_made = True
                print(f"[LISTENING] ✅ Section {section['range']} processed successfully")
        
        if changes_made:
            print(f"[LISTENING] ✅ ULTIMATE multi-type processing complete - CHANGES MADE")
        else:
            print(f"[LISTENING] ⚠️ ULTIMATE multi-type processing complete - NO CHANGES")
        
        return result_html

    def save(self, *args, **kwargs):
        """ULTIMATE UNIVERSAL QUESTION PROCESSOR"""
        print(f"[LISTENING] 🚀 Processing Listening: {self.title or 'Untitled'}")
        
        if self.questions:
            # Store original questions before parsing (only if not already stored and questions are unparsed)
            if not self.questions_raw:
                # Check if questions have been parsed (contain question-input tags)
                has_parsed_tags = bool(re.search(r'<question-input|data-question-number=|drag-drop-|table-tegs|list-selection-tegs', self.questions))
                if not has_parsed_tags:
                    # Store original unparsed questions
                    self.questions_raw = self.questions
                    print(f"[LISTENING] 💾 Stored original unparsed questions in questions_raw")
            
            original_questions = self.questions
            
            try:
                # Use the ultimate multi-type processor
                self.questions = self.process_multi_type_questions(self.questions)
                
                if self.questions != original_questions:
                    print(f"[LISTENING] ✅ SUCCESS: Questions processed successfully")
                else:
                    print(f"[LISTENING] ⚠️ No changes made")
                    
            except Exception as e:
                print(f"[LISTENING] 💥 ERROR: {str(e)}")
                import traceback
                print(f"[LISTENING] Full traceback: {traceback.format_exc()}")
                self.questions = original_questions
        
        super().save(*args, **kwargs)
        print(f"[LISTENING] 💾 Saved successfully with ID: {self.id}")


class ListeningAnswer(models.Model):
    listening = models.ForeignKey(Listening, on_delete=models.CASCADE, related_name='answers')
    question_number = models.PositiveIntegerField(verbose_name="Question Number", default=1)
    question = models.TextField(
        verbose_name="Question",
        blank=True,
        default="",
        help_text="Write the question. For MCQ put options on new lines, e.g. A) ... B) ... C) ... D) ...",
    )
    true_answer = models.CharField(max_length=200, null=True, blank=True, verbose_name="Correct Answer")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Listening Question'
        verbose_name_plural = 'Listening Questions'

    def __str__(self):
        return f" Listening ID {self.listening_id}"
    
class ListeningUserAnswer(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='listening_user_answers')
    listening = models.ForeignKey(Listening, on_delete=models.CASCADE, related_name='user_answers')
    question_number = models.PositiveIntegerField(verbose_name='Question Number')
    answer = models.CharField(max_length=200,null=True, blank=True, verbose_name="User Answer")
    is_true = models.BooleanField(default=False, verbose_name="Is Correct")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'listening', 'question_number')
        verbose_name = 'Listening Answer'
        verbose_name_plural = 'Listening Answers'

    def __str__(self):
        return f"User {self.user} - Question {self.question_number} for Listening {self.listening}"

    def save(self, *args, **kwargs):
        try:
            correct_answer_obj = ListeningAnswer.objects.get(
                listening=self.listening,
                question_number=self.question_number
            )
            if self.answer:
                # Normalize user answer: remove extra spaces, convert to lowercase
                user_answer = re.sub(r'\s+', ' ', self.answer.strip().lower())
                
                raw_true_answer = correct_answer_obj.true_answer.strip()
                valid_answers = []
                
                for answer in raw_true_answer.split(';'):
                    # Normalize each valid answer the same way
                    normalized_answer = re.sub(r'\s+', ' ', answer.strip().lower())
                    valid_answers.append(normalized_answer)
                
                self.is_true = user_answer in valid_answers
            else:
                self.is_true = False
        except ListeningAnswer.DoesNotExist:
            self.is_true = False

        # ✅ Only one save!
        super().save(*args, **kwargs)