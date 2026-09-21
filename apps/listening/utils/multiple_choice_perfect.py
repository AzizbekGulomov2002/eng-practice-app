import re
import json
from bs4 import BeautifulSoup

def parse_multiple_choice(html_content):
    """UNIVERSAL Multiple Choice parser - handles individual questions with their own options"""
    print("[PERFECT_MC] 🎯 Starting UNIVERSAL Multiple Choice parsing...")
    
    if not html_content:
        return html_content
    
    try:
        # Normalize HTML
        if not html_content.strip().startswith('<'):
            html_content = f'<div>{html_content}</div>'
        
        soup = BeautifulSoup(html_content, 'html.parser')
        plain_text = soup.get_text(separator=' ', strip=True).lower()
        
        # Detect multiple choice patterns
        multiple_choice_patterns = [
            r'choose\s+the\s+correct\s+letter',
            r'select\s+the\s+correct\s+answer',
            r'choose\s+[a-z],?\s*[a-z]\s+or\s+[a-z]',
        ]
        
        is_multiple_choice = any(re.search(pattern, plain_text) for pattern in multiple_choice_patterns)
        
        if not is_multiple_choice:
            print("[PERFECT_MC] ❌ Not a multiple choice section")
            return html_content
        
        print("[PERFECT_MC] ✅ Detected multiple choice format")
        result_html = html_content
        
        # STEP 1: Find ALL questions with pattern matching (simple and direct)
        questions_data = {}
        
        # Find all question patterns in the entire HTML
        # Pattern: "11. text" or "<strong>11. text</strong>" or "11     text" or "11 &nbsp; &nbsp; text"
        # IMPORTANT: Make sure we match the number at word boundary to avoid "n14" issues
        question_patterns = [
            r'<strong>\s*(\d+)\.\s+([^<]+?)</strong>',  # <strong>11. text</strong>
            r'(\d+)\.\s+([^<]+?)(?:<br\s*/?>|</p>|$)',  # 11. text<br /> or 11. text</p>
            r'(?<![0-9a-zA-Z])(\d+)(?:\s|&nbsp;){2,}([^<]+?)(?:<br\s*/?>|</p>|$)',  # 11     text<br /> (with word boundary)
        ]
        
        for pattern in question_patterns:
            matches = list(re.finditer(pattern, result_html, re.IGNORECASE | re.DOTALL))
            for match in matches:
                q_num = int(match.group(1))
                if 1 <= q_num <= 50:
                    question_text = match.group(2).strip()
                    # Clean text
                    question_text = re.sub(r'<[^>]+>', '', question_text)
                    question_text = re.sub(r'&nbsp;', ' ', question_text)
                    question_text = re.sub(r'\s+', ' ', question_text).strip()
                    
                    # Skip if too short or looks like option
                    if len(question_text) > 10 and q_num not in questions_data:
                        # Skip if starts with A, B, C and is short
                        first_char = question_text[0].upper()
                        if first_char in ['A', 'B', 'C'] and len(question_text) < 50:
                            if not any(word in question_text.lower() for word in ['how', 'what', 'which', 'where', 'when', 'why', 'who', 'does', 'should', 'are', 'approximately', 'items', 'tourists', 'hostel', 'residents', 'allowed']):
                                continue
                        
                        questions_data[q_num] = {
                            'text': question_text,
                            'options': [],
                            'match_start': match.start(),
                            'match_end': match.end(),
                            'full_match': match.group(0)
                        }
                        print(f"[PERFECT_MC] ✅ Found Q{q_num}: {question_text[:50]}...")
        
        # STEP 2: For each question, find its options (search after question until next question or </p>)
        sorted_questions = sorted(questions_data.keys())
        print(f"[PERFECT_MC] 📋 Processing {len(sorted_questions)} questions: {sorted_questions}")
        
        for idx, q_num in enumerate(sorted_questions):
            q_data = questions_data[q_num]
            
            # Find search area: from current question to next question or </p>
            search_start = q_data['match_end']
            if idx + 1 < len(sorted_questions):
                next_q_num = sorted_questions[idx+1]
                # Look for next question number with various patterns
                next_q_patterns = [
                    rf'<strong>\s*{next_q_num}\.\s+',
                    rf'{next_q_num}\.\s+',
                    rf'(?<![0-9]){next_q_num}(?:\s|&nbsp;){{2,}}',
                ]
                next_q_match = None
                for pattern in next_q_patterns:
                    next_q_match = re.search(pattern, result_html[search_start:], re.IGNORECASE | re.DOTALL)
                    if next_q_match:
                        break
                
                if next_q_match:
                    search_end = search_start + next_q_match.start()
                else:
                    search_end = search_start + 500  # Default 500 chars
            else:
                # Last question - search until </p> but INCLUDE the </p> tag content
                # This ensures we catch option C even if it's right before </p>
                p_end = result_html.find('</p>', search_start)
                if p_end > 0:
                    # Include content up to and including </p> to catch last option
                    search_end = p_end + 4  # Include </p> (4 chars)
                else:
                    search_end = search_start + 500
            
            search_area = result_html[search_start:search_end]
            
            # Find options in this area
            # Pattern: "A &nbsp; &nbsp; text<br />" or "&nbsp; &nbsp; &nbsp;A &nbsp; text<br />"
            # IMPORTANT: Include options that end with </p> (for last question in paragraph)
            # Handle: "C &nbsp; &nbsp; text.</p>" or "C &nbsp; &nbsp; text<br />"
            option_pattern = r'(?:\s|&nbsp;){2,}([A-Z])(?:\s|&nbsp;){2,}([^<]+?)(?:<br\s*/?>|\.?\s*</p>)'
            opt_matches = list(re.finditer(option_pattern, search_area, re.IGNORECASE | re.DOTALL))
            
            for opt_match in opt_matches:
                opt_letter = opt_match.group(1).upper()
                opt_text = opt_match.group(2).strip()
                
                # Clean option text
                opt_text = re.sub(r'<[^>]+>', '', opt_text)
                opt_text = re.sub(r'&nbsp;', ' ', opt_text)
                opt_text = re.sub(r'\s+', ' ', opt_text).strip().rstrip('.')
                
                # Skip if it's a question text (contains "which", "what", etc.)
                if any(word in opt_text.lower() for word in ['which', 'what', 'how', 'does the speaker', 'talk about', 'following features']):
                    continue
                
                if opt_text and len(opt_text) > 1:
                    existing_letters = [opt['value'] for opt in q_data['options']]
                    if opt_letter not in existing_letters:
                        q_data['options'].append({
                            'value': opt_letter,
                            'label': opt_text
                        })
                        print(f"[PERFECT_MC]   📋 Added option {opt_letter} to Q{q_num}: {opt_text[:40]}...")
            
            print(f"[PERFECT_MC] ✅ Q{q_num} has {len(q_data['options'])} options")
        
        # STEP 3: Replace questions with question-input tags (in reverse order to maintain positions)
        for q_num in reversed(sorted_questions):
            q_data = questions_data[q_num]
            
            # Allow 1-6 options for multiple choice (some questions might have 1, 2, 3, 4, 5, or 6 options)
            # IMPORTANT: Even if options are not detected, we should still create the question-input tag
            # The options might be detected later or the question might be incomplete
            if len(q_data['options']) < 1:
                print(f"[PERFECT_MC] ⚠️ Skipping Q{q_num} - no options found")
                print(f"[PERFECT_MC]   Question text: {q_data['text'][:50]}...")
                print(f"[PERFECT_MC]   Match: {q_data['full_match'][:100]}...")
                continue
            
            if len(q_data['options']) < 2:
                print(f"[PERFECT_MC] ⚠️ WARNING: Q{q_num} has only {len(q_data['options'])} options, but continuing anyway")
                                    
            # Create question-input tag - EXACT FORMAT: q_num + spaces + question_text BEFORE tag, question_text INSIDE tag
            options_json = json.dumps(q_data['options'], ensure_ascii=False, separators=(',', ':'))
            question_text = q_data["text"]
            # Format: "11     Question text<question-input>Question text</question-input><br />"
            question_input_tag = f'<question-input data-question-number="{q_num}" data-question-type="multiple_choice_with_multiple_answer" data-question-options=\'{options_json}\'>{question_text}</question-input>'
            
            # Find the exact match in HTML (handle all formats)
            full_match = q_data['full_match']
            match_start = q_data['match_start']
            match_end = q_data['match_end']
            
            # Use the question number we already have - it's guaranteed to be correct
            # Format: "14     " (number + 5 spaces)
            prefix = f'{q_num}     '
            
            # Check if this is the last question in the paragraph (ends with </p>)
            # Simple check: if this is the last question in sorted_questions, it's likely the last in paragraph
            # Also check if there's a </p> tag after this question's options
            is_last_question = False
            if q_num == sorted_questions[-1]:  # This is the last question in the section
                # Check if there's </p> after this question (look ahead for </p>)
                text_after_match = result_html[match_end:match_end+500]
                # Look for </p> before any next section starts (like "Questions 15-17")
                p_close_pos = text_after_match.find('</p>')
                next_section_pos = text_after_match.find('Questions')
                
                # If </p> is found and (no next section OR </p> comes before next section), it's the last
                if p_close_pos > 0 and (next_section_pos < 0 or p_close_pos < next_section_pos):
                    is_last_question = True
            
            # IMPORTANT: Replace the ENTIRE original match from match_start to match_end
            # The full_match contains the number and question text
            # We create new content with: "11     Question text<question-input>...</question-input><br />"
            # This ensures question text appears BEFORE the tag (as required)
            
            # Format: "14     Question text<question-input>Question text</question-input><br />" or "</p>"
            new_content = prefix + question_text + question_input_tag
            if is_last_question:
                # Last question ends with </p> - don't add <br />
                # The </p> tag will remain after options are removed
                pass
            else:
                # Not last question, add <br />
                new_content += '<br />'
            
            # Replace from match_start to match_end (this replaces the original question pattern)
            # The new_content includes the number, spaces, question text, and tag
            result_html = result_html[:match_start] + new_content + result_html[match_end:]
            
            # Now remove options (find them again after replacement)
            insert_pos = match_start + len(new_content)
            remaining_text = result_html[insert_pos:]
            
            # Find next question or </p>
            next_q_match = re.search(r'<strong>\s*\d+\.\s+|\d+\.\s+|<question-input', remaining_text, re.IGNORECASE)
            p_end_match = re.search(r'</p>', remaining_text, re.IGNORECASE)
            
            search_end = len(remaining_text)
            if next_q_match:
                search_end = min(search_end, next_q_match.start())
            if p_end_match:
                search_end = min(search_end, p_end_match.start())
            
            # Remove options
            option_pattern = r'(?:\s|&nbsp;){2,}([A-Z])(?:\s|&nbsp;){2,}([^<]+?)(?:<br\s*/?>|</p>|\.\s*</p>)'
            opt_matches = list(re.finditer(option_pattern, remaining_text[:search_end], re.IGNORECASE))
            
            collected_letters = [opt['value'] for opt in q_data['options']]
            options_to_remove = []
            
            for opt_match in opt_matches:
                opt_letter = opt_match.group(1).upper()
                if opt_letter in collected_letters:
                    opt_start = insert_pos + opt_match.start()
                    opt_end = insert_pos + opt_match.end()
                    options_to_remove.append((opt_start, opt_end))
            
            # Remove options in reverse order
            for opt_start, opt_end in reversed(options_to_remove):
                result_html = result_html[:opt_start] + result_html[opt_end:]
            
            print(f"[PERFECT_MC] ✅ Replaced Q{q_num} (removed {len(options_to_remove)} options)")
        
        # FINAL CLEANUP: Remove any remaining duplicate options ONLY
        # DO NOT remove question text - our format intentionally has question text before the tag
        # Our format is: "11     Question text<question-input>Question text</question-input>"
        # The question text before the tag is CORRECT and should NOT be removed
                    
        # Remove duplicate option lines after question-input tags
        q_input_pattern = r'<question-input[^>]*data-question-number="(\d+)"[^>]*>'
        q_input_matches = list(re.finditer(q_input_pattern, result_html))
        
        for q_input_match in reversed(q_input_matches):
            q_num = int(q_input_match.group(1))
            q_input_end = q_input_match.end()
            
            if q_num in questions_data:
                collected_letters = [opt['value'] for opt in questions_data[q_num]['options']]
                search_text = result_html[q_input_end:q_input_end + 300]
                
                option_pattern = r'(?:\s|&nbsp;){2,}([A-Z])(?:\s|&nbsp;){2,}([^<]+?)(?:<br\s*/?>|</p>)'
                opt_matches = list(re.finditer(option_pattern, search_text, re.IGNORECASE))
                
                for opt_match in reversed(opt_matches):
                    opt_letter = opt_match.group(1).upper()
                    if opt_letter in collected_letters:
                        opt_start = q_input_end + opt_match.start()
                        opt_end = q_input_end + opt_match.end()
                        result_html = result_html[:opt_start] + result_html[opt_end:]
                        print(f"[PERFECT_MC] 🧹 Removed duplicate option {opt_letter} for Q{q_num}")
        
        print("[PERFECT_MC] ✅ UNIVERSAL parsing complete!")
        return result_html
        
    except Exception as e:
        print(f"[PERFECT_MC] ❌ Error: {e}")
        import traceback
        print(f"[PERFECT_MC] ❌ Traceback: {traceback.format_exc()}")
        return html_content
