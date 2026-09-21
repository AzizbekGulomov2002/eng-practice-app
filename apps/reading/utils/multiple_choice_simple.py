import re
import json
from bs4 import BeautifulSoup

class SimpleMultipleChoiceParser:
    """SIMPLE Multiple Choice Parser - NO DUPLICATES, IN ORDER"""
    
    def __init__(self):
        self.debug = True
    
    def log(self, message):
        if self.debug:
            print(f"[SIMPLE_MC] {message}")
    
    def parse_and_insert_inputs(self, html_content):
        """SIMPLE approach: Find questions 17-20 and insert tags IN PLACE"""
        self.log("🎯 SIMPLE Multiple Choice parsing starting...")
        
        try:
            # Check if this contains "Choose the correct letter, A, B or C"
            if not re.search(r'choose\s+the\s+correct\s+letter.*A.*B.*or.*C', html_content, re.IGNORECASE):
                self.log("❌ Not a multiple choice section")
                return html_content
            
            # Extract questions and options data first
            questions_data = self.extract_questions_and_options(html_content, 17, 20)
            if not questions_data:
                self.log("❌ No questions found")
                return html_content
            
            # Process each question IN ORDER and insert tags IN PLACE
            result_html = html_content
            processed_questions = set()
            
            for q_num in [17, 18, 19, 20]:
                if q_num in questions_data:
                    question_data = questions_data[q_num]
                    
                    # Create question-input tag
                    options_json = json.dumps(question_data['options'], ensure_ascii=False, separators=(',', ':'))
                    options_json_escaped = options_json.replace('"', '&quot;')
                    
                    question_input_tag = f'<question-input data-question-number="{q_num}" data-question-type="multiple_choice_with_multiple_answer" data-question-options="{options_json_escaped}"></question-input>'
                    
                    # Find and replace the paragraph containing this question
                    success = False
                    
                    # Pattern 1: Standard format like <strong>17</strong>&nbsp;&nbsp; text
                    pattern1 = rf'(<p[^>]*>.*?<strong>\s*{q_num}\s*</strong>(?:\s|&nbsp;)*[^<]*?)(</p>)'
                    matches1 = list(re.finditer(pattern1, result_html, re.IGNORECASE | re.DOTALL))
                    
                    for match in matches1:
                        # Check if this paragraph doesn't already have question-input
                        if 'question-input' not in match.group(0):
                            # Insert the tag before </p>
                            new_content = match.group(1) + question_input_tag + match.group(2)
                            result_html = result_html[:match.start()] + new_content + result_html[match.end():]
                            success = True
                            processed_questions.add(q_num)
                            self.log(f"✅ Inserted Q{q_num} tag in original position")
                            break
                    
                    # Pattern 2: Split format for Q20: <strong>2</strong><strong>0</strong>
                    if not success and q_num == 20:
                        pattern2 = rf'(<p[^>]*>.*?<strong>\s*2\s*</strong><strong>\s*0\s*</strong>(?:\s|&nbsp;)*[^<]*?)(</p>)'
                        matches2 = list(re.finditer(pattern2, result_html, re.IGNORECASE | re.DOTALL))
                        
                        for match in matches2:
                            if 'question-input' not in match.group(0):
                                new_content = match.group(1) + question_input_tag + match.group(2)
                                result_html = result_html[:match.start()] + new_content + result_html[match.end():]
                                success = True
                                processed_questions.add(q_num)
                                self.log(f"✅ Inserted Q{q_num} tag with split format")
                                break
                    
                    if not success:
                        self.log(f"⚠️ Could not find paragraph for Q{q_num}")
            
            # REMOVE ALL DUPLICATE PARAGRAPHS AT THE END
            result_html = self.remove_duplicate_paragraphs(result_html, processed_questions)
            
            self.log(f"✅ Simple parsing complete. Processed: {sorted(processed_questions)}")
            return result_html
            
        except Exception as e:
            self.log(f"❌ Error: {e}")
            return html_content
    
    def extract_questions_and_options(self, html_content, start_q, end_q):
        """Extract questions and their options - FIXED VERSION"""
        questions_data = {}
        soup = BeautifulSoup(html_content, 'html.parser')
        p_tags = soup.find_all('p')
        
        current_question = None
        
        self.log(f"🔍 Scanning {len(p_tags)} paragraphs for Q{start_q}-{end_q}...")
        
        for i, p in enumerate(p_tags):
            p_text = p.get_text(strip=True)
            p_html = str(p)
            
            if not p_text or len(p_text) < 2:
                continue
            
            # Check for question numbers (including split Q20)
            q_num = None
            question_text = None
            
            # Standard format: <strong>17</strong>&nbsp;&nbsp; text
            q_match = re.search(r'<strong>\s*(\d+)\s*</strong>(?:\s|&nbsp;)*(.+)', p_html, re.IGNORECASE)
            if q_match:
                try:
                    q_num = int(q_match.group(1))
                    if start_q <= q_num <= end_q:
                        question_text = q_match.group(2).strip()
                        # Clean HTML and &nbsp; entities
                        question_text = re.sub(r'<[^>]+>', '', question_text)
                        question_text = re.sub(r'&nbsp;', ' ', question_text)
                        question_text = re.sub(r'\s+', ' ', question_text).strip()
                        self.log(f"✅ Found Q{q_num}: {question_text[:50]}...")
                except:
                    pass
            
            # Split format: <strong>2</strong><strong>0</strong>&nbsp;&nbsp; text
            if not q_num:
                split_match = re.search(r'<strong>\s*(\d)\s*</strong><strong>\s*(\d)\s*</strong>(?:\s|&nbsp;)*(.+)', p_html, re.IGNORECASE)
                if split_match:
                    try:
                        q_num = int(split_match.group(1) + split_match.group(2))
                        if start_q <= q_num <= end_q:
                            question_text = split_match.group(3).strip()
                            question_text = re.sub(r'<[^>]+>', '', question_text)
                            question_text = re.sub(r'&nbsp;', ' ', question_text)
                            question_text = re.sub(r'\s+', ' ', question_text).strip()
                            self.log(f"✅ Found Q{q_num} (split): {question_text[:50]}...")
                    except:
                        pass
            
            # If found a question, record it
            if q_num:
                questions_data[q_num] = {
                    'text': question_text or f"Question {q_num}",
                    'options': []
                }
                current_question = q_num
                continue
            
            # Check for options (A, B, C) - handle &nbsp; entities
            if current_question and current_question in questions_data:
                # Pattern: <strong>A&nbsp;&nbsp;</strong>&nbsp;text
                opt_html_match = re.search(r'<strong>\s*([ABC])\s*(?:&nbsp;)*\s*</strong>(?:\s|&nbsp;)*(.+)', p_html, re.IGNORECASE)
                if opt_html_match:
                    opt_letter = opt_html_match.group(1).upper()
                    opt_text = opt_html_match.group(2).strip()
                    # Clean HTML and &nbsp; entities
                    opt_text = re.sub(r'<[^>]+>', '', opt_text)
                    opt_text = re.sub(r'&nbsp;', ' ', opt_text)
                    opt_text = re.sub(r'\s+', ' ', opt_text).strip().rstrip('.')
                    
                    questions_data[current_question]['options'].append({
                        'value': opt_letter,
                        'label': opt_text
                    })
                    self.log(f"  📋 Added option {opt_letter} to Q{current_question}: {opt_text[:30]}...")
                    
                    # If we have 3 options (A, B, C), move to next question
                    if len(questions_data[current_question]['options']) >= 3:
                        self.log(f"  ✅ Q{current_question} has 3 options, moving to next question")
                        current_question = None
                    continue
                
                # Fallback: Plain text pattern for options
                opt_text_match = re.match(r'^([ABC])\s+(.+)$', p_text)
                if opt_text_match:
                    opt_letter = opt_text_match.group(1).upper()
                    opt_text = opt_text_match.group(2).strip().rstrip('.')
                    
                    questions_data[current_question]['options'].append({
                        'value': opt_letter,
                        'label': opt_text
                    })
                    self.log(f"  📋 Added option {opt_letter} to Q{current_question}: {opt_text[:30]}...")
                    
                    # If we have 3 options (A, B, C), move to next question
                    if len(questions_data[current_question]['options']) >= 3:
                        self.log(f"  ✅ Q{current_question} has 3 options, moving to next question")
                        current_question = None
        
        # Log final results
        self.log(f"📊 EXTRACTION SUMMARY:")
        for q_num in sorted(questions_data.keys()):
            q_data = questions_data[q_num]
            self.log(f"  Q{q_num}: {len(q_data['options'])} options - {q_data['text'][:50]}...")
            for opt in q_data['options']:
                self.log(f"    {opt['value']}: {opt['label'][:40]}...")
        
        return questions_data
    
    def remove_duplicate_paragraphs(self, html_content, processed_questions):
        """Remove duplicate paragraphs that were appended at the end"""
        self.log("🧹 Removing duplicate paragraphs...")
        
        # Find all paragraphs that contain question numbers we processed
        for q_num in processed_questions:
            # Count how many times this question appears
            pattern = rf'<p[^>]*>.*?<strong>\s*{q_num}\s*</strong>.*?</p>'
            matches = list(re.finditer(pattern, html_content, re.IGNORECASE | re.DOTALL))
            
            # If more than 1 match, remove all but the first
            if len(matches) > 1:
                self.log(f"🗑️ Found {len(matches)} paragraphs for Q{q_num}, removing duplicates...")
                
                # Remove duplicates in reverse order to maintain positions
                for match in reversed(matches[1:]):
                    html_content = html_content[:match.start()] + html_content[match.end():]
                    self.log(f"   ✅ Removed duplicate Q{q_num} paragraph")
        
        # Also handle Q20 split format duplicates
        if 20 in processed_questions:
            pattern20 = r'<p[^>]*>.*?<strong>\s*2\s*</strong><strong>\s*0\s*</strong>.*?</p>'
            matches20 = list(re.finditer(pattern20, html_content, re.IGNORECASE | re.DOTALL))
            
            if len(matches20) > 1:
                self.log(f"🗑️ Found {len(matches20)} Q20 split format paragraphs, removing duplicates...")
                for match in reversed(matches20[1:]):
                    html_content = html_content[:match.start()] + html_content[match.end():]
                    self.log("   ✅ Removed duplicate Q20 split paragraph")
        
        return html_content


# Function for models.py integration
def parse_multiple_choice(html_content):
    """Simple Multiple Choice parser"""
    parser = SimpleMultipleChoiceParser()
    return parser.parse_and_insert_inputs(html_content)