"""
Label Table Utility
-------------------
Detects "Label the map/plan/diagram" style blocks (e.g., Questions 17-20 with simple lines
like '17 tree', '18 dog walking area', ...) and converts them into a table-tegs component
compatible with our drag-drop UI.

This module is intentionally self-contained so it can be reused from views/services without
coupling to other parsers. A duplicate of this file exists in the Listening utils package.
"""

from __future__ import annotations

import json
import re
from typing import List, Tuple, Dict, Optional
from bs4 import BeautifulSoup


def _normalize_spaces(text: str) -> str:
    """Normalize non-breaking spaces and whitespace."""
    if not text:
        return ""
    text = text.replace("&nbsp;", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_label_table(html_content: str) -> bool:
    """
    Heuristically detect if a block is a simple labelling map/plan section that should
    be rendered as a table with inputs.
    """
    if not html_content:
        return False

    lower = BeautifulSoup(html_content, "html.parser").get_text(separator=" ", strip=True).lower()

    explicit_label_phrases = [
        "label the map",
        "label the plan",
        "label the diagram",
        "label the chart",
    ]

    supplemental_letter_phrases = [
        "write the correct letter",
        "write the correct number",
    ]

    spatial_keywords = [
        "map",
        "plan",
        "diagram",
        "site",
        "layout",
        "floor",
        "chart",
    ]

    has_explicit_label = any(phrase in lower for phrase in explicit_label_phrases)
    has_letter_instruction = any(phrase in lower for phrase in supplemental_letter_phrases)
    has_spatial_context = any(keyword in lower for keyword in spatial_keywords)

    has_label_instruction = has_explicit_label or (has_letter_instruction and has_spatial_context)

    has_question_range = bool(
        re.search(r"questions?\s*\d+\s*(?:-|–|to)\s*\d+", lower, re.IGNORECASE)
    )

    # Presence of multiple numbered single-line items like "17 tree"
    has_numbered_lines = len(re.findall(r"<strong>\s*\d+\s*</strong>", html_content, re.IGNORECASE)) >= 2

    return bool(has_label_instruction and has_question_range and has_numbered_lines)


def _extract_question_range(text: str) -> Tuple[int, int]:
    """
    Extract question number range from text. Returns (start, end) or (0, 0) if not found.
    """
    # Examples: "Questions 17-20", "Questions 17 – 20", "Question 17 to 20"
    m = re.search(
        r"questions?\s*(\d+)\s*(?:-|–|to)\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    if not m:
        return 0, 0
    try:
        a = int(m.group(1))
        b = int(m.group(2))
        if a <= b:
            return a, b
        return b, a
    except ValueError:
        return 0, 0


def _extract_questions(html_content: str, start_q: Optional[int], end_q: Optional[int]) -> List[Dict]:
    """
    Extract numbered question lines such as:
      <p><strong>17</strong> tree</p>
      <p><strong>18</strong> dog walking area</p>
    Returns list of {'number': int, 'label': str}.
    """
    results: List[Dict] = []
    seen = set()
    # Remove images for clarity
    soup = BeautifulSoup(html_content, "html.parser")
    for img in soup.find_all("img"):
        img.decompose()
    
    # First, try using BeautifulSoup to find paragraphs with strong tags containing numbers
    for p_tag in soup.find_all("p"):
        strong_tag = p_tag.find("strong")
        if not strong_tag:
            continue
        
        # Get the text of the strong tag
        strong_text = _normalize_spaces(strong_tag.get_text())
        
        # Check if it's a number
        if not strong_text.isdigit():
            continue
        
        num = int(strong_text)
        
        # Check range if provided
        if start_q and end_q and not (start_q <= num <= end_q):
            continue
        
        # Skip if already seen
        if num in seen:
            continue
        
        # Extract the label text after the strong tag
        # Method 1: Get text from next siblings (most reliable - preserves exact text)
        label_parts = []
        for sibling in strong_tag.next_siblings:
            if isinstance(sibling, str):
                text = _normalize_spaces(sibling)
                if text and not text.isdigit():
                    label_parts.append(text)
            elif hasattr(sibling, 'get_text'):
                text = _normalize_spaces(sibling.get_text(separator=" ", strip=True))
                if text and not text.isdigit():
                    label_parts.append(text)
        
        if label_parts:
            label = " ".join(label_parts)
        else:
            # Fallback: Get all text from paragraph and remove the number
            full_text = _normalize_spaces(p_tag.get_text(separator=" ", strip=True))
            # Find the number position and get everything after it
            num_pos = full_text.find(strong_text)
            if num_pos != -1:
                # Get text after the number (skip number + any punctuation/spaces)
                after_num = full_text[num_pos + len(strong_text):].lstrip(' .-:')
                if after_num:
                    label = after_num
                else:
                    continue
            else:
                continue
        
        label = _normalize_spaces(label)
        
        # Validate label
        if len(label) < 2:
            continue
        
        results.append({"number": num, "label": label})
        seen.add(num)
    
    # Fallback to regex if BeautifulSoup didn't find anything
    if not results:
        html = str(soup)
        patterns = [
            r"<p>\s*<strong>\s*(\d+)\s*</strong>\s*([^<]{2,300}?)\s*</p>",
            r"<strong>\s*(\d+)\s*</strong>\s*([^<]{2,300}?)(?=<|$)",
        ]

        for pattern in patterns:
            for m in re.finditer(pattern, html, re.IGNORECASE | re.DOTALL):
                num_str = m.group(1).strip()
                label = _normalize_spaces(m.group(2))
                if not num_str.isdigit():
                    continue
                num = int(num_str)
                if start_q and end_q and not (start_q <= num <= end_q):
                    continue
                if num in seen:
                    continue
                if len(label) < 2:
                    continue
                results.append({"number": num, "label": label})
                seen.add(num)

    results.sort(key=lambda x: x["number"])
    return results


def _extract_letter_options(html_content: str) -> List[Dict[str, str]]:
    """
    Extract letter options A-I (or wider) if present. If none are found but the section
    is detected as labelling, fall back to generating generic letter options A..I.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    options: List[Dict[str, str]] = []
    seen = set()

    for p in soup.find_all("p"):
        strong = p.find("strong")
        if not strong:
            continue
        s = _normalize_spaces(strong.get_text())
        if len(s) == 1 and s.isalpha() and s.isupper():
            value = s
            if value in seen:
                continue
            # Label after the strong letter inside the same paragraph
            full_text = _normalize_spaces(p.get_text(separator=" ", strip=True))
            label = full_text[len(value):].strip()
            # Keep short labels too; for map labelling, labels may be absent
            options.append({"value": value, "label": label or value})
            seen.add(value)

    if options:
        return options

    # Fallback: provide generic A..I options
    fallback_letters = [chr(c) for c in range(ord("A"), ord("I") + 1)]
    return [{"value": L, "label": L} for L in fallback_letters]


def _detect_nb_indicator(html_content: str, plain_text: str) -> bool:
    """Detect if NB indicator is present in the content."""
    content_lower = plain_text.lower()
    
    # Check for NB indicators
    nb_indicators = [
        r'<strong><em>nb</em></strong>',
        r'<em>nb</em>',
        r'\bnb\b',
        'you may use any letter more than once',
        'may use any letter more than once',
        'use any letter more than once',
        'letters may be used more than once'
    ]
    
    for indicator in nb_indicators:
        if re.search(indicator, content_lower):
            return True
    
    return False


def _collect_instruction_html(html_content: str, question_numbers: List[int]) -> str:
    """Return instruction HTML with question and option rows removed while preserving images/headings."""
    soup = BeautifulSoup(html_content, "html.parser")
    numbers_set = {str(num) for num in question_numbers}

    for p in list(soup.find_all("p")):
        strong = p.find("strong")
        if not strong:
            continue
        strong_text = _normalize_spaces(strong.get_text())
        if strong_text.isdigit() and strong_text in numbers_set:
            p.decompose()
            continue
        if len(strong_text) == 1 and strong_text.isalpha() and strong_text.isupper():
            p.decompose()

    return str(soup).strip()


def build_label_table_component(
    html_content: str,
    start_q: Optional[int],
    end_q: Optional[int],
    question_type: str = "matching_information",
    table_name: Optional[str] = None,
) -> Tuple[str, List[int]]:
    """
    Build a table-tegs component populated with labelling data.
    Returns (component_html, processed_question_numbers).
    """
    options = _extract_letter_options(html_content)
    questions = _extract_questions(html_content, start_q, end_q)
    if not questions:
        return html_content, []

    if (not start_q or not end_q) and questions:
        numbers = [q["number"] for q in questions]
        if numbers:
            start_q = start_q or min(numbers)
            end_q = end_q or max(numbers)

    questions_payload = [
        {"question_number": q["number"], "question_text": q["label"]}
        for q in questions
    ]

    options_json = json.dumps(options, ensure_ascii=False, separators=(",", ":"))
    questions_json = json.dumps(questions_payload, ensure_ascii=False, separators=(",", ":"))
    options_attr = options_json.replace("&", "&amp;").replace("'", "&#39;")
    questions_attr = questions_json.replace("&", "&amp;").replace("'", "&#39;")

    table_label = table_name or (f"Questions {start_q}–{end_q}" if start_q and end_q else "Labelling")
    table_label = _normalize_spaces(table_label)
    table_label_attr = table_label.replace("&", "&amp;").replace("'", "&#39;").replace('"', "&quot;")

    # Check for NB indicator to determine repeat_answer
    plain_text = _normalize_spaces(BeautifulSoup(html_content, "html.parser").get_text(separator=" ", strip=True))
    has_nb = _detect_nb_indicator(html_content, plain_text)
    repeat_answer = "True" if has_nb else "False"

    component_html = (
        f'<table-tegs data-options=\'{options_attr}\' '
        f'data-questions=\'{questions_attr}\' '
        f'data-question-type="{question_type}" '
        f'repeat_answer="{repeat_answer}" '
        f'table_name="{table_label_attr}"></table-tegs>'
    )

    return component_html, [q["number"] for q in questions]


def convert_to_label_table(
    html_content: str,
    start_q: Optional[int] = None,
    end_q: Optional[int] = None,
    question_type: str = "matching_information",
) -> Tuple[str, List[int]]:
    """
    Public entry point.
    - Detect a labelling section.
    - Extract range, build table component, return new HTML and processed question numbers.
    """
    if not html_content:
        return html_content, []

    # Fast bail if already processed
    if 'drag-drop-matching-sentence-endings' in html_content or 'table-tegs' in html_content:
        return html_content, []

    plain = _normalize_spaces(BeautifulSoup(html_content, "html.parser").get_text(separator=" ", strip=True))
    detected_start, detected_end = _extract_question_range(plain)
    if start_q is None or start_q == 0:
        start_q = detected_start or None
    if end_q is None or end_q == 0:
        end_q = detected_end or None

    if not detect_label_table(html_content):
        return html_content, []

    component_html, processed = build_label_table_component(
        html_content=html_content,
        start_q=start_q,
        end_q=end_q,
        question_type=question_type,
    )
    if not processed:
        return html_content, []

    instructions_html = _collect_instruction_html(html_content, processed)
    parts = [instructions_html, component_html]
    new_html = "".join([part for part in parts if part])
    return new_html, processed


