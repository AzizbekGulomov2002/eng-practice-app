"""
Label Table Utility
-------------------
Detects "Label the map/plan/diagram" style blocks (e.g., Questions 17-20 with simple lines
like '17 tree', '18 dog walking area', ...) and converts them into a table-tegs component
compatible with our drag-drop UI.

This module is intentionally self-contained so it can be reused from views/services without
coupling to other parsers. A duplicate of this file exists in the Reading utils package.
"""

from __future__ import annotations

import json
import re
from typing import List, Tuple, Dict, Optional
from collections import OrderedDict
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
    spatial_patterns = [
        r'\bmap\b',
        r'\bfloor\s+plan\b',
        r'\bsite\s+plan\b',
        r'\bplan\s+of\b',
        r'\bdiagram\b',
        r'\blayout\s+of\b',
        r'\blayout\s+plan\b',
        r'\bchart\b',
    ]

    has_explicit_label = any(phrase in lower for phrase in explicit_label_phrases)
    has_letter_instruction = any(phrase in lower for phrase in supplemental_letter_phrases)
    has_spatial_context = any(re.search(pattern, lower) for pattern in spatial_patterns)

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
            # Remove the number and any leading punctuation/spaces
            # Use word boundary to ensure we only match the number at the start
            label = re.sub(rf'^{re.escape(strong_text)}\s*[\.\-\:\s]*', '', full_text, flags=re.IGNORECASE)
            # If still no match, try without word boundary but be more careful
            if not label or label == full_text:
                # Find the number position and get everything after it
                num_pos = full_text.find(strong_text)
                if num_pos != -1:
                    # Get text after the number (skip number + any punctuation/spaces)
                    after_num = full_text[num_pos + len(strong_text):].lstrip(' .-:')
                    if after_num:
                        label = after_num
        
        label = _normalize_spaces(label)
        label = re.sub(r"(?:&hellip;|…|\.{2,})", "", label).strip()
        
        # Validate label
        if len(label) < 2:
            continue
        
        results.append({"number": num, "label": label})
        seen.add(num)
    
    # Fallback to regex if BeautifulSoup didn't find anything
    if not results:
        html = str(soup)
        patterns = [
            r"<p[^>]*>\s*<strong[^>]*>\s*(\d+)\s*</strong>\s*(?:&nbsp;|\s)*([^<]{2,300}?)\s*</p>",
            r"<p[^>]*>(?:<span[^>]*>)*(?:<span[^>]*>)*<strong[^>]*>\s*(\d+)\s*</strong>(?:</span>)*(?:</span>)*(?:&nbsp;|\s)*([^<]{2,300}?)(?:</span>)*(?:</span>)*</p>",
            r"<strong[^>]*>\s*(\d+)\s*</strong>\s*(?:&nbsp;|\s)*([^<]{2,300}?)(?=<|$)",
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


def _sanitize_option_label(raw_label: str) -> str:
    """Clean option labels so they match matching_parser formatting."""
    if not raw_label:
        return ""
    label = re.sub(r"&nbsp;|\xa0", " ", raw_label)
    label = re.sub(r"\s+", " ", label).strip()
    # Strip leading punctuation such as ":" "," "-" "–"
    label = re.sub(r"^[\s\-\–\:;,\.]+", "", label)
    return label.strip()


def _dedupe_options(options: Dict[str, str]) -> List[Dict[str, str]]:
    """Ensure we don't emit duplicate value/label pairs and keep alphabetical order."""
    seen_values = set()
    seen_labels = set()
    cleaned: List[Dict[str, str]] = []

    for value in sorted(options.keys()):
        # Skip if value already seen (duplicate value)
        if value in seen_values:
            continue
        seen_values.add(value)
        
        label = options[value] or value
        label_key = label.lower()
        # Skip if label already seen (duplicate label)
        if label_key in seen_labels:
            continue
        seen_labels.add(label_key)
        cleaned.append({"value": value, "label": label})

    return cleaned


def _extract_letter_options(html_content: str) -> List[Dict[str, str]]:
    """
    Extract letter options A-I (or wider) if present. Always formats as "Paragraph {letter}".
    Raises ValueError if no valid range is found.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    options_map: OrderedDict[str, str] = OrderedDict()

    # First pass: collect explicit letter + label pairs
    for strong in soup.find_all("strong"):
        text = _normalize_spaces(strong.get_text())
        if len(text) != 1 or not text.isalpha() or not text.isupper():
            continue

        value = text
        if value in options_map:
            continue

        parent = strong.parent
        parent_text = ""
        if parent:
            parent_text = _normalize_spaces(parent.get_text(separator=" ", strip=True))

        label = parent_text
        # Remove the leading letter (with possible punctuation/space variants)
        if label.upper().startswith(value):
            label = label[1:].strip()
        label = _sanitize_option_label(label)
        # Always format as "Paragraph {letter}"
        options_map[value] = f"Paragraph {value}"

    # Detect range like A–G or A-D to build consistent options
    range_match = re.search(r"\b([A-Z])\s*(?:-|–|—|to)\s*([A-Z])\b", html_content, re.IGNORECASE)
    if range_match:
        start_letter = range_match.group(1).upper()
        end_letter = range_match.group(2).upper()
        if start_letter <= end_letter:
            letters = [chr(c) for c in range(ord(start_letter), ord(end_letter) + 1)]
            # Always format as "Paragraph {letter}"
            options_map = OrderedDict((letter, f"Paragraph {letter}") for letter in letters)
            return _dedupe_options(options_map)

    # If we have collected options from strong tags, use them
    if options_map:
        return _dedupe_options(options_map)

    # Fallback: provide generic A..I options, always formatted as "Paragraph {letter}"
    fallback_letters = [chr(c) for c in range(ord("A"), ord("I") + 1)]
    options_map = OrderedDict((letter, f"Paragraph {letter}") for letter in fallback_letters)
    options = _dedupe_options(options_map)
    
    if not options:
        raise ValueError("Cannot extract letter options from HTML content")
    
    return options


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
        'letters may be used more than once',
        'you may choose any letter more than once',
        'may choose any letter more than once'
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
    Build a table-tegs-input component populated with labelling data.
    Returns table-tegs-input with repeat_answer based on NB detection, table_name="List".
    Raises ValueError if required data cannot be extracted.
    Returns (component_html, processed_question_numbers).
    """
    try:
        options = _extract_letter_options(html_content)
    except ValueError as e:
        raise ValueError(f"Cannot extract options: {e}")
    
    questions = _extract_questions(html_content, start_q, end_q)
    if not questions:
        raise ValueError("Cannot extract questions from HTML content")

    if (not start_q or not end_q) and questions:
        numbers = [q["number"] for q in questions]
        if numbers:
            start_q = start_q or min(numbers)
            end_q = end_q or max(numbers)

    # Convert question_number to string to match matching_parser format
    questions_payload = [
        {"question_number": str(q["number"]), "question_text": q["label"]}
        for q in questions
    ]

    # Ensure no duplicate options by value
    seen_values = set()
    unique_options = []
    for opt in options:
        if opt["value"] not in seen_values:
            seen_values.add(opt["value"])
            unique_options.append(opt)

    if not unique_options:
        raise ValueError("No valid options extracted")

    options_json = json.dumps(unique_options, ensure_ascii=False, separators=(",", ":"))
    questions_json = json.dumps(questions_payload, ensure_ascii=False, separators=(",", ":"))
    options_attr = options_json.replace("&", "&amp;").replace("'", "&#39;")
    questions_attr = questions_json.replace("&", "&amp;").replace("'", "&#39;")

    # Always use "List" as table_name
    table_label_attr = "List"

    # Check for NB indicator to determine repeat_answer
    plain_text = _normalize_spaces(BeautifulSoup(html_content, "html.parser").get_text(separator=" ", strip=True))
    has_nb = _detect_nb_indicator(html_content, plain_text)
    repeat_answer = "True" if has_nb else "False"

    # Use table-tegs-input with repeat_answer based on NB detection
    component_html = (
        f'<table-tegs-input data-options=\'{options_attr}\' '
        f'data-questions=\'{questions_attr}\' '
        f'data-question-type="{question_type}" '
        f'repeat_answer="{repeat_answer}" '
        f'table_name="{table_label_attr}"></table-tegs-input>'
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
    - Extract range, build table-tegs-input component, return new HTML and processed question numbers.
    - Returns table-tegs-input with repeat_answer based on NB detection, table_name="List".
    - Raises ValueError if required format cannot be produced.
    """
    if not html_content:
        raise ValueError("HTML content is empty")

    # Fast bail if already processed
    if 'drag-drop-matching-sentence-endings' in html_content or 'table-tegs' in html_content or 'table-tegs-input' in html_content:
        raise ValueError("Content already contains processed table component")

    plain = _normalize_spaces(BeautifulSoup(html_content, "html.parser").get_text(separator=" ", strip=True))
    detected_start, detected_end = _extract_question_range(plain)

    # Prefer detected range when provided range is missing or clearly mismatched
    if detected_start and detected_end:
        has_provided_range = bool(start_q) and bool(end_q)

        if not has_provided_range:
            if not start_q or start_q == 0:
                start_q = detected_start
            if not end_q or end_q == 0:
                end_q = detected_end
        else:
            provided_overlaps = not (end_q < detected_start or start_q > detected_end)
            if not provided_overlaps:
                start_q, end_q = detected_start, detected_end

    if start_q is None or start_q == 0:
        start_q = detected_start or None
    if end_q is None or end_q == 0:
        end_q = detected_end or None

    if not detect_label_table(html_content):
        raise ValueError("Content does not match label table detection criteria")

    try:
        component_html, processed = build_label_table_component(
            html_content=html_content,
            start_q=start_q,
            end_q=end_q,
            question_type=question_type,
        )
    except ValueError as e:
        raise ValueError(f"Cannot build label table component: {e}")
    
    if not processed:
        raise ValueError("No questions were processed")

    instructions_html = _collect_instruction_html(html_content, processed)
    parts = [instructions_html, component_html]
    new_html = "".join([part for part in parts if part])
    
    if not new_html or 'table-tegs-input' not in new_html:
        raise ValueError("Failed to generate valid table-tegs-input component")
    
    # Final validation: ensure the component has the required attributes
    if 'repeat_answer=' not in component_html:
        raise ValueError("Generated component missing repeat_answer attribute")
    if 'table_name="List"' not in component_html:
        raise ValueError("Generated component missing table_name='List' attribute")
    if 'data-options=' not in component_html:
        raise ValueError("Generated component missing data-options attribute")
    if 'data-questions=' not in component_html:
        raise ValueError("Generated component missing data-questions attribute")
    
    return new_html, processed
