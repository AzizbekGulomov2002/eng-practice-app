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
                    
                    # Skip if it's too short or looks like instruction text
                    if len(text) > 2 and not any(skip in text.lower() for skip in ['choose', 'write', 'correct', 'letters', 'boxes']):
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
        
        # Extract main question text
        main_question = ""
        for p in p_tags:
            text = p.get_text(strip=True)
            if any(word in text.lower() for word in ['which', 'what', 'advantages', 'disadvantages']):
                if not any(skip in text.lower() for skip in ['choose', 'write', 'correct', 'letters', 'boxes', 'questions']):
                    main_question = text
                    break
        
        if not main_question:
            main_question = f"Which {end_q - start_q + 1} options are correct?"
        
        # Extract instruction text (number of answers to choose)
        choose_number = "TWO"
        number_match = re.search(r'choose\s+(two|three|four|five|six|seven|eight|nine|ten)', plain_text)
        if number_match:
            choose_number = number_match.group(1).upper()
        
        # Determine option range (A-E, A-G, A-I, etc.)
        if options:
            option_range = f"A-{options[-1]['value']}"
        else:
            option_range = "A-E"
        
        # Build the perfect list-selection-tegs format with question_numbers attribute
        options_json = json.dumps(options, ensure_ascii=False, separators=(',', ':'))
        question_numbers = [str(q) for q in range(start_q, end_q + 1)]
        question_numbers_json = json.dumps(question_numbers, separators=(',', ':'))
        
        # Header format
        if end_q - start_q == 1:  # Two questions (e.g., 10 and 11)
            questions_header = f"Questions {start_q} and {end_q}"
        else:  # Range of questions (e.g., 11-16)
            questions_header = f"Questions {start_q}-{end_q}"
        
        result_html = '<div>\n'
        result_html += f'<h3><em><strong>{questions_header}</strong></em></h3>\n'
        result_html += f'<p><em>Choose {choose_number} letters, {option_range} . Write the correct letters in boxes {start_q} and {end_q} on your answer sheet.</em></p>\n'
        result_html += f'<p>{main_question}</p>\n'
        result_html += f'<list-selection-tegs data-options=\'{options_json}\' question_numbers=\'{question_numbers_json}\' question_type="list_selection"> </list-selection-tegs>\n'
        result_html += '<p><br/>\r\n </p>\n'
        result_html += '</div>'
        
        print(f"[PERFECT_LS] ✅ UNIVERSAL list selection format complete for Q{start_q}-{end_q}!")
        return result_html
        
    except Exception as e:
        print(f"[PERFECT_LS] ❌ Error: {e}")
        import traceback
        print(f"[PERFECT_LS] Traceback: {traceback.format_exc()}")
        return html_content