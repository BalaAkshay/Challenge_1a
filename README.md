# PDF Outline Extractor

This project is a PDF processing pipeline built using Python and Docker. It scans a directory of input PDFs, identifies document titles and hierarchical headings (H1, H2, H3), and generates a structured JSON outline for each PDF.

## 📌 Approach

The goal is to extract a clean outline of headings from PDF files without relying on built-in bookmarks or TOC metadata. The approach involves:

1. *Text Extraction*: Each PDF is parsed using PyMuPDF to extract spans, lines, fonts, sizes, and layout data.
2. *Heuristic Rules*:
   - Lines are filtered based on position, font size, boldness, all-caps, and more.
   - Short lines with larger fonts or bold/all-caps styling are likely to be headings.
3. *Line Recombination*:
   - Handles broken multi-line headings or numbered heading formats (e.g., 3. + Introduction) by merging adjacent lines.
4. *Heading Classification*:
   - Font sizes are clustered into levels: largest as H1, next as H2, and so on.
5. *Robust Title Extraction*:
   - The title is inferred from metadata or the largest text on the first page.

This design ensures consistent performance even on unstructured or OCR-based PDFs.

## 🧠 Models and Libraries Used

- PyMuPDF: For PDF parsing and layout extraction.
- collections.Counter: For computing dominant styles (e.g., body font size).
- re and json: For heading identification and structured output formatting.
- (Optional): An alternative ML-powered version (document_processor_with_MLModel.py) uses:
  - KeyBERT
  - SentenceTransformers for offline keyword extraction.

⚠ The main implementation used in main.py is based on rule-based heuristics only and does *not* require a machine learning model.

## ⚙ How to Build and Run

This solution is fully containerized with Docker. You can build and run it easily using the commands below:

### 📁 Directory Structure


project/
│
├── Dockerfile
├── requirements.txt
├── main.py
├── src/
│   └── document_processor.py
├── input/
│   └── [PDF files to process]
├── output/
│   └── [JSON outputs will be saved here]


### 🧪 Build the Docker Image

bash
docker build -t pdf-outline-extractor .


### 🚀 Run the Container

bash
docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output pdf-outline-extractor


- Mounts the local input/ and output/ directories to the container.
- All .pdf files in input/ will be processed.
- Results are saved as .json files in output/.

## ✅ Example Output

**Example: output/STEMPathwaysFlyer.json**

json
{
  "title": "Parsippany -Troy Hills STEM Pathways",
  "outline": [
    {
      "level": "H3",
      "text": "Mission Statement:",
      "page": 1
    },
    {
      "level": "H2",
      "text": "PATHWAY OPTIONS",
      "page": 1
    },
    {
      "level": "H1",
      "text": "What Colleges Say!",
      "page": 2
    }
  ]
}


## 🧩 Notes

- The main PDF parsing logic resides in src/document_processor.py.
- Error handling ensures a graceful fallback to JSON with error details if any file fails to process.
- The optional ML model version is provided separately and not included in the final Docker container.