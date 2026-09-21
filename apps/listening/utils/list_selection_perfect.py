import re
import json
from bs4 import BeautifulSoup

def parse_list_selection(html_content):
    """UNIVERSAL List Selection parser - handles both 'Choose TWO letters A-E' and 'Choose SIX answers from box' formats"""
    print("[PERFECT_LS] 🎯 Starting UNIVERSAL List Selection parsing...")
    
    if not html_content:
        return html_content
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        plain_text = soup.get_text(separator=' ', strip=True).lower()
        
        # Detect list selection patterns - much more flexible
        list_selection_patterns = [
            r'choose\s+(two|three|four|five|six|seven|eight|nine|ten)\s+letters?',
            r'choose\s+(two|three|four|five|six|seven|eight|nine|ten)\s+answers?\s+from\s+the\s+box',
            r'which\s+(two|three|four|five|six|seven|eight|nine|ten)',
            r'write\s+the\s+correct\s+letters?\s+in\s+boxes',
        ]
        
        is_list_selection = any(re.search(pattern, plain_text) for pattern in list_selection_patterns)
        
        if not is_list_selection:
            print("[PERFECT_LS] ❌ Not a list selection section")
            return html_content
        
        print("[PERFECT_LS] ✅ Detected list selection format")
        
        # Extract question range dynamically
        question_range = None
        range_patterns = [
            r'questions?\s+(\d+)\s+and\s+(\d+)',
            r'questions?\s+(\d+)[-–](\d+)',
            r'boxes\s+(\d+)\s+and\s+(\d+)',
        ]
        
        for pattern in range_patterns:
            match = re.search(pattern, plain_text)
            if match:
                start_q, end_q = int(match.group(1)), int(match.group(2))
                question_range = (start_q, end_q)
                print(f"[PERFECT_LS] ✅ Found question range: {start_q}-{end_q}")
                break
        
        if not question_range:
            print("[PERFECT_LS] ❌ Could not determine question range")
            return html_content
        
        start_q, end_q = question_range
        
        # Extract options dynamically (A-E, A-G, A-I, etc.)
        options = []
        p_tags = soup.find_all('p')
        
        # Multiple patterns to catch different option formats
        option_patterns = [
            r'<strong>\s*([A-Z])\s*(?:&nbsp;)*\s*</strong>(?:\s|&nbsp;)*(.+)',
            r'<p[^>]*>\s*<strong>\s*([A-Z])\s*</strong>\s*([^<]+?)</p>',
            r'<strong>\s*([A-Z])\s*</strong>\s*([^<]+?)(?=<strong>|</p>|$)',
        ]
        
        for p in p_tags:
            p_html = str(p)
            for pattern in option_patterns:
                opt_match = re.search(pattern, p_html, re.DOTALL)
                if opt_match:
                    letter = opt_match.group(1).upper()
                    text = opt_match.group(2)
                    
                    # Clean the text
                    text = re.sub(r'<[^>]+>', '', text)
                    text = re.sub(r'&nbsp;', ' ', text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    
                    # Skip if it's too short or looks like instruction text or question text
                    skip_patterns = ['choose', 'write', 'correct', 'letters', 'boxes', 'which', 'three', 'following', 'features', 'area', 'spain', 'speaker', 'talk', 'about']
                    text_lower = text.lower()
                    if len(text) > 2 and not any(skip in text_lower for skip in skip_patterns):
                        # Additional check: skip if text contains question-like phrases
                        question_indicators = ['does the speaker', 'talk about', 'of the following', 'which three']
                        if not any(indicator in text_lower for indicator in question_indicators):
                            # Check if we already have this option
                            if not any(opt['value'] == letter for opt in options):
                                options.append({
                                    'value': letter,
                                    'label': text
                                })
                                print(f"[PERFECT_LS] ✅ Found option {letter}: {text[:40]}...")
        
        # Sort options alphabetically
        options.sort(key=lambda x: x['value'])
        
        if len(options) < 2:
            print("[PERFECT_LS] ❌ Not enough options found")
            return html_content
        
        # Extract main question text - preserve original text
        main_question = ""
        instruction_text = ""
        questions_header_text = ""
        
        # Extract original header text (e.g., "Questions 18-20")
        # Also check HTML directly for better matching
        header_pattern = rf'questions?\s+{start_q}[-–]{end_q}'
        header_match = re.search(header_pattern, html_content, re.IGNORECASE)
        if header_match:
            # Extract the full line containing the header
            start_pos = max(0, header_match.start() - 50)
            end_pos = min(len(html_content), header_match.end() + 50)
            context = html_content[start_pos:end_pos]
            # Try to extract just the header text
            header_line_match = re.search(rf'(questions?\s+{start_q}[-–]{end_q})', context, re.IGNORECASE)
            if header_line_match:
                questions_header_text = header_line_match.group(1)
        
        # Fallback to paragraph search
        if not questions_header_text:
            for p in p_tags:
                text = p.get_text(strip=True)
                if re.search(rf'questions?\s+{start_q}[-–]{end_q}', text, re.IGNORECASE):
                    questions_header_text = text
                    break
        
        # Extract instruction text (e.g., "Choose THREE letters, A-F.")
        # Check HTML directly first for better matching
        instruction_pattern = r'choose\s+(two|three|four|five|six|seven|eight|nine|ten)\s+letters?[^<]*?[A-F]'
        instruction_match = re.search(instruction_pattern, html_content, re.IGNORECASE)
        if instruction_match:
            # Extract the full instruction line
            start_pos = max(0, instruction_match.start() - 20)
            end_pos = min(len(html_content), instruction_match.end() + 20)
            context = html_content[start_pos:end_pos]
            # Try to extract clean instruction
            instruction_line_match = re.search(r'(choose\s+(?:two|three|four|five|six|seven|eight|nine|ten)\s+letters?[^<]*?[A-F])', context, re.IGNORECASE)
            if instruction_line_match:
                instruction_text = instruction_line_match.group(1).strip()
                # Clean up HTML tags
                instruction_text = re.sub(r'<[^>]+>', '', instruction_text)
                instruction_text = re.sub(r'&nbsp;', ' ', instruction_text)
                instruction_text = re.sub(r'\s+', ' ', instruction_text).strip()
        
        # Fallback to paragraph search
        if not instruction_text:
            for p in p_tags:
                text = p.get_text(strip=True)
                if 'choose' in text.lower() and ('letters' in text.lower() or 'letter' in text.lower()):
                    if not any(skip in text.lower() for skip in ['questions', 'boxes']):
                        instruction_text = text
                        break
        
        # Extract main question text (e.g., "Which THREE of the following...")
        # Check HTML directly first for better matching - improved pattern to capture full question
        question_pattern = r'which\s+(?:two|three|four|five|six|seven|eight|nine|ten)\s+of\s+the\s+following[^<]*?(?:does|do|is|are)[^<]*?(?:talk|mention|discuss|describe)[^<]*?\?'
        question_match = re.search(question_pattern, html_content, re.IGNORECASE | re.DOTALL)
        if question_match:
            # Extract the full question line
            main_question = question_match.group(0).strip()
            # Clean up HTML tags
            main_question = re.sub(r'<[^>]+>', '', main_question)
            main_question = re.sub(r'&nbsp;', ' ', main_question)
            main_question = re.sub(r'\s+', ' ', main_question).strip()
            # Remove trailing punctuation if needed
            main_question = main_question.rstrip('?.').strip()
            if not main_question.endswith('?'):
                main_question += '?'
        
        # Try shorter pattern if full pattern didn't match
        if not main_question:
            question_pattern = r'which\s+(?:two|three|four|five|six|seven|eight|nine|ten)\s+of\s+the\s+following[^<]*'
            question_match = re.search(question_pattern, html_content, re.IGNORECASE)
            if question_match:
                # Extract the full question line
                start_pos = max(0, question_match.start() - 20)
                end_pos = min(len(html_content), question_match.end() + 200)
                context = html_content[start_pos:end_pos]
                # Try to extract clean question - look for question mark
                question_line_match = re.search(r'(which\s+(?:two|three|four|five|six|seven|eight|nine|ten)\s+of\s+the\s+following[^<]*?\?)', context, re.IGNORECASE | re.DOTALL)
                if question_line_match:
                    main_question = question_line_match.group(1).strip()
                else:
                    # Fallback to shorter version
                    question_line_match = re.search(r'(which\s+(?:two|three|four|five|six|seven|eight|nine|ten)\s+of\s+the\s+following[^<]*)', context, re.IGNORECASE)
                    if question_line_match:
                        main_question = question_line_match.group(1).strip()
                
                if main_question:
                    # Clean up HTML tags
                    main_question = re.sub(r'<[^>]+>', '', main_question)
                    main_question = re.sub(r'&nbsp;', ' ', main_question)
                    main_question = re.sub(r'\s+', ' ', main_question).strip()
                    # Remove trailing punctuation if needed
                    main_question = main_question.rstrip('?.').strip()
                    if not main_question.endswith('?'):
                        main_question += '?'
        
        # Fallback to paragraph search
        if not main_question:
            for p in p_tags:
                text = p.get_text(strip=True)
                if any(word in text.lower() for word in ['which', 'what']) and 'following' in text.lower():
                    if not any(skip in text.lower() for skip in ['choose', 'write', 'correct', 'letters', 'boxes', 'questions']):
                        main_question = text
                        break
        
        # Fallbacks if not found
        if not questions_header_text:
            if end_q - start_q == 1:
                questions_header_text = f"Questions {start_q} and {end_q}"
            else:
                questions_header_text = f"Questions {start_q}-{end_q}"
        
        if not instruction_text:
            choose_number = "TWO"
            number_match = re.search(r'choose\s+(two|three|four|five|six|seven|eight|nine|ten)', plain_text)
            if number_match:
                choose_number = number_match.group(1).upper()
            if options:
                option_range = f"A-{options[-1]['value']}"
            else:
                option_range = "A-E"
            instruction_text = f"Choose {choose_number} letters, {option_range}."
        
        if not main_question:
            main_question = f"Which {end_q - start_q + 1} options are correct?"
        
        # Build the perfect list-selection-tegs format with question_numbers attribute
        options_json = json.dumps(options, ensure_ascii=False, separators=(',', ':'))
        question_numbers = [str(q) for q in range(start_q, end_q + 1)]
        question_numbers_json = json.dumps(question_numbers, separators=(',', ':'))
        
        # Build result preserving original text structure EXACTLY
        result_html = '<p><br />\n'
        result_html += f'{questions_header_text}</p>\n'
        result_html += f'<p><br />\n{instruction_text}</p>\n'
        result_html += f'<p>{main_question}</p>\n'
        result_html += f'<list-selection-tegs data-options=\'{options_json}\' question_numbers=\'{question_numbers_json}\' question_type="list_selection"></list-selection-tegs>\n'
        result_html += '<p>&nbsp;</p>'
        
        print(f"[PERFECT_LS] ✅ UNIVERSAL list selection format complete for Q{start_q}-{end_q}!")
        return result_html
        
    except Exception as e:
        print(f"[PERFECT_LS] ❌ Error: {e}")
        import traceback
        print(f"[PERFECT_LS] Traceback: {traceback.format_exc()}")
        return html_content