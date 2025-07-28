import os
import json
import fitz  # PyMuPDF <-- Add this import
from src.document_processor import DocumentProcessor

# Define input and output directories
INPUT_DIR = "input"
OUTPUT_DIR = "output"

def main():
    """
    Main function to process all PDF files in the input directory and
    generate JSON outlines in the output directory.
    """
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print(f"Searching for PDF files in {INPUT_DIR}...")
    
    for filename in os.listdir(INPUT_DIR):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(INPUT_DIR, filename)
            output_filename = os.path.splitext(filename)[0] + ".json"
            output_path = os.path.join(OUTPUT_DIR, output_filename)
            
            print(f"Processing {filename}...")
            
            try:
                # Use the 'with' statement to handle the file
                with fitz.open(pdf_path) as doc:
                    # Pass the open 'doc' object to the processor
                    processor = DocumentProcessor(doc)
                    result = processor.process()
                
                # Write the result to a JSON file
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=4, ensure_ascii=False)
                
                print(f"Successfully created outline at {output_path}")

            except Exception as e:
                print(f"Error processing {filename}: {e}")
                error_output = {
                    "error": f"Failed to process {filename}",
                    "details": str(e)
                }
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(error_output, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main()
