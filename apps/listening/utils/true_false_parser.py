import re
from bs4 import BeautifulSoup

class TrueFalseNotGivenParser:
    """BULLETPROOF True/False parser that handles GARBLED HTML and ALL formats"""
    
    def __init__(self):
        self.question_type = 'true_false_not_given'
    
    def clean_garbled_html(self, html_content):
        """CRITICAL: Clean garbled HTML with URL encoding and malformed tags"""
        if not html_content:
            return html_content
        
        print(f"[TFNG_CLEAN] 🧽 Cleaning garbled HTML...")
        
        try:
            # Step 1: Remove HTML comments (encoded and normal)
            html_content = re.sub(r'<!--[^>]*-->', '', html_content)
            html_content = re.sub(r'%3C!%2D%2D[^%]*%2D%2D%3E', '', html_content)
            
            # Step 2: URL decode garbage
            html_content = re.sub(r'%3C', '<', html_content)
            html_content = re.sub(r'%3E', '>', html_content) 
            html_content = re.sub(r'%2D', '-', html_content)
            html_content = re.sub(r'%20', ' ', html_content)
            html_content = re.sub(r'%22', '"', html_content)
            
            # Step 3: Fix malformed endings
            html_content = re.sub(r'p&gt;</p>', '</p>', html_content)
            html_content = re.sub(r'p&gt;', '</p>', html_content)
            
            # Step 4: Remove remaining URL encoding patterns
            html_content = re.sub(r'%[0-9A-F]{2}', '', html_content)
            
            # Step 5: Clean up multiple spaces and entities
            html_content = re.sub(r'&nbsp;', ' ', html_content)
            html_content = re.sub(r'&rsquo;', "'", html_content)
            html_content = re.sub(r'\s+', ' ', html_content)
            
            print(f"[TFNG_CLEAN] ✅ HTML cleaned successfully")
            return html_content
            
        except Exception as e:
            print(f"[TFNG_CLEAN] ❌ Cleaning error: {e}")
            return html_content
    
    def detect_question_type(self, html_content, plain_text):
        """Detect if this is True/False or Yes/No type"""
        content_lower = plain_text.lower()
        
        if any(keyword in content_lower for keyword in ['true', 'false']):
            return 'true_false_not_given'
            
        if any(keyword in content_lower for keyword in ['yes', 'no']) and 'true' not in content_lower:
            return 'yes_no_not_given'
        
        return 'true_false_not_given'
    
    def is_true_false_question(self, html_content, plain_text):
        """BULLETPROOF detection for True/False questions"""
        content_lower = plain_text.lower()
        
        print(f"[TFNG] 🎯 BULLETPROOF True/False detection...")
        
        # Ultra-strong True/False indicators
        ultra_strong_indicators = [
            'do the following statements agree',
            'agree with the information',
            'contradicts the information', 
            'statement agrees with the information',
            'statement contradicts the information',
        ]
        
        # T/F keywords
        tf_keywords = ['true', 'false', 'not given', 'yes', 'no']
        has_tf_keywords = any(keyword in content_lower for keyword in tf_keywords)
        
        # Strong context
        has_strong_context = any(indicator in content_lower for indicator in ultra_strong_indicators)
        
        # Must NOT have completion patterns
        has_completion = bool(re.search(r'\.{3,}|&hellip;|…', html_content))
        
        # Must NOT have multiple choice patterns
        has_multiple_choice = bool(re.search(r'choose the correct letter', content_lower))
        
        result = (
            has_strong_context and has_tf_keywords and 
            not has_completion and not has_multiple_choice
        )
        
        print(f"[TFNG] 🎯 Strong context: {has_strong_context}, TF keywords: {has_tf_keywords}")
        print(f"[TFNG] 🎯 Completion: {has_completion}, Multiple choice: {has_multiple_choice}")
        print(f"[TFNG] 🎯 Result: {result}")
        
        return result
    
    def find_questions_bulletproof(self, html_content):
        """BULLETPROOF method to find questions in GARBLED HTML"""
        print(f"[TFNG] 🔍 BULLETPROOF question detection...")
        
        questions = []
        
        # BULLETPROOF patterns for garbled HTML
        bulletproof_patterns = [
            # Pattern 1: <strong>9</strong>  Statement (with spaces/nbsp)
            (r'<strong>(\d+)</strong>\s*([A-Z][^<]+?)(?:</p>|$)', 'strong-spaced'),
            
            # Pattern 2: <strong>9</strong>Statement (direct connection)
            (r'<strong>(\d+)</strong>([A-Z][^<]+?)(?:</p>|$)', 'strong-direct'),
            
            # Pattern 3: <strong>9.</strong> Statement 
            (r'<strong>(\d+)\.</strong>\s*([A-Z][^<]+?)(?:</p>|<br)', 'strong-dot'),
            
            # Pattern 4: Paragraph-based with strong
            (r'<p[^>]*><strong>(\d+)</strong>[^<]*([A-Z][^<]+?)(?:</p>)', 'p-strong'),
            
            # Pattern 5: Any strong number followed by capital letter text
            (r'<strong>(\d+)\.?\s*</strong>\s*([A-Z][^<]*?)(?:</p>|<br|$)', 'flexible-strong'),
        ]
        
        for pattern, format_name in bulletproof_patterns:
            matches = re.finditer(pattern, html_content, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                try:
                    q_num = int(match.group(1))
                    statement = match.group(2).strip()
                    
                    # Clean statement text
                    statement = re.sub(r'\s+', ' ', statement).strip()
                    statement = re.sub(r'&[a-zA-Z]+;', '', statement)
                    
                    # Filter valid statements
                    if len(statement) > 10 and not statement.isdigit():
                        # Avoid duplicates
                        if not any(q['number'] == q_num for q in questions):
                            questions.append({
                                'number': q_num,
                                'text': statement,
                                'start': match.start(),
                                'end': match.end(),
                                'format': format_name,
                                'full_match': match.group(0)
                            })
                            print(f"[TFNG] ✅ {format_name} Q{q_num}: {statement[:60]}...")
                            
                except (ValueError, IndexError) as e:
                    print(f"[TFNG] ⚠️ Pattern error: {e}")
                    continue
        
        # Sort by number
        questions.sort(key=lambda x: x['number'])
        print(f"[TFNG] 📊 BULLETPROOF found {len(questions)} questions")
        return questions
    
    def insert_question_input_bulletproof(self, html_content, question):
        """BULLETPROOF method to insert question-input tags"""
        q_num = question['number']
        q_format = question['format']
        
        question_input = f'<question-input data-question-number="{q_num}" data-question-type="{self.question_type}"></question-input>'
        
        print(f"[TFNG] 🔧 Inserting Q{q_num} with {q_format} format...")
        
        try:
            if q_format in ['strong-spaced', 'strong-direct', 'flexible-strong']:
                # For <strong>9</strong> Statement formats
                pattern = rf'(<strong>{q_num}\.?\s*</strong>\s*[^<]*?)(<\/p>|$)'
                
                def replace_func(match):
                    return match.group(1) + question_input + match.group(2)
                
                new_html = re.sub(pattern, replace_func, html_content, count=1, flags=re.DOTALL)
                
                if new_html != html_content:
                    print(f"[TFNG] ✅ Successfully inserted {q_format} for Q{q_num}")
                    return new_html, True
            
            elif q_format == 'strong-dot':
                # For <strong>9.</strong> Statement format
                pattern = rf'(<strong>{q_num}\.</strong>\s*[^<]+?)(<br|</p>)'
                
                def replace_func(match):
                    return match.group(1) + question_input + match.group(2)
                
                new_html = re.sub(pattern, replace_func, html_content, count=1, flags=re.DOTALL)
                
                if new_html != html_content:
                    print(f"[TFNG] ✅ Successfully inserted strong-dot for Q{q_num}")
                    return new_html, True
            
            elif q_format == 'p-strong':
                # For paragraph format - add before closing </p>
                close_pos = html_content.find('</p>', question['start'])
                if close_pos != -1:
                    new_html = html_content[:close_pos] + question_input + html_content[close_pos:]
                    print(f"[TFNG] ✅ Successfully inserted p-strong for Q{q_num}")
                    return new_html, True
            
            # Fallback: Insert at end position
            end_pos = question['end']
            new_html = html_content[:end_pos] + question_input + html_content[end_pos:]
            print(f"[TFNG] ✅ Fallback insertion for Q{q_num}")
            return new_html, True
                
        except Exception as e:
            print(f"[TFNG] ❌ Insertion error for Q{q_num}: {e}")
            
        print(f"[TFNG] ⚠️ Failed to insert Q{q_num}")
        return html_content, False
    
    def parse_and_insert_inputs(self, html_content):
        """BULLETPROOF main parsing function"""
        print(f"[TFNG] 🎯 ========== BULLETPROOF TRUE/FALSE PARSING ==========")
        
        if not html_content:
            return html_content
        
        try:
            # CRITICAL: Clean garbled HTML first
            cleaned_html = self.clean_garbled_html(html_content)
            
            # Get plain text for analysis
            soup = BeautifulSoup(cleaned_html, 'html.parser')
            plain_text = soup.get_text(separator=' ', strip=True)
            
            # Validation
            if not self.is_true_false_question(cleaned_html, plain_text):
                print(f"[TFNG] ❌ Not a True/False question")
                return html_content
            
            print(f"[TFNG] ✅ BULLETPROOF confirmation: True/False format")
            
            # Determine question type
            self.question_type = self.detect_question_type(cleaned_html, plain_text)
            print(f"[TFNG] 🔧 Question type: {self.question_type}")
            
            # Find questions with BULLETPROOF detection
            questions = self.find_questions_bulletproof(cleaned_html)
            
            if not questions:
                print(f"[TFNG] ❌ No questions found")
                return html_content
            
            print(f"[TFNG] 📊 Processing {len(questions)} questions...")
            
            # CRITICAL: Remove duplicate questions (same question number and similar text)
            # Keep only the first occurrence of each question number
            seen_question_nums = {}
            unique_questions = []
            
            for q in questions:
                q_num = q['number']
                q_text = q['text'][:80]  # First 80 chars for comparison
                
                if q_num not in seen_question_nums:
                    unique_questions.append(q)
                    seen_question_nums[q_num] = q_text
                else:
                    # Check if text is similar (might be same question)
                    prev_text = seen_question_nums[q_num]
                    similarity = len(set(q_text.split()) & set(prev_text.split())) / max(len(q_text.split()), len(prev_text.split()), 1)
                    
                    if similarity > 0.7:  # 70% similarity threshold
                        print(f"[TFNG] 🗑️ Removing duplicate Q{q_num} at position {q['start']} (similarity: {similarity:.2f})")
                        print(f"[TFNG]   First: {prev_text[:50]}...")
                        print(f"[TFNG]   Duplicate: {q_text[:50]}...")
                    else:
                        # Different text, keep both
                        unique_questions.append(q)
                        print(f"[TFNG] ⚠️ Q{q_num} appears again with different text (similarity: {similarity:.2f}), keeping both")
            
            if len(unique_questions) < len(questions):
                print(f"[TFNG] ✅ Removed {len(questions) - len(unique_questions)} duplicate questions")
            
            questions = unique_questions
            
            # Process in reverse order
            processed_html = cleaned_html
            questions.sort(key=lambda x: x['end'], reverse=True)
            
            successful_insertions = 0
            
            for question in questions:
                # Check if question-input tag already exists for this question number
                existing_pattern = rf'<question-input[^>]*data-question-number=["\']{question["number"]}["\'][^>]*>'
                if re.search(existing_pattern, processed_html, re.IGNORECASE):
                    print(f"[TFNG] ⚠️ Q{question['number']} already has question-input tag, skipping...")
                    successful_insertions += 1
                    continue
                
                processed_html, success = self.insert_question_input_bulletproof(processed_html, question)
                if success:
                    successful_insertions += 1
            
            print(f"[TFNG] 🎯 BULLETPROOF success: {successful_insertions}/{len(questions)} insertions")
            print(f"[TFNG] 🎯 ========== BULLETPROOF TRUE/FALSE PARSING COMPLETE ==========")
            
            return processed_html
            
        except Exception as e:
            print(f"[TFNG] ❌ BULLETPROOF ERROR: {e}")
            import traceback
            print(f"[TFNG] Traceback: {traceback.format_exc()}")
            return html_content


# BULLETPROOF function for models.py
def parse_true_false_questions(html_content):
    """BULLETPROOF True/False parser - handles garbled HTML and all formats"""
    parser = TrueFalseNotGivenParser()
    return parser.parse_and_insert_inputs(html_content)


# ENHANCED method for models.py - UNIVERSAL question detection
def get_unprocessed_questions_in_section_universal(self, section_html, existing_tags, start_q, end_q):
    """UNIVERSAL method to find questions in ALL formats with optimal patterns"""
    unprocessed = []
    
    # Universal patterns - most specific to general
    universal_patterns = [
        r'<strong>(\d+)\.</strong>',                        # Your format: <strong>1.</strong>
        r'<p[^>]*list-style-type:decimal[^>]*>.*?(\d+)\.',   # List-style format
        r'<p[^>]*><strong>(\d+)</strong>',                  # Traditional paragraph
        r'<h[1-6][^>]*><strong>(\d+)</strong>',             # Header questions
        r'<strong>(\d+)</strong>',                          # General strong tags
        r'<td[^>]*>[^<]*<strong>(\d+)</strong>',            # Table questions
        r'<span[^>]*>(\d+)\.\s*[A-Z]',                      # Span with number
        r'(\d+)\.\s*[A-Z][a-z]{5,}',                       # Simple number format
    ]
    
    found_questions = set()
    
    for pattern in universal_patterns:
        try:
            matches = re.finditer(pattern, section_html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                q_num = int(match.group(1))
                if start_q <= q_num <= end_q:
                    found_questions.add(q_num)
                    
        except (ValueError, IndexError):
            continue
    
    # Filter out questions that already have tags
    for q_num in sorted(found_questions):
        if q_num not in existing_tags:
            unprocessed.append(q_num)
    
    print(f"[READING] 📊 Section {start_q}-{end_q}: Found {len(found_questions)} questions, {len(unprocessed)} unprocessed: {unprocessed}")
    return unprocessed




