# parsers/detector.py
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple

class ContentDetector:
    """Universal content detector for different question types"""
    
    @staticmethod
    def split_into_sections(html_content: str) -> List[Dict]:
        """Enhanced section splitting with multiple patterns"""
        
        # Comprehensive header detection patterns
        section_patterns = [
            # Questions X-Y format with various HTML structures
            r'<h[1-6][^>]*>.*?<strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong>.*?</h[1-6]>',
            r'<p[^>]*>.*?<strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong>.*?</p>',
            r'<div[^>]*>.*?<strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong>.*?</div>',
            r'<strong>Questions?\s+(\d+)[-–—&ndash;&mdash;](\d+)</strong>',
            
            # Single question format
            r'<h[1-6][^>]*>.*?<strong>Question\s+(\d+)</strong>.*?</h[1-6]>',
            r'<p[^>]*>.*?<strong>Question\s+(\d+)</strong>.*?</p>',
        ]
        
        sections = []
        all_matches = []
        
        for i, pattern in enumerate(section_patterns):
            matches = list(re.finditer(pattern, html_content, re.IGNORECASE))
            for match in matches:
                if len(match.groups()) == 2:
                    start_num = int(match.group(1))
                    end_num = int(match.group(2))
                else:
                    start_num = end_num = int(match.group(1))
                
                all_matches.append({
                    'start_num': start_num,
                    'end_num': end_num,
                    'start_pos': match.start(),
                    'end_pos': match.end(),
                    'pattern_index': i
                })
        
        # Remove duplicates and sort by position
        unique_matches = []
        seen_positions = set()
        
        for match in all_matches:
            if match['start_pos'] not in seen_positions:
                unique_matches.append(match)
                seen_positions.add(match['start_pos'])
        
        unique_matches.sort(key=lambda x: x['start_pos'])
        
        # Create sections
        for i, match in enumerate(unique_matches):
            section_start = match['start_pos']
            section_end = unique_matches[i + 1]['start_pos'] if i + 1 < len(unique_matches) else len(html_content)
            
            sections.append({
                'start_question': match['start_num'],
                'end_question': match['end_num'], 
                'html': html_content[section_start:section_end],
                'position': section_start
            })
        
        # If no sections found, treat as single section
        if not sections:
            sections.append({
                'start_question': 1,
                'end_question': 999,
                'html': html_content,
                'position': 0
            })
        
        return sections

    @staticmethod
    def find_existing_inputs(html_content: str) -> Dict[int, str]:
        """Find existing question-input tags"""
        existing = {}
        pattern = r'<question-input[^>]*data-question-number="(\d+)"[^>]*data-question-type="([^"]*)"[^>]*>'
        
        for match in re.finditer(pattern, html_content):
            q_num = int(match.group(1))
            q_type = match.group(2)
            existing[q_num] = q_type
            
        return existing