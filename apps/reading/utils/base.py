# parsers/base.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import re
from bs4 import BeautifulSoup

class QuestionType:
    """Question type constants"""
    COMPLETION = "sentence_completion"
    TRUE_FALSE = "true_false" 
    MULTIPLE_CHOICE = "multiple_choice"
    MATCHING = "matching"
    MATCHING_HEADINGS = "matching_headings"
    SHORT_ANSWER = "short_answer"

class QuestionParser(ABC):
    """Abstract base class for all question parsers"""
    
    @abstractmethod
    def can_parse(self, html_content: str, plain_text: str) -> float:
        """Return confidence score 0-1 for this parser"""
        pass
    
    @abstractmethod
    def get_question_type(self) -> str:
        """Return the question type this parser handles"""
        pass
    
    @abstractmethod
    def parse_questions(self, html_content: str) -> str:
        """Parse and return modified HTML with question inputs"""
        pass
    
    def extract_question_numbers(self, html_content: str) -> List[int]:
        """Extract all question numbers from HTML"""
        numbers = []
        patterns = [
            r'<strong>(\d+)</strong>',
            r'<b>(\d+)</b>',
            r'(\d+)\.',
            r'Question\s+(\d+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, html_content, re.IGNORECASE)
            for match in matches:
                numbers.append(int(match.group(1)))
        
        return sorted(list(set(numbers)))
