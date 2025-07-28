import fitz  # PyMuPDF
import json
import re
from collections import Counter

class DocumentProcessor:
    """
    A class to process a single PDF document, extracting its title and a
    hierarchical outline of headings (H1, H2, H3).
    """

    HEURISTICS_CONFIG = {
    # --- Rejection Filters ---
    'header_margin_percent': 10,
    'footer_margin_percent': 10,
    'citation_regex': r'\[[A-Z]+[0-9]{2,}\]',
    'max_word_count': 20,
    'min_word_count': 1,

    # --- Primary Style Signals (at least one required) ---
    'min_size_multiplier': 1.15,
    'must_be_bold': True,
    'must_be_all_caps': True,

    # --- Secondary Layout Signals (at least one required) ---
    'must_have_different_color': False,
    'must_be_centered': False,
    'centered_tolerance': 20, 
}


    def __init__(self, doc_object):
        """
        Initializes the processor with an open fitz.Document object.
        """
        self.doc = doc_object


    def _get_document_title(self):
        """
        Extracts the document title, prioritizing metadata but falling back
        to the largest text on the first page and attempting to merge multi-line titles.
        """
        # Prioritize metadata title, but check for generic placeholders
        if self.doc.metadata and self.doc.metadata.get('title'):
            title = self.doc.metadata['title'].strip()
            if title and len(title) > 5 and not title.lower().startswith('untitled'):
                return title

        # Fallback: find and merge the largest text blocks on the first page
        if len(self.doc) > 0:
            page = self.doc[0]
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
            
            largest_size = 0
            title_candidates = []

            # Find the largest font size in the top half of the page
            for block in blocks:
                if block['type'] == 0 and block['bbox'][3] < page.rect.height / 2:
                    for line in block['lines']:
                        for span in line['spans']:
                            if span['size'] > largest_size:
                                largest_size = span['size']
            
            # Collect all lines with that font size
            for block in blocks:
                if block['type'] == 0 and block['bbox'][3] < page.rect.height / 2:
                    for line in block['lines']:
                        # Check if the line's primary font size matches the largest
                        if line['spans'] and round(line['spans'][0]['size']) == round(largest_size):
                            title_candidates.append("".join(s['text'] for s in line['spans']).strip())
            
            if title_candidates:
                return " ".join(title_candidates)

        return "Untitled Document"



    def _extract_all_lines(self):
        """
        Extracts text by spans and correctly groups them into lines by checking
        both vertical and horizontal proximity. This is the most robust method
        for complex, multi-column layouts.
        """
        all_lines = []
        for page_num, page in enumerate(self.doc):
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
            page_height = page.rect.height
            page_width = page.rect.width

            spans = []
            for block in blocks:
                if block['type'] == 0:
                    for line in block['lines']:
                        for span in line['spans']:
                            spans.append({
                                'text': span['text'],
                                'size': round(span['size']),
                                'font': span['font'].lower(),
                                'flags': span['flags'],
                                'color': span['color'],
                                'bbox': span['bbox'],
                                'page': page_num + 1,
                            })
            
            # Sort spans by page, then vertical, then horizontal position
            spans.sort(key=lambda s: (s['page'], s['bbox'][1], s['bbox'][0]))

            if not spans:
                continue

            # Group spans into proper lines
            current_line_spans = [spans[0]]
            for i in range(1, len(spans)):
                current_span = spans[i]
                last_span = current_line_spans[-1]

                # Check if spans are on the same vertical level
                is_vertically_aligned = abs(current_span['bbox'][1] - last_span['bbox'][1]) < 2
                # Check if spans are horizontally adjacent
                horizontal_gap = current_span['bbox'][0] - last_span['bbox'][2]
                is_horizontally_adjacent = 0 <= horizontal_gap < 10

                if is_vertically_aligned and is_horizontally_adjacent:
                    current_line_spans.append(current_span)
                else:
                    # Finalize the previous line
                    line_text = "".join(s['text'] for s in current_line_spans).strip()
                    if line_text:
                        line_bbox = fitz.Rect(
                            min(s['bbox'][0] for s in current_line_spans),
                            min(s['bbox'][1] for s in current_line_spans),
                            max(s['bbox'][2] for s in current_line_spans),
                            max(s['bbox'][3] for s in current_line_spans)
                        )
                        first_span = current_line_spans[0]
                        all_lines.append({
                            'text': line_text, 'size': first_span['size'], 'font': first_span['font'],
                            'flags': first_span['flags'], 'color': first_span['color'], 'bbox': tuple(line_bbox),
                            'page': first_span['page'], 'page_height': page_height, 'page_width': page_width
                        })
                    current_line_spans = [current_span]

            # Add the last line
            if current_line_spans:
                line_text = "".join(s['text'] for s in current_line_spans).strip()
                if line_text:
                    line_bbox = fitz.Rect(
                        min(s['bbox'][0] for s in current_line_spans),
                        min(s['bbox'][1] for s in current_line_spans),
                        max(s['bbox'][2] for s in current_line_spans),
                        max(s['bbox'][3] for s in current_line_spans)
                    )
                    first_span = current_line_spans[0]
                    all_lines.append({
                        'text': line_text, 'size': first_span['size'], 'font': first_span['font'],
                        'flags': first_span['flags'], 'color': first_span['color'], 'bbox': tuple(line_bbox),
                        'page': first_span['page'], 'page_height': page_height, 'page_width': page_width
                    })

        return all_lines


    def _recombine_lines(self, lines):
        """
        A robust method to merge fragmented lines, handling both multi-line
        headings and horizontally adjacent fragments like numbered lists.
        """
        if not lines:
            return []

        recombined = []
        current_line = lines[0]

        for i in range(1, len(lines)):
            next_line = lines[i]
            
            # Check if lines are on the same page and have the same style
            if (next_line['page'] == current_line['page'] and
                next_line['size'] == current_line['size'] and
                next_line['font'] == current_line['font']):

                # Condition 1: Horizontally adjacent (for "1." + "Introduction")
                horizontal_gap = next_line['bbox'][0] - current_line['bbox'][2]
                is_horizontally_adjacent = 0 <= horizontal_gap < (current_line['size'] * 0.8)

                # Condition 2: Vertically adjacent (for multi-line headings)
                vertical_gap = next_line['bbox'][1] - current_line['bbox'][3]
                is_vertically_adjacent = 0 <= vertical_gap < 5

                if is_horizontally_adjacent or is_vertically_adjacent:
                    current_line['text'] += " " + next_line['text']
                    current_line['bbox'] = (
                        min(current_line['bbox'][0], next_line['bbox'][0]),
                        min(current_line['bbox'][1], next_line['bbox'][1]),
                        max(current_line['bbox'][2], next_line['bbox'][2]),
                        max(current_line['bbox'][3], next_line['bbox'][3])
                    )
                    continue

            recombined.append(current_line)
            current_line = next_line
                
        recombined.append(current_line)
        return recombined

 

    def _is_heading(self, line, body_font_size, body_color):
        """
        Applies all heuristics to determine if a line is a heading.
        """
        text = line['text']
        
        # --- 1. REJECTION FILTERS ---
        if 'arXiv' in text: return False
        header_margin = line['page_height'] * (self.HEURISTICS_CONFIG['header_margin_percent'] / 100)
        footer_margin = line['page_height'] * (self.HEURISTICS_CONFIG['footer_margin_percent'] / 100)
        if line['bbox'][1] < header_margin or line['bbox'][3] > (line['page_height'] - footer_margin):
            return False
        if re.search(self.HEURISTICS_CONFIG['citation_regex'], text): return False
        word_count = len(text.split())
        if word_count > self.HEURISTICS_CONFIG['max_word_count']: return False
        if word_count < self.HEURISTICS_CONFIG['min_word_count'] and not re.match(r'^\d', text):
            return False

        # --- 2. POSITIVE HEURISTICS ---
        is_large_enough = line['size'] > body_font_size * self.HEURISTICS_CONFIG['min_size_multiplier']
        is_bold = (line['flags'] & 16) != 0 if self.HEURISTICS_CONFIG['must_be_bold'] else False
        has_numbering = re.match(r'^\d+(\.\d+)*\s|[A-Z]\s', text) is not None
        is_all_caps = text.isupper() if self.HEURISTICS_CONFIG['must_be_all_caps'] else False
        
        # --- 3. FINAL DECISION ---
        if is_large_enough or is_bold or has_numbering or is_all_caps:
            return True
        
        return False
    
    def _classify_headings(self, all_lines, body_font_size, body_color):
        """
        Classifies headings from a list of lines by applying the _is_heading check.
        """
        headings = []
        for line in all_lines:
            # Pass body_color to the check
            if self._is_heading(line, body_font_size, body_color):
                headings.append(line)
        return headings


    def _determine_hierarchy(self, classified_headings):
        """
        Determines the hierarchy (H1, H2, H3) of headings by clustering font sizes.
        """
        if not classified_headings:
            return [] # Return an empty list

        # Get unique font sizes from headings and sort them descending
        unique_sizes = sorted(list(set(h['size'] for h in classified_headings)), reverse=True)
        
        # FIX 2: Map individual sizes to levels, not the whole list.
        size_to_level = {}
        if len(unique_sizes) > 0:
            size_to_level[unique_sizes[0]] = "H1"
        if len(unique_sizes) > 1:
            size_to_level[unique_sizes[1]] = "H2"
        if len(unique_sizes) > 2:
            size_to_level[unique_sizes[2]] = "H3"

        # FIX 3: The outline should be a list to append to, not a dictionary.
        outline = [] 
        for heading in classified_headings:
            level = size_to_level.get(heading['size'])
            if level: # Only include H1, H2, H3
                outline.append({
                    'level': level,
                    'text': heading['text'],
                    'page': heading['page']
                })
        return outline

   

    def process(self):
        """
        Orchestrates the entire PDF processing workflow.
        """
        # 1. Extract the title using the robust method
        title = self._get_document_title()
        
        # 2. Extract properties for all text lines from the PDF
        all_lines = self._extract_all_lines()
        
        # 3. CRITICAL STEP: Recombine lines that were incorrectly split by the parser
        all_lines = self._recombine_lines(all_lines)
        
        # 4. Analyze styles from the cleaned-up line data
        all_sizes = [line['size'] for line in all_lines]
        body_font_size = Counter(all_sizes).most_common(1)[0][0] if all_sizes else 12.0

        all_colors = [line['color'] for line in all_lines]
        body_color = Counter(all_colors).most_common(1)[0][0] if all_colors else 0

        # 5. Classify headings using the recombined lines and style data
        classified_headings = self._classify_headings(all_lines, float(body_font_size), body_color)
        
        # 6. Determine the H1, H2, H3 hierarchy
        outline = self._determine_hierarchy(classified_headings)
        
        # 7. Return the final structured JSON
        return {
            "title": title,
            "outline": outline
        }