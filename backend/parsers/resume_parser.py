"""
Resume parser - Extracts information from resumes.
Supports PDF, DOCX, and TXT formats.
"""
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    from pypdf import PdfReader as _PdfReader
    PDF_AVAILABLE = True
except ImportError:
    _PdfReader = None  # type: ignore[assignment]
    PDF_AVAILABLE = False
    logger.warning("pypdf not installed - PDF parsing disabled")

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx not installed - DOCX parsing disabled")


class ResumeParser:
    """
    Parser for extracting information from resumes.
    """
    
    def __init__(self):
        """Initialize the resume parser."""
        self.supported_formats = ['.pdf', '.docx', '.txt']
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a resume file and extract structured information.
        
        Args:
            file_path: Path to the resume file
            
        Returns:
            Dictionary with extracted information
        """
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            raise FileNotFoundError(f"Resume file not found: {file_path}")
        
        file_ext = file_path_obj.suffix.lower()
        
        if file_ext not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {file_ext}")
        
        # Extract text based on file type
        if file_ext == '.pdf':
            text = self._extract_from_pdf(file_path)
        elif file_ext == '.docx':
            text = self._extract_from_docx(file_path)
        else:
            text = self._extract_from_txt(file_path)
        
        # Parse the extracted text
        parsed_data = self._parse_text(text)
        
        return parsed_data
    
    def _extract_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file."""
        if not PDF_AVAILABLE or _PdfReader is None:
            return "PDF parsing not available - pypdf not installed"
        
        try:
            text = []
            with open(file_path, 'rb') as file:
                # Narrow optional import for static type checking.
                pdf_reader = _PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text)
            return '\n'.join(text)
        except Exception as e:
            logger.error(f"Error extracting PDF: {e}")
            return ""
    
    def _extract_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file."""
        if not DOCX_AVAILABLE:
            return "DOCX parsing not available - python-docx not installed"
        
        try:
            from docx import Document  # Import here to avoid unbound warning
            doc = Document(file_path)
            text = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text.append(paragraph.text)
            return '\n'.join(text)
        except Exception as e:
            logger.error(f"Error extracting DOCX: {e}")
            return ""
    
    def _extract_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _parse_text(self, text: str) -> Dict[str, Any]:
        """
        Parse extracted text to structured data using AI.
        
        Args:
            text: Raw text from resume
            
        Returns:
            Structured resume data
        """
        try:
            # Import here to avoid circular imports
            from backend.llm.multi_ai_service import MultiAIService
            
            # Use AI to extract structured data
            ai_service = MultiAIService()
            
            prompt = f"""
Extract structured information from the following resume text. Return ONLY a valid JSON object with these fields:

1. "skills": Array of technical and professional skills (programming languages, tools, frameworks, soft skills)
2. "experience": Array of objects with: "title", "company", "duration", "description"
3. "education": Array of objects with: "degree", "institution", "year"
4. "contact": Object with: "name", "email", "phone" (if available)
5. "summary": Brief 2-3 sentence professional summary

Resume text:
{text[:4000]}

Return ONLY the JSON object, no explanations or markdown formatting.
"""
            
            response = ai_service.generate_text(prompt)
            
            # Try to parse the AI response as JSON
            import json
            import re
            
            # Ensure response is a string
            if not response:
                response = "{}"
            
            # Extract JSON from response (in case AI adds extra text)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed_data = json.loads(json_match.group())
            else:
                # Fallback to basic structure
                parsed_data = {
                    "contact": {},
                    "experience": [],
                    "education": [],
                    "skills": [],
                    "summary": ""
                }
            
            # Ensure all required fields exist
            parsed_data.setdefault("contact", {})
            parsed_data.setdefault("experience", [])
            parsed_data.setdefault("education", [])
            parsed_data.setdefault("skills", [])
            parsed_data.setdefault("summary", "")
            parsed_data["raw_text"] = text
            
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error parsing resume with AI: {e}")
            # Return basic structure with raw text
            return {
                "contact": {},
                "experience": [],
                "education": [],
                "skills": [],
                "summary": "",
                "raw_text": text
            }


# Helper function for backward compatibility
def extract_resume_text(file_path: str) -> str:
    """
    Extract raw text from a resume file.
    
    Args:
        file_path: Path to the resume file
        
    Returns:
        Extracted text from the resume
    """
    parser = ResumeParser()
    result = parser.parse(file_path)
    return result.get("raw_text", "")
