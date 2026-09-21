import re
from bs4 import BeautifulSoup

class IELTSQuestionParser:
    
    def __init__(self):
        pass
    
    def parse_and_insert_inputs(self, html_content):
        """BULLETPROOF UNIVERSAL PARSER - handles everything"""
        print(f"[PARSER] ========== BULLETPROOF UNIVERSAL PARSING ==========")
        
        if not html_content:
            return html_content
        
        print(f"[PARSER] Processing HTML length: {len(html_content)} characters")
        
        # Step 1: Handle ALL possible dot formats in one massive pattern
        # This pattern finds: <strong>NUMBER</strong> followed by optional space/nbsp and dots
        
        universal_pattern = r'(<strong>\s*(\d+)\s*</strong>)(\s*&nbsp;\s*|&nbsp;|\s+)?(\.{2,}|&hellip;{1,}|…{1,}|_{3,}|-{3,})'
        
        def replace_universal(match):
            full_strong_tag = match.group(1)  # <strong>6</strong>
            question_number = match.group(2)  # 6
            space_or_nbsp = match.group(3) or ''  # &nbsp; or space
            dots = match.group(4)  # .................
            
            # Create the replacement
            question_input = f'<question-input data-question-number="{question_number}" data-question-type="sentence_completion">{dots}</question-input>'
            result = full_strong_tag + space_or_nbsp + question_input
            
            print(f"[PARSER] ✅ Converted Q{question_number}: '{full_strong_tag}{space_or_nbsp}{dots}' → '{result}'")
            return result
        
        # Apply the universal pattern
        processed_html = re.sub(universal_pattern, replace_universal, html_content)
        
        # Step 2: Catch any remaining patterns that might have been missed
        # Direct number+dots pattern (without strong tags)
        fallback_pattern = r'(\d+)(\s*&nbsp;\s*|&nbsp;|\s+)(\.{2,}|&hellip;{1,}|…{1,}|_{3,}|-{3,})'
        
        def replace_fallback(match):
            question_number = match.group(1)
            space_or_nbsp = match.group(2)
            dots = match.group(3)
            
            # Only replace if it's not already inside a question-input tag
            return f'{question_number}{space_or_nbsp}<question-input data-question-number="{question_number}" data-question-type="sentence_completion">{dots}</question-input>'
        
        # Apply fallback only to parts not already processed
        if '<question-input' not in processed_html:
            processed_html = re.sub(fallback_pattern, replace_fallback, processed_html)
            print(f"[PARSER] Applied fallback pattern")
        
        # Step 3: Super aggressive catch-all for any dots near numbers
        if processed_html == html_content:  # No changes made yet
            print(f"[PARSER] Using AGGRESSIVE MODE...")
            
            # Find all numbers in strong tags
            strong_numbers = re.findall(r'<strong>(\d+)</strong>', html_content)
            
            # Find all dot patterns
            all_dots = re.finditer(r'\.{2,}|&hellip;+|…+|_{3,}|-{3,}', html_content)
            
            # Replace dots with question inputs in reverse order
            dots_list = list(all_dots)
            for i, dot_match in enumerate(reversed(dots_list)):
                if i < len(strong_numbers):
                    question_number = strong_numbers[-(i+1)]  # Match in reverse
                    dots = dot_match.group()
                    start, end = dot_match.span()
                    
                    replacement = f'<question-input data-question-number="{question_number}" data-question-type="sentence_completion">{dots}</question-input>'
                    processed_html = processed_html[:start] + replacement + processed_html[end:]
                    
                    print(f"[PARSER] 🔥 AGGRESSIVE: Q{question_number} dots replaced")
        
        changes_made = processed_html != html_content
        print(f"[PARSER] Result: {'SUCCESS - Changes made' if changes_made else 'NO CHANGES'}")
        print(f"[PARSER] ========== BULLETPROOF PARSING COMPLETE ==========")
        
        return processed_html


def parse_ielts_questions(html_content):
    """Universal function to parse any IELTS questions"""
    parser = IELTSQuestionParser()
    return parser.parse_and_insert_inputs(html_content)


# EVEN SIMPLER VERSION IF THE ABOVE FAILS
class SimpleIELTSParser:
    
    def parse(self, html_content):
        """SUPER SIMPLE - just replace dots after numbers"""
        if not html_content:
            return html_content
        
        # One single pattern to rule them all
        pattern = r'(<strong>(\d+)</strong>[^<]*?)(\.{2,}|&hellip;+|…+)'
        
        def replace_func(match):
            before_dots = match.group(1)
            question_number = match.group(2)
            dots = match.group(3)
            
            return f'{before_dots}<question-input data-question-number="{question_number}" data-question-type="sentence_completion">{dots}</question-input>'
        
        result = re.sub(pattern, replace_func, html_content)
        print(f"[SIMPLE] {'SUCCESS' if result != html_content else 'NO CHANGE'}")
        return result


# NUCLEAR OPTION - BRUTE FORCE
def nuclear_parse(html_content):
    """NUCLEAR OPTION - handles everything by brute force"""
    if not html_content:
        return html_content
    
    print("[NUCLEAR] 🚀 NUCLEAR PARSING ACTIVATED")
    
    # Step 1: Find ALL <strong>number</strong> patterns
    strong_pattern = r'<strong>(\d+)</strong>'
    question_numbers = []
    
    for match in re.finditer(strong_pattern, html_content):
        question_numbers.append({
            'number': int(match.group(1)),
            'position': match.end()
        })
    
    # Step 2: Find ALL dot patterns  
    dot_pattern = r'\.{2,}|&hellip;+|…+|_{3,}|-{3,}'
    dot_matches = []
    
    for match in re.finditer(dot_pattern, html_content):
        dot_matches.append({
            'dots': match.group(),
            'start': match.start(),
            'end': match.end()
        })
    
    # Step 3: Match and replace in reverse order
    processed_html = html_content
    
    if len(question_numbers) == len(dot_matches):
        # Perfect match - replace in reverse order
        for i in reversed(range(len(dot_matches))):
            question_num = question_numbers[i]['number']
            dot_info = dot_matches[i]
            
            replacement = f'<question-input data-question-number="{question_num}" data-question-type="sentence_completion">{dot_info["dots"]}</question-input>'
            
            start = dot_info['start']
            end = dot_info['end']
            processed_html = processed_html[:start] + replacement + processed_html[end:]
            
            print(f"[NUCLEAR] ☢️  Q{question_num} → {dot_info['dots']}")
    
    print(f"[NUCLEAR] {'🎯 SUCCESS' if processed_html != html_content else '❌ NO CHANGE'}")
    return processed_html


