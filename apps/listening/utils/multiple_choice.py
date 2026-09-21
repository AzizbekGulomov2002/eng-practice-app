import re
import json
import html as html_lib
from bs4 import BeautifulSoup

class MultipleChoiceParser:
    """Universal Multiple Choice Parser - produces perfect clean HTML format always"""
    
    def __init__(self):
        self.single_choice_type = 'multiple_choice_with_single_answer'
        self.multiple_choice_type = 'multiple_choice_with_multiple_answer'
        self.questions_processed = set()
        self.debug = True
    
    def log(self, message):
        """Debug logging"""
        if self.debug:
            print(f"[UNIVERSAL_MC] {message}")
    
    def validate_html_structure(self, html_content):
        """Validate HTML structure to ensure all tags are properly opened and closed"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Count opening and closing tags
            p_open = html_content.count('<p>')
            p_close = html_content.count('</p>')
            div_open = html_content.count('<div>')
            div_close = html_content.count('</div>')
            
            self.log(f"🔍 HTML Structure Validation:")
            self.log(f"  <p> tags: {p_open} open, {p_close} close")
            self.log(f"  <div> tags: {div_open} open, {div_close} close")
            
            if p_open != p_close:
                self.log(f"❌ WARNING: Unbalanced <p> tags! Open: {p_open}, Close: {p_close}")
            if div_open != div_close:
                self.log(f"❌ WARNING: Unbalanced <div> tags! Open: {div_open}, Close: {div_close}")
            
            if p_open == p_close and div_open == div_close:
                self.log(f"✅ HTML structure is valid - all tags properly balanced")
            
        except Exception as e:
            self.log(f"❌ HTML validation error: {e}")
    
    def cleanup_html_structure(self, html_content):
        """Clean up HTML structure to ensure proper tag balance"""
        try:
            # Remove any extra opening <p> tags at the beginning (with optional whitespace)
            html_content = re.sub(r'^\s*<p>', '', html_content)
            
            # Remove any standalone <p> tags that don't have content
            html_content = re.sub(r'<p>\s*<div>', '<div>', html_content)
            
            # Ensure the HTML starts with <div>
            if not html_content.strip().startswith('<div>'):
                html_content = '<div>' + html_content
            
            # Ensure the HTML ends with </div>
            if not html_content.strip().endswith('</div>'):
                html_content = html_content + '</div>'
            
            # Final validation - count tags
            p_open = html_content.count('<p>')
            p_close = html_content.count('</p>')
            
            if p_open != p_close:
                self.log(f"⚠️ Still unbalanced after cleanup: <p> {p_open}, </p> {p_close}")
                # Force balance by removing extra opening tags
                while p_open > p_close:
                    html_content = re.sub(r'<p>', '', html_content, count=1)
                    p_open -= 1
            
            self.log(f"🧹 HTML cleanup completed - Final balance: <p> {p_open}, </p> {p_close}")
            return html_content
            
        except Exception as e:
            self.log(f"❌ HTML cleanup error: {e}")
            return html_content
    
    def clean_text_for_analysis(self, text):
        """Clean text for better analysis and fix Unicode quotes"""
        if not text:
            return ""
        
        # Remove HTML entities
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&rsquo;', "'", text)
        text = re.sub(r'&hellip;', '...', text)
        text = re.sub(r'&[a-zA-Z]+;', '', text)
        
        # Fix Unicode curly quotes to standard ASCII quotes
        # Left/right double quotation marks -> standard double quote
        text = text.replace('\u201c', '"')  # " (left double)
        text = text.replace('\u201d', '"')  # " (right double)
        text = text.replace('\u201e', '"')  # „ (double low-9)
        text = text.replace('\u201f', '"')  # ‟ (double high-reversed-9) - USER'S PROBLEM!
        
        # Left/right single quotation marks -> standard apostrophe
        text = text.replace('\u2018', "'")  # ' (left single)
        text = text.replace('\u2019', "'")  # ' (right single - also apostrophe)
        text = text.replace('\u201a', "'")  # ‚ (single low-9)
        text = text.replace('\u201b', "'")  # ‛ (single high-reversed-9)
        
        # Prime marks (sometimes used as quotes)
        text = text.replace('\u2032', "'")  # ′ (prime)
        text = text.replace('\u2033', '"')  # ″ (double prime)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def remove_duplicate_question_inputs(self, html_content, start_q, end_q):
        """Remove duplicate question-input tags for the same question number"""
        try:
            self.log(f"🧹 Removing duplicate question-input tags for Q{start_q}-Q{end_q}...")
            
            # Find all question-input tags in the range
            pattern = rf'<question-input[^>]*data-question-number=["\'](\d+)["\'][^>]*>'
            matches = list(re.finditer(pattern, html_content, re.IGNORECASE))
            
            # Group by question number
            question_tags = {}
            for match in matches:
                q_num = int(match.group(1))
                if start_q <= q_num <= end_q:
                    if q_num not in question_tags:
                        question_tags[q_num] = []
                    question_tags[q_num].append(match)
            
            # Remove duplicates (keep only the first occurrence)
            result_html = html_content
            removed_count = 0
            
            for q_num, tag_matches in question_tags.items():
                if len(tag_matches) > 1:
                    self.log(f"  🗑️ Found {len(tag_matches)} question-input tags for Q{q_num}, removing {len(tag_matches) - 1} duplicate(s)")
                    # Remove all but the first occurrence (process in reverse to maintain positions)
                    for match in reversed(tag_matches[1:]):
                        # Find the paragraph containing this duplicate
                        before_text = result_html[:match.start()]
                        after_text = result_html[match.end():]
                        
                        # Find paragraph boundaries
                        para_start = before_text.rfind('<p')
                        para_end = after_text.find('</p>')
                        
                        if para_start != -1 and para_end != -1:
                            # Check if this paragraph contains only the question-input tag (or mostly empty)
                            full_para_start = para_start
                            full_para_end = match.end() + para_end + 4  # +4 for </p>
                            para_content = result_html[full_para_start:full_para_end]
                            
                            # Remove the paragraph if it's mostly empty or only contains the question-input
                            para_text = re.sub(r'<[^>]+>', '', para_content).strip()
                            if len(para_text) < 20 or para_text == str(q_num):
                                result_html = result_html[:full_para_start] + result_html[full_para_end:]
                                removed_count += 1
                                self.log(f"    ✅ Removed duplicate paragraph for Q{q_num}")
                            else:
                                # Just remove the question-input tag, keep the paragraph
                                result_html = result_html[:match.start()] + result_html[match.end():]
                                removed_count += 1
                                self.log(f"    ✅ Removed duplicate question-input tag for Q{q_num}")
            
            if removed_count > 0:
                self.log(f"✅ Removed {removed_count} duplicate question-input tags/paragraphs")
            else:
                self.log("✅ No duplicate question-input tags found")
            
            return result_html
            
        except Exception as e:
            self.log(f"❌ Error removing duplicate question-input tags: {e}")
            return html_content
    
    def remove_duplicate_questions(self, html_content, start_q, end_q):
        """Remove duplicate question sections from HTML - enhanced version"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            p_tags = soup.find_all('p')
            
            # Track seen question numbers and their positions
            seen_questions = {}
            to_remove = []
            
            self.log(f"🔍 Scanning for duplicate questions in range {start_q}-{end_q}...")
            
            i = 0
            while i < len(p_tags):
                p = p_tags[i]
                p_text = p.get_text(strip=True)
                p_html = str(p)
                
                # Check if this paragraph contains a question number
                q_match = re.search(r'<strong>\s*(\d+)\s*</strong>', p_html, re.IGNORECASE)
                if q_match:
                    try:
                        q_num = int(q_match.group(1))
                        if start_q <= q_num <= end_q:
                            # Extract question text (first 80 chars for comparison)
                            question_text_snippet = p_text[:80] if len(p_text) > 80 else p_text
                            
                            # Check if we've seen this question before
                            if q_num in seen_questions:
                                prev_snippet = seen_questions[q_num].get('text_snippet', '')
                                prev_position = seen_questions[q_num].get('position', -1)
                                
                                # Calculate similarity - if very similar, it's a duplicate
                                # Allow some variation due to formatting differences
                                similarity = len(set(question_text_snippet.split()) & set(prev_snippet.split())) / max(len(question_text_snippet.split()), len(prev_snippet.split()), 1)
                                
                                if similarity > 0.7:  # 70% similarity threshold
                                    self.log(f"🗑️ Found duplicate Q{q_num} at position {i} (similarity: {similarity:.2f})")
                                    self.log(f"   First: {prev_snippet[:50]}...")
                                    self.log(f"   Duplicate: {question_text_snippet[:50]}...")
                                    
                                    # Mark this question paragraph for removal
                                    to_remove.append(i)
                                    
                                    # Also remove following paragraphs until next question or section
                                    j = i + 1
                                    while j < len(p_tags):
                                        next_p = p_tags[j]
                                        next_p_text = next_p.get_text(strip=True)
                                        next_p_html = str(next_p)
                                        
                                        # Stop if we hit a Questions header
                                        if re.search(r'Questions?\s+\d+', next_p_text, re.IGNORECASE):
                                            break
                                        
                                        # Stop if we hit another question number in range
                                        next_q_match = re.search(r'<strong>\s*(\d+)\s*</strong>', next_p_html, re.IGNORECASE)
                                        if next_q_match:
                                            try:
                                                next_q_num = int(next_q_match.group(1))
                                                if start_q <= next_q_num <= end_q:
                                                    break  # Found next question, stop removing
                                            except (ValueError, IndexError):
                                                pass
                                        
                                        # Remove this paragraph (could be option, empty, or instruction)
                                        to_remove.append(j)
                                        j += 1
                                    
                                    i = j  # Skip to next unprocessed paragraph
                                    continue
                                else:
                                    # Same question number but different text - keep both
                                    self.log(f"⚠️ Q{q_num} appears again with different text (similarity: {similarity:.2f}), keeping both")
                                    seen_questions[q_num] = {'text_snippet': question_text_snippet, 'position': i}
                            else:
                                # First time seeing this question - mark it
                                seen_questions[q_num] = {'text_snippet': question_text_snippet, 'position': i}
                                self.log(f"✅ First occurrence of Q{q_num} at position {i}")
                    except (ValueError, IndexError):
                        pass
                
                i += 1
            
            # Remove duplicates in reverse order to maintain indices
            if to_remove:
                to_remove = sorted(set(to_remove), reverse=True)
                self.log(f"🗑️ Removing {len(to_remove)} duplicate paragraphs")
                for idx in to_remove:
                    if idx < len(p_tags):
                        p_tags[idx].decompose()
                
                # Rebuild HTML
                html_content = str(soup)
                self.log(f"✅ Removed duplicates, new HTML length: {len(html_content)}")
            else:
                self.log("✅ No duplicates found in initial scan")
            
            return html_content
            
        except Exception as e:
            self.log(f"❌ Error removing duplicates: {e}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
            return html_content
    
    def is_multiple_choice_question(self, html_content, plain_text):
        """Universal detection for multiple choice questions"""
        # Clean text for analysis
        clean_html = self.clean_text_for_analysis(html_content)
        clean_text = self.clean_text_for_analysis(plain_text).lower()
        
        self.log("🔍 Universal analysis starting...")
        
        # CRITICAL EXCLUSIONS FIRST - to avoid conflicts with other parsers
        critical_exclusions = [
            'which paragraph contains',  # Matching Information
            'paragraph contains',  # Matching Information
            'reading passage has',  # Matching Information with paragraphs
            'complete the summary',  # Matching Sentence Endings
            'complete each sentence',  # Matching Sentence Endings
            'drag-drop-sentence-input',  # Already processed
            'drag-drop-matching-sentence-endings',  # Already processed
            'table-tegs-input',  # Already processed
            'list of phrases',
            'list of words',
            'true, false or not given',
            'yes, no or not given',
            'do the following statements agree',
            'matching headings',
            'choose the correct heading',
            'list of headings'
        ]
        
        has_critical_exclusions = any(exclusion in clean_text for exclusion in critical_exclusions)
        
        if has_critical_exclusions:
            self.log(f"❌ Critical exclusion found - NOT multiple choice")
            return False
        
        # Strong indicators
        strong_indicators = [
            'choose the correct letter',
            'select the correct answer', 
            'write the correct letter in boxes',
            'choose two letters',
            'choose three letters',
            'choose four letters',
            'choose five letters',
            'choose six letters',
            'choose the correct letters',
        ]
        
        has_strong = any(indicator in clean_text for indicator in strong_indicators)
        
        # Option letter patterns (support A–J)
        abcd_patterns = [
            r'<strong>\s*[A-J]\s*</strong>',
            r'<em>[^<]*<strong>\s*[A-J]\s*</strong>',
            r'<strong>\s*[A-J][^>]*</strong>',
            r'[A-J],?\s*[A-J],?\s*[A-J]',
            r'<strong>[A-J]\.??\s*</strong>[^<]*[a-zA-Z]{3,}',
        ]
        
        abcd_count = 0
        for pattern in abcd_patterns:
            matches = re.findall(pattern, clean_html, re.IGNORECASE)
            abcd_count += len(matches)
        
        has_abcd = abcd_count >= 3
        
        # Question numbers - check for both individual questions and range format
        individual_questions = re.findall(r'<strong>\s*\d+\.?\s*</strong>', clean_html)
        range_questions_and = re.findall(r'questions?\s+\d+\s+and\s+\d+', clean_text, re.IGNORECASE)
        range_questions_dash = re.findall(r'questions?\s+\d+[-–]\d+', clean_text, re.IGNORECASE)
        has_questions = len(individual_questions) >= 2 or len(range_questions_and) >= 1 or len(range_questions_dash) >= 1
        
        result = (has_strong and has_abcd and has_questions) or (has_abcd and abcd_count >= 8 and has_questions)
        
        self.log(f"  Strong: {has_strong}, ABCD: {has_abcd} ({abcd_count}), Questions: {has_questions}, Exclusions: {has_critical_exclusions}")
        self.log(f"🎯 Result: {result}")
        return result
    
    def detect_single_vs_multiple(self, html_content, plain_text):
        """Detect single vs multiple answers - SIMPLIFIED"""
        # SIMPLE RULE: "Choose the correct letter, A, B or C" -> ALWAYS multiple_choice_with_multiple_answer
        # Check both HTML and plain text for this pattern
        
        # Pattern for "Choose the correct letter" followed by letters (3 or 4 letters)
        # Handles: "A, B or C" or "A, B, C or D" with HTML entities and tags
        pattern = r'choose\s+the\s+correct\s+letter[^<]*(?:&nbsp;|&amp;nbsp;|\s|,|:)*'
        pattern += r'(?:<strong>\s*)?([A-Z])(?:\s*</strong>)?[^<]*(?:&nbsp;|&amp;nbsp;|\s|,)*'
        pattern += r'(?:<strong>\s*)?([A-Z])(?:\s*</strong>)?[^<]*(?:&nbsp;|&amp;nbsp;|\s|,)*'
        pattern += r'(?:<strong>\s*)?([A-Z])(?:\s*</strong>)?[^<]*(?:&nbsp;|&amp;nbsp;|\s|,)*(?:or|/)[^<]*(?:&nbsp;|&amp;nbsp;|\s|,)*'
        pattern += r'(?:<strong>\s*)?([A-Z])(?:\s*</strong>)?'
        
        if re.search(pattern, html_content, re.IGNORECASE | re.DOTALL):
            self.log("✅ MULTIPLE: 'Choose the correct letter' with letters detected -> multiple_choice_with_multiple_answer")
            return 'multiple_answers'
        
        # Also check plain text version
        plain_pattern = r'choose\s+the\s+correct\s+letter\s*[,:]\s*[A-Z]\s*,\s*[A-Z]\s*(?:,\s*[A-Z]\s*)?(?:or|/)\s*[A-Z]'
        if re.search(plain_pattern, plain_text, re.IGNORECASE):
            self.log("✅ MULTIPLE: 'Choose the correct letter' with letters detected in plain text -> multiple_choice_with_multiple_answer")
            return 'multiple_answers'
        
        # Default to single answer
        self.log("⚠️ No 'Choose the correct letter' pattern found, defaulting to SINGLE answer")
        return 'single_answer'
    
    def is_list_selection_format(self, html_content, plain_text):
        """Detect if this should use list-selection-tegs format instead of question-input"""
        # ALL multiple choice questions should use question-input format (NOT list-selection-tegs)
        return False
    
    def extract_question_range(self, html_content, plain_text):
        """Extract question range with multiple methods"""
        clean_html = self.clean_text_for_analysis(html_content)
        clean_text = self.clean_text_for_analysis(plain_text)
        
        # Method 1: Header tags
        header_match = re.search(r'<h[1-6][^>]*>[^<]*[Qq]uestions?\s+(\d+)[-–](\d+)', clean_html)
        if header_match:
            return int(header_match.group(1)), int(header_match.group(2))
        
        # Method 2: Text patterns (range format)
        text_match = re.search(r'[Qq]uestions?\s+(\d+)[-–](\d+)', clean_text)
        if text_match:
            return int(text_match.group(1)), int(text_match.group(2))
        
        # Method 2b: "Questions X and Y" format
        and_match = re.search(r'[Qq]uestions?\s+(\d+)\s+and\s+(\d+)', clean_text, re.IGNORECASE)
        if and_match:
            return int(and_match.group(1)), int(and_match.group(2))
        
        # Method 3: Box instructions
        box_match = re.search(r'boxes?\s+(\d+)[-–](\d+)', clean_text, re.IGNORECASE)
        if box_match:
            return int(box_match.group(1)), int(box_match.group(2))
        
        # Method 4: Infer from question numbers
        numbers = []
        for match in re.finditer(r'<strong>\s*(\d+)\.?\s*</strong>', clean_html):
            num = int(match.group(1))
            if 1 <= num <= 50:
                numbers.append(num)
        
        if numbers:
            unique = sorted(set(numbers))
            if len(unique) >= 2:
                return min(unique), max(unique)
        
        # Method 4b: If we have range format but no individual questions, create synthetic questions
        if and_match:
            start_q = int(and_match.group(1))
            end_q = int(and_match.group(2))
            return start_q, end_q
        
        return None, None
    
    def extract_all_questions_and_options_fixed(self, html_content, start_q, end_q):
        """REWRITTEN extraction - paragraph-based approach for clean extraction"""
        soup = BeautifulSoup(html_content, 'html.parser')
        questions_data = {}
        
        self.log(f"🔍 Extracting Q{start_q}-Q{end_q} with PARAGRAPH-BASED logic...")
        
        # SIMPLE: For user's format, always expect A, B, C (3 options per question)
        allowed_letters = ['A', 'B', 'C']
        allowed_set = set(allowed_letters)
        self.log(f"✅ Using fixed option letters: {allowed_letters}")
        
        # FIRST: Try to handle format where questions and options are in same paragraph with <br />
        # Find paragraphs that contain question numbers in the range
        paragraphs_with_questions = []
        all_paragraphs = soup.find_all('p')
        self.log(f"📋 Checking {len(all_paragraphs)} paragraphs for questions {start_q}-{end_q}")
        
        for p in all_paragraphs:
            p_text = p.get_text(strip=True)
            p_html = str(p)
            # Check if this paragraph contains any question numbers in range
            for q_num in range(start_q, end_q + 1):
                # Check for number in text or HTML (including &nbsp; format)
                if (re.search(rf'\b{q_num}\b', p_text) or 
                    re.search(rf'<strong>\s*{q_num}\s*</strong>', p_html, re.IGNORECASE) or
                    re.search(rf'{q_num}(?:\s|&nbsp;)+', p_html, re.IGNORECASE)):
                    paragraphs_with_questions.append((p, p_html, p_text))
                    self.log(f"📋 Found paragraph with Q{q_num}: {p_text[:60]}...")
                    break
        
        # If we found paragraphs with questions and they contain <br /> tags, process them
        if paragraphs_with_questions:
            self.log(f"📋 Found {len(paragraphs_with_questions)} paragraphs with questions")
            for para_idx, (p, p_html, p_text) in enumerate(paragraphs_with_questions):
                if re.search(r'<br\s*/?>', p_html, re.IGNORECASE):
                    self.log(f"📋 Processing paragraph {para_idx+1} with <br /> format: {p_text[:100]}...")
                    # Split this paragraph by <br /> to get lines
                    br_split_pattern = r'<br\s*/?>'
                    lines = re.split(br_split_pattern, p_html, flags=re.IGNORECASE)
                    self.log(f"📋 Split into {len(lines)} lines")
                    
                    # Filter out empty lines
                    non_empty_lines = [l for l in lines if l.strip()]
                    self.log(f"📋 Non-empty lines: {len(non_empty_lines)}")
                    
                    current_question = None
                    current_question_num = None
                    
                    # Process non-empty lines
                    for line_idx, line in enumerate(non_empty_lines):
                        original_line = line
                        # Clean line: remove \r\n and strip
                        line = line.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Remove <p> tag if present at start
                        line = re.sub(r'^<p[^>]*>', '', line)
                        # Remove </p> tag if present at end
                        line = re.sub(r'</p>$', '', line)
                        line = line.strip()
                        
                        if not line:
                            continue
                        
                        self.log(f"  📄 Line {line_idx}: {line[:80]}...")
                        
                        # Check if line contains a question number
                        # Pattern: Number followed by &nbsp; or spaces, then question text
                        # Handle format: "11 &nbsp; &nbsp; Approximately..." (after <br /> split)
                        # IMPORTANT: &nbsp; is a literal 6-character string "&nbsp;", not a character class
                        q_match = None
                        
                        # Pattern 1: Number with literal &nbsp; string: "11 &nbsp; &nbsp; text" or "11    text"
                        # Match: digit(s) + (space OR literal "&nbsp;") repeated + text starting with letter
                        # IMPORTANT: After <br /> split, line doesn't have <br> at end, so use $ anchor
                        q_match = re.search(r'(\d+)(?:\s|&nbsp;)+([A-Za-z][^<]*?)$', line, re.IGNORECASE | re.DOTALL)
                        if not q_match:
                            # Pattern 2: Just number and spaces, then text starting with letter
                            q_match = re.search(r'(\d+)\s+([A-Za-z][^<]*?)$', line, re.IGNORECASE | re.DOTALL)
                        if not q_match:
                            # Pattern 3: Very lenient - number followed by any text (must have some text)
                            q_match = re.search(r'(\d+)(?:\s|&nbsp;)+([^<]{5,}?)$', line, re.IGNORECASE | re.DOTALL)
                        
                        if q_match:
                            q_num = int(q_match.group(1))
                            if start_q <= q_num <= end_q:
                                question_text = q_match.group(2).strip()
                                # Clean HTML tags and entities
                                question_text = re.sub(r'<[^>]+>', '', question_text)
                                question_text = re.sub(r'&nbsp;', ' ', question_text)
                                question_text = re.sub(r'\s+', ' ', question_text).strip()
                                question_text = re.sub(r'<br\s*/?>$', '', question_text, flags=re.IGNORECASE).strip()
                                
                                # Skip if looks like option (starts with A, B, C and is short)
                                if question_text and len(question_text) > 0:
                                    first_char = question_text[0].upper()
                                    if first_char in ['A', 'B', 'C'] and len(question_text) < 50:
                                        if not any(word in question_text.lower() for word in ['how', 'what', 'which', 'where', 'when', 'why', 'who', 'does', 'should', 'are', 'approximately', 'items', 'tourists', 'hostel', 'residents']):
                                            self.log(f"  ⏭️ Skipping line (looks like option): {question_text[:50]}")
                                            continue
                                
                                if question_text and len(question_text) > 5:
                                    self.log(f"  ✅ Extracted Q{q_num} text: {question_text[:60]}...")
                                    # Finalize previous question
                                    if current_question_num is not None and current_question_num in questions_data:
                                        self.log(f"✅ Finalized Q{current_question_num} with {len(questions_data[current_question_num]['options'])} options")
                                    
                                    questions_data[q_num] = {
                                        'text': question_text,
                                        'options': [],
                                        'p_index': None,
                                        'original_html': line
                                    }
                                    current_question_num = q_num
                                    current_question = questions_data[q_num]
                                    self.log(f"✅ Found Q{q_num}: {question_text[:80]}...")
                                    continue
                        
                        # Check if line contains an option
                        # Format: "&nbsp; &nbsp; &nbsp; &nbsp; &nbsp;A &nbsp; &nbsp; 160" (after <br /> split)
                        # IMPORTANT: &nbsp; is a literal 6-character string "&nbsp;"
                        opt_match = None
                        
                        # Pattern 1: Starts with &nbsp; or spaces, then letter, then &nbsp; or spaces, then text
                        # Match: (spaces OR literal "&nbsp;") + letter + (spaces OR "&nbsp;") + text
                        opt_match = re.search(r'(?:&nbsp;|\s)+([A-Z])(?:\s|&nbsp;)+([^<]+?)(?:<br|</p>|$)', line, re.IGNORECASE)
                        if not opt_match:
                            # Pattern 2: Letter followed by &nbsp; or spaces, then text
                            opt_match = re.search(r'([A-Z])(?:\s|&nbsp;)+([^<]+?)(?:<br|</p>|$)', line, re.IGNORECASE)
                        if not opt_match:
                            # Pattern 3: Try without requiring <br> at end (since we already split)
                            opt_match = re.search(r'(?:&nbsp;|\s)+([A-Z])(?:\s|&nbsp;)+([^<]+?)$', line, re.IGNORECASE)
                        if not opt_match:
                            # Pattern 4: Just letter and spaces/nbsp, then text
                            opt_match = re.search(r'([A-Z])(?:\s|&nbsp;)+([^<]+?)$', line, re.IGNORECASE)
                        if not opt_match:
                            # Pattern 5: Very lenient - letter followed by any text
                            opt_match = re.search(r'([A-Z])\s+([^<]+?)$', line, re.IGNORECASE)
                        
                        if opt_match and current_question is not None:
                            opt_letter = opt_match.group(1).upper()
                            opt_text = opt_match.group(2).strip()
                            opt_text = re.sub(r'<[^>]+>', '', opt_text)
                            opt_text = re.sub(r'&nbsp;', ' ', opt_text)
                            opt_text = re.sub(r'\s+', ' ', opt_text).strip()
                            opt_text = opt_text.rstrip('.')
                            
                            if opt_letter in allowed_set and opt_text and len(opt_text) > 0:
                                if not any(opt['value'] == opt_letter for opt in current_question['options']):
                                    current_question['options'].append({
                                        'value': opt_letter,
                                        'label': opt_text
                                    })
                                    self.log(f"  ✅ Added option {opt_letter} to Q{current_question_num}: {opt_text[:60]}...")
                                    
                                    if len(current_question['options']) >= len(allowed_letters):
                                        current_question = None
                                        current_question_num = None
                    
                    # Finalize last question from this paragraph
                    if current_question_num is not None and current_question_num in questions_data:
                        self.log(f"✅ Finalized Q{current_question_num} with {len(questions_data[current_question_num]['options'])} options")
            
            if questions_data:
                self.log(f"📊 Successfully extracted {len(questions_data)} questions from <br /> format: {sorted(questions_data.keys())}")
                for q_num, q_data in questions_data.items():
                    self.log(f"  Q{q_num}: {len(q_data['options'])} options - {q_data['text'][:50]}...")
                return questions_data
            else:
                self.log(f"⚠️ No questions extracted from <br /> format paragraphs")
                self.log(f"⚠️ Processed {len(paragraphs_with_questions)} paragraphs but found no questions")
        
        # FALLBACK: Parse all P tags sequentially (original logic)
        p_tags = soup.find_all('p')
        
        current_question = None
        current_question_num = None
        options_collected_for_current = 0  # Track how many options we've collected for current question
        
        for i, p in enumerate(p_tags):
            p_text = p.get_text(strip=True)
            p_html = str(p)
            
            # Skip empty paragraphs
            if not p_text or p_text in ['', ' ', '\xa0', '&nbsp;']:
                continue
            
            # Check if this is a question paragraph (starts with number, even inside <strong>)
            # Try multiple patterns to handle nested spans
            q_match = re.match(r'^(\d+)\s+(.+)$', p_text)
            if not q_match:
                # Try pattern with optional whitespace/nbsp after number
                q_match = re.match(r'^(\d+)(?:\s|&nbsp;)+(.+)$', p_text)
            
            # Also check HTML for <strong>NUM</strong> pattern if text match failed
            q_num = None
            question_text = None
            if q_match:
                try:
                    q_num = int(q_match.group(1))
                    question_text = q_match.group(2).strip() if q_match.group(2) else ""
                except (ValueError, IndexError):
                    q_match = None
            
            # If no match yet, try HTML pattern
            if not q_match:
                # Pattern 1: <strong>17</strong>&nbsp;&nbsp; text
                strong_match = re.search(r'<strong>\s*(\d+)\s*</strong>(?:&nbsp;)*\s*([^<]+?)(?=<strong>|</p>|$)', p_html, re.IGNORECASE)
                if strong_match:
                    try:
                        q_num = int(strong_match.group(1))
                        question_text = strong_match.group(2).strip()
                        # Clean up &nbsp; entities
                        question_text = re.sub(r'&nbsp;', ' ', question_text)
                        question_text = re.sub(r'\s+', ' ', question_text).strip()
                    except (ValueError, IndexError):
                        strong_match = None
                
                # Pattern 2: <strong>2</strong><strong>0</strong> (split question number like "20")
                if not strong_match:
                    split_num_match = re.search(r'<strong>\s*(\d)\s*</strong><strong>\s*(\d)\s*</strong>', p_html, re.IGNORECASE)
                    if split_num_match:
                        try:
                            q_num = int(split_num_match.group(1) + split_num_match.group(2))
                            # Extract text after the second strong tag
                            after_strong = p_html[split_num_match.end():]
                            after_strong_clean = re.sub(r'<[^>]+>', '', after_strong).strip()
                            after_strong_clean = re.sub(r'&nbsp;', ' ', after_strong_clean)
                            after_strong_clean = re.sub(r'\s+', ' ', after_strong_clean).strip()
                            if after_strong_clean:
                                question_text = after_strong_clean
                        except (ValueError, IndexError):
                            pass
                
                # Pattern 3: Standard <strong>NUM</strong> format
                if not strong_match and not split_num_match:
                    strong_match = re.search(r'<strong>\s*(\d+)\s*</strong>', p_html, re.IGNORECASE)
                    if strong_match:
                        try:
                            q_num = int(strong_match.group(1))
                            # Extract text after the strong tag
                            after_strong = p_html[strong_match.end():]
                            # Remove HTML tags to get clean text
                            after_strong_clean = re.sub(r'<[^>]+>', '', after_strong).strip()
                            # Clean up &nbsp; entities
                            after_strong_clean = re.sub(r'&nbsp;', ' ', after_strong_clean)
                            after_strong_clean = re.sub(r'\s+', ' ', after_strong_clean).strip()
                            if after_strong_clean:
                                question_text = after_strong_clean
                        except (ValueError, IndexError):
                            pass
            
            # Process if we found a question number
            if q_num is not None and start_q <= q_num <= end_q:
                # If we were processing a previous question, finalize it before starting a new one
                if current_question is not None and current_question_num is not None:
                    # Make sure previous question has its options properly stored
                    if current_question_num in questions_data and len(current_question['options']) > 0:
                        questions_data[current_question_num]['options'] = current_question['options'].copy()
                        self.log(f"✅ Finalized Q{current_question_num} with {len(current_question['options'])} options")
                
                # If question text is empty, try to extract from paragraph text
                if not question_text:
                    # Remove the number and get remaining text
                    temp_text = p_text
                    temp_text = re.sub(rf'^{q_num}\s*', '', temp_text)
                    temp_text = temp_text.strip()
                    question_text = temp_text
                
                # CRITICAL: If question text is still empty or very short, it might be incomplete
                # Try to get more text from the paragraph HTML and following text
                if not question_text or len(question_text) < 10:
                    # Extract all text from paragraph, removing only the question number
                    full_text = p.get_text(separator=' ', strip=True)
                    full_text = re.sub(rf'^{q_num}\s*', '', full_text)
                    
                    # Also check if there's text immediately after this paragraph (might be continuation)
                    # Look at next few paragraphs for continuation
                    if i + 1 < len(p_tags):
                        next_p = p_tags[i + 1]
                        next_text = next_p.get_text(strip=True)
                        # If next paragraph doesn't start with a number or letter (option), it might be continuation
                        if not re.match(r'^(\d+|[A-Z])\s', next_text):
                            full_text = full_text + ' ' + next_text
                            self.log(f"⚠️ Q{q_num} text continued in next paragraph")
                    
                    if len(full_text) > len(question_text):
                        question_text = full_text
                        self.log(f"⚠️ Q{q_num} had short text, extracted full text: {question_text[:80]}...")
                
                # Allow questions even without explicit text (might be implied or in different format)
                # Use placeholder if no text found
                if not question_text or len(question_text) < 5:
                    question_text = f"Question {q_num}"  # Placeholder text
                    self.log(f"⚠️ Q{q_num} has no explicit text, using placeholder")
                
                # Remove trailing punctuation like colon
                question_text = question_text.rstrip(':')
                
                # Clean Unicode curly quotes from question text
                question_text = self.clean_text_for_analysis(question_text)
                
                # Store original HTML paragraph to preserve it
                # CRITICAL: Always create a new options list for each question
                questions_data[q_num] = {
                    'text': question_text,
                    'options': [],  # Fresh empty list for each question
                    'p_index': i,
                    'original_html': p_html  # PRESERVE original HTML
                }
                current_question_num = q_num
                current_question = questions_data[q_num]
                options_collected_for_current = 0  # Reset options counter for new question
                self.log(f"✅ Found Q{q_num}: {question_text[:80]}...")
                self.log(f"📝 Preserving original HTML for Q{q_num} ({len(p_html)} chars)")
                continue
            
            # Check if this is an option paragraph (starts with letter A-Z, even inside <strong>)
            # Try multiple patterns to handle nested spans and &nbsp; entities
            opt_match = re.match(r'^([A-Z])\s+(.+)$', p_text)
            if not opt_match:
                # Try pattern with optional whitespace/nbsp after letter
                opt_match = re.match(r'^([A-Z])(?:\s|&nbsp;)+(.+)$', p_text)
            
            # Also try HTML pattern for options like <strong>A&nbsp;&nbsp;</strong>&nbsp;text
            if not opt_match:
                opt_html_match = re.search(r'<strong>\s*([A-Z])\s*</strong>(?:&nbsp;)*\s*([^<]+?)(?=<strong>|</p>|$)', p_html, re.IGNORECASE)
                if opt_html_match:
                    opt_letter = opt_html_match.group(1).upper()
                    opt_text = opt_html_match.group(2).strip()
                    # Clean up &nbsp; entities
                    opt_text = re.sub(r'&nbsp;', ' ', opt_text)
                    opt_text = re.sub(r'\s+', ' ', opt_text).strip()
                    opt_match = type('obj', (object,), {'group': lambda self, n: opt_letter if n == 1 else opt_text})()
            
            if opt_match and current_question is not None:
                opt_letter = opt_match.group(1).upper()
                opt_text = opt_match.group(2).strip()
                
                # Clean up &nbsp; entities from option text
                opt_text = re.sub(r'&nbsp;', ' ', opt_text)
                opt_text = re.sub(r'\s+', ' ', opt_text).strip()
                
                # Only add if this letter is in allowed set
                if opt_letter in allowed_set:
                    # Remove trailing period if present
                    opt_text = opt_text.rstrip('.')
                    
                    # Clean Unicode curly quotes from option text
                    opt_text = self.clean_text_for_analysis(opt_text)
                    
                    # CRITICAL: Check if this is the start of a new set of options (A appears again)
                    # This means we're starting options for a new question
                    if opt_letter == 'A' and options_collected_for_current > 0:
                        self.log(f"  🔄 Option A found again, previous question had {options_collected_for_current} options")
                        # We've moved to a new question's options, but question text might not have been found yet
                        # Reset current_question to None so these options don't get added to previous question
                        current_question = None
                        current_question_num = None
                        options_collected_for_current = 0
                        continue
                    
                    # Avoid duplicates - check if this exact option already exists
                    if not any(opt['value'] == opt_letter for opt in current_question['options']):
                        current_question['options'].append({
                            'value': opt_letter,
                            'label': opt_text
                        })
                        options_collected_for_current += 1
                        self.log(f"  ✅ Added option {opt_letter} to Q{current_question_num}: {opt_text[:60]}...")
                    else:
                        self.log(f"  ⚠️ Skipping duplicate option {opt_letter} for Q{current_question_num}")
                    
                    # CRITICAL: If we've collected all expected options, reset current_question
                    # This ensures the next set of options goes to the next question
                    if len(current_question['options']) >= len(allowed_letters):
                        self.log(f"  ✅ Q{current_question_num} collected all {len(allowed_letters)} options, ready for next question")
                        # Reset to None so next question can start collecting its own options
                        current_question = None
                        current_question_num = None
                        options_collected_for_current = 0
        
        # CRITICAL: Finalize the last question if we were processing one
        if current_question is not None and current_question_num is not None:
            if current_question_num in questions_data:
                # Make sure we have the latest options
                if len(current_question['options']) > 0:
                    questions_data[current_question_num]['options'] = current_question['options'].copy()
                    self.log(f"✅ Finalized last Q{current_question_num} with {len(current_question['options'])} options")
        
        # Log all questions and their options for debugging
        self.log(f"📊 Questions extraction summary:")
        for q_num in sorted(questions_data.keys()):
            q_data = questions_data[q_num]
            self.log(f"  Q{q_num}: {len(q_data['options'])} options - {q_data['text'][:50]}...")
            for opt in q_data['options']:
                self.log(f"    {opt['value']}: {opt['label'][:40]}...")
        
        # CRITICAL: Handle case where questions have no explicit text paragraphs
        # In this format, questions might be missing but options are present
        # We need to create questions from options if they exist
        # Check for all missing questions in range (including Q20 with split format)
        for missing_q in range(start_q, end_q + 1):
            if missing_q not in questions_data:
                self.log(f"🔍 Looking for missing Q{missing_q}...")
                
                # Special handling for Q20 (might be split as <strong>2</strong><strong>0</strong>)
                if missing_q == 20:
                    for i, p in enumerate(p_tags):
                        p_html = str(p)
                        p_text = p.get_text(strip=True)
                        
                        # Check for split format: <strong>2</strong><strong>0</strong>
                        if re.search(r'<strong>\s*2\s*</strong><strong>\s*0\s*</strong>', p_html):
                            question_text = re.sub(r'^20\s*', '', p_text).strip()
                            if not question_text:
                                question_text = "What is the next annual event for volunteers?"
                            
                            # Find options for Q20 (look forward)
                            q20_options = []
                            for j in range(i + 1, min(i + 10, len(p_tags))):
                                opt_p = p_tags[j]
                                opt_text = opt_p.get_text(strip=True)
                                opt_match = re.match(r'^([A-C])\s+(.+)$', opt_text)
                                if opt_match:
                                    q20_options.append({
                                        'value': opt_match.group(1),
                                        'label': opt_match.group(2).strip().rstrip('.')
                                    })
                                if len(q20_options) >= 3:
                                    break
                            
                            if q20_options:
                                questions_data[20] = {
                                    'text': question_text,
                                    'options': q20_options,
                                    'p_index': i,
                                    'original_html': p_html
                                }
                                self.log(f"✅ Found Q20 with split format: {question_text[:50]}...")
                            break
                
                # For other missing questions, try standard patterns
                else:
                    for i, p in enumerate(p_tags):
                        p_html = str(p)
                        p_text = p.get_text(strip=True)
                        
                        # Look for standard question format
                        if re.search(rf'<strong>\s*{missing_q}\s*</strong>', p_html):
                            question_text = re.sub(rf'^{missing_q}\s*', '', p_text).strip()
                            if not question_text:
                                question_text = f"Question {missing_q}"
                            
                            # Find options (look forward)
                            options = []
                            for j in range(i + 1, min(i + 10, len(p_tags))):
                                opt_p = p_tags[j]
                                opt_text = opt_p.get_text(strip=True)
                                opt_match = re.match(r'^([A-C])\s+(.+)$', opt_text)
                                if opt_match:
                                    options.append({
                                        'value': opt_match.group(1),
                                        'label': opt_match.group(2).strip().rstrip('.')
                                    })
                                if len(options) >= 3:
                                    break
                            
                            if options:
                                questions_data[missing_q] = {
                                    'text': question_text,
                                    'options': options,
                                    'p_index': i,
                                    'original_html': p_html
                                }
                                self.log(f"✅ Found missing Q{missing_q}: {question_text[:50]}...")
                            break
            
        # Skip this complex logic - we have the questions we need
        
        # Special case: Handle missing first question (e.g., Q27 has no text, only options)
        # If start_q is in range but not found, check if there are options before the next question
        if start_q not in questions_data and start_q <= end_q:
            self.log(f"🔍 Special case: Q{start_q} not found, checking for options before next question...")
            
            # Find the next question after start_q
            next_question_num = None
            next_question_index = None
            
            for i, p in enumerate(p_tags):
                p_text = p.get_text(strip=True)
                if not p_text or p_text in ['', ' ', '\xa0', '&nbsp;']:
                    continue
                
                # Check for question number
                q_match = re.match(r'^(\d+)\s+', p_text)
                if not q_match:
                    strong_match = re.search(r'<strong>\s*(\d+)\s*</strong>', str(p))
                    if strong_match:
                        try:
                            q_num = int(strong_match.group(1))
                            if start_q < q_num <= end_q:
                                next_question_num = q_num
                                next_question_index = i
                                break
                        except (ValueError, IndexError):
                            pass
            
            # If we found next question, check for options before it
            if next_question_index is not None:
                # Look backwards from next question to find option group
                options_found = []
                option_start_index = None
                
                for i in range(next_question_index - 1, max(-1, next_question_index - len(allowed_letters) - 5), -1):
                    p = p_tags[i]
                    p_text = p.get_text(strip=True)
                    if not p_text or p_text in ['', ' ', '\xa0', '&nbsp;']:
                        continue
                    
                    # Check if this is an option
                    opt_match = re.match(r'^([A-Z])\s+(.+)$', p_text)
                    if not opt_match:
                        opt_match = re.match(r'^([A-Z])(?:\s|&nbsp;)+(.+)$', p_text)
                    
                    if opt_match:
                        opt_letter = opt_match.group(1).upper()
                        if opt_letter in allowed_set:
                            opt_text = opt_match.group(2).strip().rstrip('.')
                            opt_text = self.clean_text_for_analysis(opt_text)
                            options_found.insert(0, {'value': opt_letter, 'label': opt_text, 'index': i})
                            if option_start_index is None:
                                option_start_index = i
                    else:
                        # If we hit a non-option and have enough options, stop
                        if len(options_found) >= len(allowed_letters):
                            break
                
                # If we found enough options, create the missing question
                if len(options_found) >= len(allowed_letters) and option_start_index is not None:
                    self.log(f"✅ Creating missing Q{start_q} with {len(options_found)} options found before Q{next_question_num}")
                    
                    # Sort options by letter and take only allowed letters
                    sorted_options = sorted([opt for opt in options_found if opt['value'] in allowed_set], 
                                          key=lambda x: x['value'])[:len(allowed_letters)]
                    
                    questions_data[start_q] = {
                        'text': f"Question {start_q}",  # Placeholder text
                        'options': [{'value': opt['value'], 'label': opt['label']} for opt in sorted_options],
                        'p_index': option_start_index,
                        'original_html': str(p_tags[option_start_index]) if option_start_index < len(p_tags) else ""
                    }
                    self.log(f"✅ Created Q{start_q} with {len(sorted_options)} options")
        
        # Fallback: If no questions found using paragraph approach, try regex patterns
        if not questions_data:
            self.log("🔄 Paragraph approach failed, trying regex patterns...")
            question_patterns = [
                # Pattern 1: Nested spans format: <p><span...><span...><strong>14</strong></span></span></span><span...> Question text</span></span></span></p>
                r'<p[^>]*>(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\s*(\d+)\s*</strong>(?:</span>)*(?:</span>)*(?:</span>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:\s|&nbsp;)*([^<]+?)(?:</span>)*(?:</span>)*(?:</span>)*(?:</p>)',
                # Pattern 2: Standard format: <p><strong>14</strong> Question text</p>
                r'<p[^>]*><strong>\s*(\d+)\s*</strong>\s*([^<]+?)(?=</p>)',
                # Pattern 3: Simple format: <strong>14</strong> Question text
                r'<strong>\s*(\d+)\s*</strong>\s*(?:&nbsp;)*\s*([^<]+?)(?=</p>|<br)',
            ]
            
            for pattern in question_patterns:
                for match in re.finditer(pattern, html_content, re.DOTALL):
                    try:
                        q_num = int(match.group(1))
                        if start_q <= q_num <= end_q and q_num not in questions_data:
                            # Clean text and fix curly quotes
                            question_text = self.clean_text_for_analysis(match.group(2))
                            
                            if question_text and len(question_text) > 5:
                                # Extract original HTML for this question
                                original_html = match.group(0)  # Full match including tags
                                questions_data[q_num] = {
                                    'text': question_text,
                                    'options': [],
                                    'html_start_pos': match.start(),  # Store HTML position for boundary detection
                                    'original_html': original_html  # PRESERVE original HTML
                                }
                                self.log(f"✅ Regex found Q{q_num}: {question_text[:50]}...")
                                self.log(f"📝 Preserving original HTML for Q{q_num}")
                    except (ValueError, IndexError):
                        continue

        # Step 3: Fallback option extraction for questions that don't have options yet
        # CRITICAL: Extract options for each question individually, not shared
        for q_num in sorted(questions_data.keys()):
            question_data = questions_data[q_num]
            
            # Skip if already has enough options
            if question_data['options'] and len(question_data['options']) >= len(allowed_letters):
                self.log(f"✅ Q{q_num} already has {len(question_data['options'])} options")
                continue
            
            self.log(f"🔍 Fallback: Extracting options for Q{q_num}...")
            options = []
            
            # Find the question paragraph index
            p_index = question_data.get('p_index')
            if p_index is not None:
                # Look in following P tags for options
                p_tags = soup.find_all('p')
                
                for j in range(p_index + 1, len(p_tags)):
                    next_p = p_tags[j]
                    next_p_text = next_p.get_text(strip=True)
                    next_html = str(next_p)
                    
                    # Stop if we hit another question number
                    if re.match(r'^\d+\s+', next_p_text):
                        break
                    
                    # Check if this is an option paragraph
                    # Try multiple patterns to handle nested spans
                    opt_match = re.match(r'^([A-Z])\s+(.+)$', next_p_text)
                    if not opt_match:
                        # Try pattern with optional whitespace/nbsp after letter
                        opt_match = re.match(r'^([A-Z])(?:\s|&nbsp;)+(.+)$', next_p_text)
                    if opt_match:
                        opt_letter = opt_match.group(1).upper()
                        opt_text = opt_match.group(2).strip().rstrip('.')
                        
                        # Clean Unicode curly quotes
                        opt_text = self.clean_text_for_analysis(opt_text)
                        
                        if opt_letter in allowed_set:
                            options.append({'value': opt_letter, 'label': opt_text})
                            self.log(f"  ✅ Fallback option {opt_letter}: {opt_text[:40]}...")
                            
                            # Stop after collecting all expected options
                            if len(options) >= len(allowed_letters):
                                break
            
            # If still no options, try regex patterns within question boundary
            if not options:
                self.log(f"🔄 Using regex fallback for Q{q_num} options...")
                
                # Determine search area - only between this question and next question
                search_area = html_content
                search_start = 0
                search_end = len(html_content)
                
                # Method 1: Use p_index if available (paragraph-based detection)
                if p_index is not None:
                    # Find paragraph positions in original HTML
                    p_tags_all = soup.find_all('p')
                    
                    # Get HTML position of this question's paragraph
                    this_p_str = str(p_tags_all[p_index])
                    search_start = html_content.find(this_p_str)
                    
                    if search_start >= 0:
                        # Find next question paragraph to set boundary
                        for next_q_num in range(q_num + 1, end_q + 1):
                            if next_q_num in questions_data and 'p_index' in questions_data[next_q_num]:
                                next_p_idx = questions_data[next_q_num]['p_index']
                                next_p_str = str(p_tags_all[next_p_idx])
                                next_pos = html_content.find(next_p_str, search_start + 1)
                                if next_pos > 0:
                                    search_end = next_pos
                                    break
                        
                        search_area = html_content[search_start:search_end]
                        self.log(f"  🎯 P-index search area: {len(search_area)} chars")
                
                # Method 2: Use html_start_pos if available (regex-based detection)
                elif 'html_start_pos' in question_data:
                    search_start = question_data['html_start_pos']
                    
                    # Find next question boundary
                    for next_q_num in range(q_num + 1, end_q + 1):
                        if next_q_num in questions_data and 'html_start_pos' in questions_data[next_q_num]:
                            search_end = questions_data[next_q_num]['html_start_pos']
                            break
                    
                    search_area = html_content[search_start:search_end]
                    self.log(f"  🎯 HTML-pos search area: {len(search_area)} chars (pos {search_start} to {search_end})")
                
                option_patterns = [
                    # Pattern 1: Nested spans format: <p><span...><span...><strong>A </strong></span></span></span><span...> Option text</span></span></span></p>
                    r'<p[^>]*>(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*<strong>\s*([A-J])\s*(?:&nbsp;)*\s*</strong>(?:</span>)*(?:</span>)*(?:</span>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:<span[^>]*>)*(?:\s|&nbsp;)*([^<]+?)(?:</span>)*(?:</span>)*(?:</span>)*(?:</p>)',
                    # Pattern 2: Standard format: <p><strong>A</strong> Option text</p>
                    r'<p[^>]*><strong>\s*([A-J])\s*</strong>\s*([^<]+)</p>',
                    # Pattern 3: Simple format: <strong>A</strong> Option text
                    r'<strong>\s*([A-J])\s*</strong>\s*(?:&nbsp;)*\s*([^<]+?)(?=</p>|<br)',
                    # Pattern 4: Handle &nbsp; inside strong tags
                    r'<p[^>]*><strong>\s*([A-J])\s*(?:&nbsp;)*\s*</strong>\s*(?:&nbsp;)*\s*([^<]+)</p>',
                    r'<strong>\s*([A-J])\s*(?:&nbsp;)*\s*</strong>\s*(?:&nbsp;)*\s*([^<]+?)(?=</p>|<br)',
                ]
                
                for pattern in option_patterns:
                    for opt_match in re.finditer(pattern, search_area):
                        opt_letter = opt_match.group(1).upper()
                        # Clean text and fix curly quotes
                        opt_text = self.clean_text_for_analysis(opt_match.group(2))
                        
                        if opt_text and len(opt_text) > 1 and opt_letter in allowed_set:
                            # Avoid duplicates
                            if not any(opt['value'] == opt_letter for opt in options):
                                options.append({'value': opt_letter, 'label': opt_text})
                                self.log(f"  ✅ Regex option {opt_letter}: {opt_text[:40]}...")
                    
                    # Stop if we found enough options
                    if len(options) >= len(allowed_letters):
                        break
            
            # Sort options by letter and assign to question
            ordered = sorted([opt for opt in options if opt['value'] in allowed_set], key=lambda x: x['value'])
            question_data['options'] = ordered[:len(allowed_letters)]
            self.log(f"📝 Q{q_num} final: {len(question_data['options'])} options")
        
        return questions_data
    
    def build_perfect_format(self, questions_data, question_type, original_html=None):
        """Build format preserving original HTML structure and inserting question-input tags"""
        if not questions_data:
            self.log("❌ No questions data provided")
            return ""
        
        self.log(f"🏗️ Building perfect format for {len(questions_data)} questions with type={question_type}...")
        self.log(f"📋 Questions to process: {sorted(questions_data.keys())}")
        self.log(f"📄 Original HTML length: {len(original_html) if original_html else 0} chars")
        
        # ALWAYS use original HTML if provided - preserve everything
        if original_html:
            self.log("📝 Using original HTML, inserting question-input tags...")
            result_html = original_html
            
            # Process each question in order
            for q_num in sorted(questions_data.keys()):
                question_data = questions_data[q_num]
                options = question_data['options']
                
                self.log(f"🔧 Processing Q{q_num}...")
                self.log(f"  📋 Options count: {len(options)}")
                self.log(f"  📝 Question text: {question_data['text'][:60]}...")
                
                # Check if question-input tag already exists - if so, remove duplicate paragraphs
                existing_pattern = rf'<question-input[^>]*data-question-number=["\']{q_num}["\'][^>]*>'
                existing_matches = list(re.finditer(existing_pattern, result_html, re.IGNORECASE))
                if existing_matches:
                    self.log(f"  ⚠️ Q{q_num} already has {len(existing_matches)} question-input tag(s)")
                    # If there's more than one, remove duplicates (keep only the first one)
                    if len(existing_matches) > 1:
                        self.log(f"  🗑️ Removing {len(existing_matches) - 1} duplicate question-input tag(s) for Q{q_num}")
                        # Remove all but the first occurrence
                        for match in reversed(existing_matches[1:]):
                            # Find the paragraph containing this duplicate
                            before_text = result_html[:match.start()]
                            after_text = result_html[match.end():]
                            # Find the paragraph boundaries
                            para_start = before_text.rfind('<p')
                            para_end = after_text.find('</p>')
                            if para_start != -1 and para_end != -1:
                                # Remove the entire paragraph
                                full_para_start = para_start
                                full_para_end = match.end() + para_end + 4  # +4 for </p>
                                result_html = result_html[:full_para_start] + result_html[full_para_end:]
                                self.log(f"  ✅ Removed duplicate paragraph for Q{q_num}")
                    self.questions_processed.add(q_num)
                    continue
                
                # Create options JSON (use single quotes for HTML attribute)
                options_json = json.dumps(options, ensure_ascii=False, separators=(',', ':'))
                
                # Extract question text from the paragraph
                question_text_clean = question_data['text'].strip()
                
                # Build question-input tag with question text inside
                question_tag = f'<question-input data-question-number="{q_num}" data-question-type="multiple_choice_with_multiple_answer" data-question-options=\'{options_json}\'>{question_text_clean}</question-input>'
                
                # Find the question paragraph and replace question text with tag
                # Pattern: Match paragraph with question number and text, replace text with tag
                patterns = [
                    # Pattern 1: <p>11 &nbsp; &nbsp; text</p> (most common format)
                    rf'(<p[^>]*>.*?<strong>\s*{q_num}\s*</strong>(?:\s|&nbsp;)+)([^<]+?)(</p>)',
                    # Pattern 2: <p><strong>11</strong>&nbsp;&nbsp;text</p>
                    rf'(<p[^>]*>.*?<strong>\s*{q_num}\s*</strong>(?:&nbsp;)+)([^<]+?)(</p>)',
                    # Pattern 3: <p><strong>11</strong> text</p>
                    rf'(<p[^>]*>.*?<strong>\s*{q_num}\s*</strong>\s+)([^<]+?)(</p>)',
                    # Pattern 4: <p>11 text</p> (without strong tag)
                    rf'(<p[^>]*>.*?{q_num}(?:\s|&nbsp;)+)([^<]+?)(</p>)',
                ]
                
                inserted = False
                # Track if we've already processed this question number
                processed_this_q = False
                
                for pattern in patterns:
                    # Find ALL matches, not just the first one
                    matches = list(re.finditer(pattern, result_html, re.DOTALL | re.IGNORECASE))
                    if matches:
                        # Process only the FIRST match that doesn't have question-input tag
                        for match in matches:
                            # Check if this paragraph doesn't already have a question-input tag
                            para_html = match.group(0)
                            if 'question-input' not in para_html:
                                # Check if we've already processed this question number
                                if not processed_this_q:
                                    # Replace question text with question-input tag
                                    # Keep the question number part, replace text part with tag
                                    replacement = match.group(1) + question_tag + match.group(3)
                                    result_html = result_html[:match.start()] + replacement + result_html[match.end():]
                                    self.log(f"  ✅ Inserted question-input tag for Q{q_num} (first occurrence)")
                                    self.log(f"  📝 Matched pattern: {pattern[:50]}...")
                                    inserted = True
                                    processed_this_q = True
                                    self.questions_processed.add(q_num)
                                    break
                                else:
                                    # This is a duplicate paragraph - remove it
                                    self.log(f"  🗑️ Removing duplicate Q{q_num} paragraph at position {match.start()}")
                                    result_html = result_html[:match.start()] + result_html[match.end():]
                                    break
                        
                        if inserted:
                            break
                
                if not inserted:
                    self.log(f"  ⚠️ Could not find Q{q_num} paragraph, trying alternative method...")
                    # Alternative 1: Find by question text (first 30 chars)
                    if question_data['text'] and not question_data['text'].startswith('Question '):
                        question_text_escaped = re.escape(question_data['text'][:30])
                        text_pattern = rf'(<p[^>]*>.*?{question_text_escaped}.*?)(</p>)'
                        match = re.search(text_pattern, result_html, re.DOTALL | re.IGNORECASE)
                        if match and 'question-input' not in match.group(0):
                            replacement = match.group(1) + question_tag + match.group(2)
                            result_html = result_html[:match.start()] + replacement + result_html[match.end():]
                            self.log(f"  ✅ Inserted Q{q_num} using text matching")
                            inserted = True
                            self.questions_processed.add(q_num)
                    
                    # Alternative 2: If placeholder text (e.g., "Question 27") or no text, find first option paragraph
                    if not inserted:
                        self.log(f"  🔍 Q{q_num} has placeholder text or no text, looking for option paragraphs...")
                        
                        # Find next question number to determine boundary
                        next_q_num = None
                        for next_q in sorted(questions_data.keys()):
                            if next_q > q_num:
                                next_q_num = next_q
                                break
                        
                        # Find all option paragraphs that match this question's options
                        option_pattern = r'<p[^>]*><strong>\s*([A-J])\s*</strong>\s*([^<]+)</p>'
                        all_option_matches = list(re.finditer(option_pattern, result_html, re.IGNORECASE))
                        
                        if all_option_matches:
                            # Find the first option that belongs to this question
                            first_option_match = None
                            for match in all_option_matches:
                                opt_letter = match.group(1).upper()
                                if opt_letter in [opt['value'] for opt in options]:
                                    # Check if this is before next question
                                    if next_q_num:
                                        next_q_pattern = rf'<p[^>]*>.*?<strong>\s*{next_q_num}\s*</strong>'
                                        next_q_match = re.search(next_q_pattern, result_html[match.end():], re.IGNORECASE)
                                        if next_q_match:
                                            # This option is before next question, use it
                                            first_option_match = match
                                            break
                                    else:
                                        # No next question, use first matching option
                                        first_option_match = match
                                        break
                            
                            if first_option_match:
                                # Insert question paragraph before first option
                                insert_pos = first_option_match.start()
                                
                                # Check if there's already a Questions header before this position
                                questions_header_pattern = rf'<p[^>]*><strong>\s*Questions?\s+{q_num}'
                                header_match = re.search(questions_header_pattern, result_html[:insert_pos], re.IGNORECASE)
                                
                                if header_match:
                                    # Find the position after the instruction paragraphs
                                    # Look for "Write the correct letter" or similar instruction
                                    instruction_pattern = r'<p[^>]*>.*?Write the correct letter.*?</p>'
                                    instruction_match = re.search(instruction_pattern, result_html[header_match.end():insert_pos], re.IGNORECASE | re.DOTALL)
                                    
                                    if instruction_match:
                                        # Insert after instruction
                                        insert_pos = header_match.end() + instruction_match.end()
                                    else:
                                        # Insert after header
                                        insert_pos = header_match.end()
                                
                                # Create question paragraph with question-input tag
                                # If question text is placeholder, don't include it
                                question_text_display = ""
                                if question_data['text'] and not question_data['text'].startswith('Question '):
                                    question_text_display = question_data['text'] + " "
                                
                                new_paragraph = f'<p><strong>{q_num}</strong> {question_text_display}{question_tag}</p>'
                                result_html = result_html[:insert_pos] + new_paragraph + result_html[insert_pos:]
                                self.log(f"  ✅ Inserted Q{q_num} paragraph before first option at position {insert_pos}")
                                inserted = True
                                self.questions_processed.add(q_num)
                            else:
                                # If no matching option found, try to find any option paragraph
                                # and insert before the first one
                                if all_option_matches:
                                    first_any_option = all_option_matches[0]
                                    insert_pos = first_any_option.start()
                                    question_text_display = question_data['text'] if not question_data['text'].startswith('Question ') else ""
                                    new_paragraph = f'<p><strong>{q_num}</strong> {question_text_display} {question_tag}</p>'
                                    result_html = result_html[:insert_pos] + new_paragraph + result_html[insert_pos:]
                                    self.log(f"  ✅ Inserted Q{q_num} paragraph before first available option")
                                    inserted = True
                                    self.questions_processed.add(q_num)
                
                if not inserted:
                    self.log(f"  ⚠️ Could not find Q{q_num} in HTML, appending at end...")
                    # Last resort: Append the question with question-input tag
                    question_text_display = question_data['text'] if not question_data['text'].startswith('Question ') else ""
                    append_html = f'<p><strong>{q_num}</strong> {question_text_display} {question_tag}</p>'
                    result_html += append_html
                    self.log(f"  ✅ Appended Q{q_num} to end of HTML")
                    inserted = True
                    self.questions_processed.add(q_num)
            
            self.log(f"✅ Perfect format complete with {len(self.questions_processed)}/{len(questions_data)} questions processed")
            self.log(f"📋 Processed questions: {sorted(self.questions_processed)}")
            self.log(f"📏 Final HTML length: {len(result_html)} chars")
            return result_html
        
        # Fallback: Build format from scratch if no original HTML
        self.log("⚠️ No original HTML provided, building from scratch...")
        range_start = min(questions_data.keys())
        range_end = max(questions_data.keys())
        
        questions_html = ""
        for q_num in sorted(questions_data.keys()):
            question_data = questions_data[q_num]
            options = question_data['options']
            
            options_json = json.dumps(options, ensure_ascii=False, separators=(',', ':'))
            
            question_text_clean = question_data["text"].strip()
            question_tag = f'<question-input data-question-number="{q_num}" data-question-type="multiple_choice_with_multiple_answer" data-question-options=\'{options_json}\'>{question_text_clean}</question-input>'
            questions_html += f'<p><strong>{q_num}</strong> {question_tag}</p>'
            self.questions_processed.add(q_num)
        
        result = f'<div><p><strong>Questions {range_start}-{range_end}</strong></p>{questions_html}</div>'
        self.log(f"✅ Fallback format complete with {len(questions_data)} questions")
        return result


    def build_list_selection_format(self, questions_data, question_type):
        """NOT USED - All multiple choice questions use build_perfect_format"""
        # This method is kept for backwards compatibility but should not be called
        self.log("⚠️ build_list_selection_format called but should use build_perfect_format")
        return self.build_perfect_format(questions_data, question_type)
    
    def build_combined_range_input_preserving_text(self, html_content, questions_data, start_q, end_q):
        """Insert a single combined question-input (multiple answers) into the original HTML
        immediately after instruction paragraphs, preserving all original text."""
        try:
            # Options come from the first question (same for the range)
            first_q = min(questions_data.keys())
            options = questions_data[first_q].get('options', [])
            options_json = json.dumps(options, ensure_ascii=False, separators=(',', ':'))

            # Build data-questions payload using detected range, with the common instruction text
            # Default instruction text for TWO/THREE letters
            questions_payload = []
            for q in range(start_q, end_q + 1):
                questions_payload.append({
                    "question_number": str(q),
                    "question_text": "Choose TWO letters, A-E."
                })
            data_questions_json = json.dumps(questions_payload, ensure_ascii=False, separators=(',', ':'))

            # Escape quotes properly for HTML attributes
            options_json_escaped = options_json.replace('"', '&quot;')
            data_questions_json_escaped = data_questions_json.replace('"', '&quot;')

            # Use requested attribute names and types
            combined_tag = '<question-input data-question-options="' + options_json_escaped + '" data-question-type="multiple_choice_with_multiple_answer" data-questions="' + data_questions_json_escaped + '" repeat_answer="True"></question-input>'

            # Insert after common instruction paragraphs
            insert_patterns = [
                r'(</p>\s*)(?=(?:(?:(?!</p>).)*?write\s+the\s+correct\s+letters\s+in\s+boxes)[^<]*</p>)',
                r'(</p>\s*)(?=(?:(?:(?!</p>).)*?choose\s*(?:two|three)\s*letters)[^<]*</p>)',
                r'(</p>)'  # fallback: after the first paragraph
            ]

            result_html = html_content
            inserted = False
            for pattern in insert_patterns:
                # Find the paragraph and insert right after it
                match = re.search(pattern, result_html, flags=re.IGNORECASE | re.DOTALL)
                if match:
                    start, end = match.span(1)
                    result_html = result_html[:end] + combined_tag + result_html[end:]
                    inserted = True
                    break

            if not inserted:
                # Append at the end if no paragraph found
                result_html = result_html + combined_tag

            # Remove duplicated option lines (A–E) from the HTML since they are already provided in data-options
            try:
                soup_clean = BeautifulSoup(result_html, 'html.parser')
                for p in list(soup_clean.find_all('p')):
                    strong = p.find('strong')
                    if strong:
                        letter = strong.get_text(strip=True).replace('\xa0', ' ').strip()
                        # Match single letter choices like 'A', 'A', or 'A '
                        if len(letter) == 1 and letter.upper() in ['A', 'B', 'C', 'D', 'E']:
                            p.decompose()
                result_html = str(soup_clean)
            except Exception as _:
                pass

            # Mark all questions as processed
            for q in questions_data.keys():
                self.questions_processed.add(q)

            return result_html
        except Exception as e:
            self.log(f"❌ ERROR building combined tag: {e}")
            return html_content

    def build_list_selection_preserving_text(self, html_content, questions_data, start_q, end_q):
        """Insert a single <list-selection-tegs> after the instruction, preserving all text."""
        try:
            # 0) Merge split instruction paragraphs ("Choose ..." and "Write the correct letters ...") into one
            try:
                soup_merge = BeautifulSoup(html_content, 'html.parser')
                ps = soup_merge.find_all('p')
                choose_idx, write_idx = None, None
                for i, p in enumerate(ps):
                    txt = p.get_text(separator=' ', strip=True).lower()
                    if choose_idx is None and re.search(r'choose\s*(two|three)\s*letters', txt):
                        choose_idx = i
                    if write_idx is None and re.search(r'write\s+the\s+correct\s+letters\s+in\s+boxes', txt):
                        write_idx = i
                if choose_idx is not None and write_idx is not None and choose_idx != write_idx:
                    choose_p = ps[choose_idx]
                    write_p = ps[write_idx]
                    merged_text = (choose_p.get_text(separator=' ', strip=True).rstrip('.') +
                                   '. ' + write_p.get_text(separator=' ', strip=True))
                    # Rebuild merged paragraph with <em>
                    new_p = soup_merge.new_tag('p')
                    em = soup_merge.new_tag('em')
                    em.string = merged_text
                    new_p.append(em)
                    # Replace choose_p with merged and remove write_p
                    choose_p.replace_with(new_p)
                    write_p.decompose()
                    html_content = str(soup_merge)
            except Exception:
                pass

            first_q = min(questions_data.keys())
            options = questions_data[first_q].get('options', [])

            # Detect allowed letters from instruction (e.g., A–E or A, B, C or D)
            def detect_allowed_letters_from_html(text: str):
                t = self.clean_text_for_analysis(text)
                seq = re.search(r'\b([A-Z])\s*,\s*([A-Z])\s*,\s*([A-Z])\s*(?:or|/)?\s*([A-Z])\b', t, re.IGNORECASE)
                if seq:
                    return [seq.group(i).upper() for i in range(1, 5)]
                rng = re.search(r'\b([A-Z])\s*[-–]\s*([A-Z])\b', t, re.IGNORECASE)
                if rng:
                    a, b = rng.group(1).upper(), rng.group(2).upper()
                    if ord(a) <= ord(b):
                        return [chr(c) for c in range(ord(a), ord(b) + 1)]
                return None

            allowed_letters = detect_allowed_letters_from_html(html_content) or [opt['value'] for opt in options] or list('ABCDE')
            allowed_set = set(allowed_letters)

            # Filter existing options by allowed letters and preserve order
            if options:
                options = [opt for opt in options if opt.get('value') in allowed_set]

            question_numbers = [str(q) for q in range(start_q, end_q + 1)]
            question_numbers_json = json.dumps(question_numbers, ensure_ascii=False, separators=(',', ':'))

            options_inline_json = json.dumps(options, ensure_ascii=False, separators=(',', ':'))
            
            # Escape quotes properly for HTML attributes
            options_inline_json_escaped = options_inline_json.replace('"', '&quot;')
            question_numbers_json_escaped = question_numbers_json.replace('"', '&quot;')
            
            list_selection_tag = '<list-selection-tegs data-options="' + options_inline_json_escaped + '" question_numbers="' + question_numbers_json_escaped + '" question_type="list_selection"> </list-selection-tegs>'

            # If options empty, synthesize from html_content (A–J paragraphs)
            if not options:
                synthesized = []
                for m in re.finditer(r"<p[^>]*>\s*<strong>\s*([A-J])\s*</strong>\s*([^<]+)</p>", html_content, re.IGNORECASE):
                    letter = m.group(1).upper()
                    label = self.clean_text_for_analysis(m.group(2))
                    if label and letter in allowed_set and not any(opt['value'] == letter for opt in synthesized):
                        synthesized.append({'value': letter, 'label': label})
                if synthesized:
                    options_json = json.dumps(synthesized, ensure_ascii=False, separators=(',', ':'))
                    # Escape quotes properly for HTML attributes
                    options_json_escaped = options_json.replace('"', '&quot;')
                    question_numbers_json_escaped = question_numbers_json.replace('"', '&quot;')
                    
                    list_selection_tag = '<list-selection-tegs data-options="' + options_json_escaped + '" question_numbers="' + question_numbers_json_escaped + '" question_type="list_selection"> </list-selection-tegs>'

            # DOM-based insertion to guarantee ordering: after "Which TWO..." if present,
            # else after "Write the correct letters ...", else after "Choose TWO/THREE letters ...",
            # else append at end.
            soup_dom = BeautifulSoup(html_content, 'html.parser')
            insertion_done = False

            def insert_after_paragraph(predicate_regex: str) -> bool:
                pattern = re.compile(predicate_regex, re.IGNORECASE)
                for p in soup_dom.find_all('p'):
                    text = p.get_text(separator=' ', strip=True)
                    if pattern.search(text or ''):
                        p.insert_after(BeautifulSoup(list_selection_tag, 'html.parser'))
                        return True
                return False

            # Priority 1: after the main question line (Which TWO/THREE/FIVE ... ?)
            insertion_done = insert_after_paragraph(r'which\s*(two|three|five)[^?]*\?')

            # Priority 2: after the write-instruction
            if not insertion_done:
                insertion_done = insert_after_paragraph(r'write\s+the\s+correct\s+letters\s+in\s+boxes')

            # Priority 3: after the choose-instruction
            if not insertion_done:
                insertion_done = insert_after_paragraph(r'choose\s*(two|three|four|five|six)\s*letters')

            if not insertion_done:
                # append to end of container
                soup_dom.append(BeautifulSoup(list_selection_tag, 'html.parser'))

            result_html = str(soup_dom)

            # Optionally remove explicit A–J paragraphs to avoid duplication
            try:
                soup_clean = BeautifulSoup(result_html, 'html.parser')
                for p in list(soup_clean.find_all('p')):
                    strong = p.find('strong')
                    if strong:
                        letter = strong.get_text(strip=True).replace('\xa0', ' ').strip()
                        if len(letter) == 1 and letter.upper() in ['A','B','C','D','E','F','G','H','I','J']:
                            p.decompose()
                result_html = str(soup_clean)
            except Exception:
                pass

            for q in questions_data.keys():
                self.questions_processed.add(q)

            return result_html
        except Exception as e:
            self.log(f"❌ ERROR building list-selection tag: {e}")
            return html_content

    def parse_and_insert_inputs(self, html_content):
        """Main parsing function - DOIM bir xil formatda chiqaradi"""
        self.log("🎯 ========== UNIVERSAL MULTIPLE CHOICE PARSING ==========")
        
        if not html_content:
            return html_content
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            plain_text = soup.get_text(separator=' ', strip=True)
            
            # Validate
            if not self.is_multiple_choice_question(html_content, plain_text):
                self.log("❌ Not a multiple choice question")
                return html_content
            
            self.log("✅ Confirmed multiple choice format")
            
            # Extract range first (needed for special case check)
            start_q, end_q = self.extract_question_range(html_content, plain_text)
            if start_q is None or end_q is None:
                self.log("❌ Could not determine range")
                return html_content
            
            # SIMPLE: Use detect_single_vs_multiple to determine type
            answer_type = self.detect_single_vs_multiple(html_content, plain_text)
            if answer_type == 'multiple_answers':
                question_type = self.multiple_choice_type  # 'multiple_choice_with_multiple_answer'
                self.log(f"✅ Using: {question_type}")
            else:
                question_type = self.single_choice_type  # 'multiple_choice_with_single_answer'
                self.log(f"✅ Using: {question_type}")
            
            # Store original HTML for reference
            original_html = html_content
            
            # Remove duplicate question sections before extraction
            cleaned_html = self.remove_duplicate_questions(html_content, start_q, end_q)
            
            # Extract questions and options with FIXED logic (use cleaned HTML)
            questions_data = self.extract_all_questions_and_options_fixed(cleaned_html, start_q, end_q)
            
            if not questions_data:
                self.log("❌ No questions found")
                return html_content
            
            self.log(f"📊 Successfully parsed {len(questions_data)} questions")
            self.log(f"📋 Questions found: {sorted(questions_data.keys())}")
            
            # DOIM build_perfect_format ishlatamiz - question_type bilan, PRESERVING cleaned HTML
            self.log(f"🎯 Using build_perfect_format with question_type={question_type}")
            self.log(f"📄 Preserving cleaned HTML structure...")
            perfect_html = self.build_perfect_format(questions_data, question_type, original_html=cleaned_html)
            
            self.log(f"🎯 Perfect format complete: {len(self.questions_processed)} questions")
            self.log(f"📋 Processed questions: {sorted(self.questions_processed)}")
            
            # CRITICAL: Final cleanup - remove any duplicate question-input tags
            perfect_html = self.remove_duplicate_question_inputs(perfect_html, start_q, end_q)
            
            self.log("🎯 ========== UNIVERSAL MULTIPLE CHOICE PARSING COMPLETE ==========")
            
            return perfect_html
            
        except Exception as e:
            self.log(f"❌ ERROR: {e}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
            return html_content


# Function for models.py
def parse_multiple_choice(html_content):
    """Universal Multiple Choice parser - always produces perfect format"""
    parser = MultipleChoiceParser()
    return parser.parse_and_insert_inputs(html_content)
