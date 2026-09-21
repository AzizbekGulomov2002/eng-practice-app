import re
import json
from bs4 import BeautifulSoup

def parse_multiple_choice(html_content):
    """UNIVERSAL Multiple Choice parser - handles individual questions with their own options"""
    print("[PERFECT_MC] 🎯 Starting UNIVERSAL Multiple Choice parsing...")
    
    if not html_content:
        return html_content
    
    try:
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
        
        # Parse questions and options in sequential order
        result_html = html_content
        p_tags = soup.find_all('p')
        
        questions_with_options = {}
        current_question = None
        
        # STEP 1: Sequential parsing to associate questions with their options
        for i, p in enumerate(p_tags):
            p_text = p.get_text(strip=True)
            p_html = str(p)
            
            if not p_text or len(p_text) < 2:
                continue
            
            # Check for question numbers - expanded range for flexibility
            q_num = None
            question_text = None
            
            # PRIORITY 1: Split formats (like <strong>2</strong><strong>0</strong> for Q20)
            split_match = re.search(r'<strong>\s*(\d)\s*</strong>\s*<strong>\s*(\d)\s*</strong>(?:\s|&nbsp;)*(.+)', p_html)
            if split_match:
                digit1, digit2 = split_match.group(1), split_match.group(2)
                q_num = int(digit1 + digit2)
                question_text = split_match.group(3)
                question_text = re.sub(r'<[^>]+>', '', question_text)
                question_text = re.sub(r'&nbsp;', ' ', question_text)
                question_text = re.sub(r'\s+', ' ', question_text).strip()
                print(f"[PERFECT_MC] 🎯 Detected Q{q_num} in split format: {question_text[:30]}...")
            
            # PRIORITY 2: Standard patterns: <strong>18</strong>, <strong>19</strong>, etc.
            if not q_num:
                q_match = re.search(r'<strong>\s*(\d+)\s*</strong>(?:\s|&nbsp;)*(.+)', p_html)
                if q_match:
                    try:
                        potential_q_num = int(q_match.group(1))
                        # Accept any reasonable question number (1-50)
                        if 1 <= potential_q_num <= 50:
                            q_num = potential_q_num
                            question_text = q_match.group(2)
                            question_text = re.sub(r'<[^>]+>', '', question_text)
                            question_text = re.sub(r'&nbsp;', ' ', question_text)
                            question_text = re.sub(r'\s+', ' ', question_text).strip()
                    except:
                        pass
            
            # If found question, record it and prepare for options
            if q_num:
                questions_with_options[q_num] = {
                    'text': question_text or f"Question {q_num}",
                    'options': [],
                    'paragraph_index': i
                }
                current_question = q_num
                display_text = (question_text or f"Question {q_num}")[:50]
                print(f"[PERFECT_MC] ✅ Found Q{q_num}: {display_text}...")
                continue
            
            # Check for options immediately after question - flexible letter matching
            if current_question and current_question in questions_with_options:
                # Pattern: <strong>A</strong> or <strong>A&nbsp;</strong> followed by text
                opt_match = re.search(r'<strong>\s*([A-Z])\s*(?:&nbsp;)*\s*</strong>(?:\s|&nbsp;)*(.+)', p_html)
                if opt_match:
                    opt_letter = opt_match.group(1).upper()
                    opt_text = opt_match.group(2)
                    opt_text = re.sub(r'<[^>]+>', '', opt_text)
                    opt_text = re.sub(r'&nbsp;', ' ', opt_text)
                    opt_text = re.sub(r'\s+', ' ', opt_text).strip().rstrip('.')
                    
                    # Only add if we don't already have this option letter for this question
                    existing_values = [opt['value'] for opt in questions_with_options[current_question]['options']]
                    
                    if opt_text and len(opt_text) > 1 and opt_letter not in existing_values:
                        questions_with_options[current_question]['options'].append({
                            'value': opt_letter,
                            'label': opt_text
                        })
                        print(f"[PERFECT_MC]   📋 Added {opt_letter}: {opt_text[:40]}...")
                        
                        # If we have enough options (typically 3-4), consider this question complete
                        # But don't immediately move to next - let it continue until we find next question
                        if len(questions_with_options[current_question]['options']) >= 3:
                            print(f"[PERFECT_MC]   ✅ Q{current_question} has {len(questions_with_options[current_question]['options'])} options")
        
        # STEP 2: Insert question-input tags for found questions
        found_questions = sorted(questions_with_options.keys())
        print(f"[PERFECT_MC] 📋 Processing found questions: {found_questions}")
        
        for q_num in found_questions:
            if q_num in questions_with_options and len(questions_with_options[q_num]['options']) >= 3:
                try:
                    # Create question-input tag with individual options for this question
                    options_json = json.dumps(questions_with_options[q_num]['options'], ensure_ascii=False, separators=(',', ':'))
                    options_json_escaped = options_json.replace('"', '&quot;')
                    
                    # Use proper question type - individual questions should use multiple_choice_with_multiple_answer
                    question_text = questions_with_options[q_num]['text']
                    question_input_tag = f'<question-input data-question-number="{q_num}" data-question-type="multiple_choice_with_multiple_answer" data-question-options="{options_json_escaped}">{question_text}</question-input>'
                    
                    # Find the question paragraph and insert tag
                    patterns_to_try = []
                    
                    # Handle split format questions (like Q20 = 2+0)
                    if q_num >= 20 and str(q_num)[0] != str(q_num)[1]:  # Multi-digit with different digits
                        digit1, digit2 = str(q_num)[0], str(q_num)[1]
                        patterns_to_try = [
                            rf'(<p[^>]*>.*?<strong>\s*{digit1}\s*</strong>\s*<strong>\s*{digit2}\s*</strong>.*?)(</p>)',
                            rf'(<p.*?<strong>\s*{digit1}\s*</strong>\s*<strong>\s*{digit2}\s*</strong>.*?)(</p>)',
                        ]
                    
                    # Standard patterns for regular question numbers
                    patterns_to_try.extend([
                        rf'(<p[^>]*>.*?<strong>\s*{q_num}\s*</strong>.*?)(</p>)',
                        rf'(<p.*?<strong>\s*{q_num}\s*</strong>.*?)(</p>)',
                        rf'(<p[^>]*><strong>\s*{q_num}\s*</strong>.*?)(</p>)',
                    ])
                    
                    # Try each pattern until one works
                    inserted = False
                    for test_pattern in patterns_to_try:
                        matches = list(re.finditer(test_pattern, result_html, re.IGNORECASE | re.DOTALL))
                        
                        if matches:
                            print(f"[PERFECT_MC] 🎯 Using pattern for Q{q_num}: {test_pattern}")
                            
                            # Insert in the first match that doesn't already have question-input
                            for match in matches:
                                if match and match.group(0) and 'question-input' not in match.group(0):
                                    try:
                                        if match.lastindex and match.lastindex >= 2:
                                            new_content = match.group(1) + question_input_tag + match.group(2)
                                            result_html = result_html[:match.start()] + new_content + result_html[match.end():]
                                            print(f"[PERFECT_MC] ✅ Inserted Q{q_num} tag with {len(questions_with_options[q_num]['options'])} options")
                                            inserted = True
                                            break
                                    except Exception as e:
                                        print(f"[PERFECT_MC] ⚠️ Failed to insert Q{q_num}: {e}")
                                        continue
                            
                            if inserted:
                                break
                    
                    if not inserted:
                        print(f"[PERFECT_MC] ❌ Could not insert Q{q_num} - no suitable match found")
                
                except Exception as e:
                    print(f"[PERFECT_MC] ❌ Error processing Q{q_num}: {e}")
                    continue
        
        print("[PERFECT_MC] ✅ UNIVERSAL parsing complete!")
        return result_html
        
    except Exception as e:
        print(f"[PERFECT_MC] ❌ Error: {e}")
        import traceback
        print(f"[PERFECT_MC] ❌ Traceback: {traceback.format_exc()}")
        return html_content