"""
Multi-Provider AI Service
Supports Gemini, Groq, and OpenAI for cover letter generation and question answering.
"""
import os
import logging
from typing import Optional, Dict, Any, List, Literal
from dotenv import load_dotenv

# Import provider-specific libraries
try:
    import google.generativeai as genai  # type: ignore
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None  # type: ignore

try:
    from groq import Groq  # type: ignore
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None  # type: ignore

try:
    from openai import OpenAI  # type: ignore
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None  # type: ignore

load_dotenv()
logger = logging.getLogger(__name__)

AIProvider = Literal["gemini", "groq", "openai"]


class MultiAIService:
    """
    Unified service for multiple AI providers.
    Supports Gemini, Groq, and OpenAI with automatic fallback.
    """
    
    def __init__(
        self, 
        provider: Optional[AIProvider] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7
    ):
        """
        Initialize multi-provider AI service.
        
        Args:
            provider: AI provider to use ('gemini', 'groq', 'openai')
            api_key: API key for the provider
            temperature: Temperature for generation (0-1)
        """
        self.temperature = temperature
        self.provider = provider
        self.api_key = api_key
        self.client = None
        
        # Auto-detect provider if not specified
        if not provider:
            self.provider = self._auto_detect_provider()
        
        # Initialize the selected provider
        if self.provider:
            self._initialize_provider(self.provider, api_key)
    
    def _auto_detect_provider(self) -> Optional[AIProvider]:
        """Auto-detect available AI provider from environment variables."""
        if GEMINI_AVAILABLE and (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
            logger.info("Auto-detected Gemini as AI provider")
            return "gemini"
        elif GROQ_AVAILABLE and os.getenv("GROQ_API_KEY"):
            logger.info("Auto-detected Groq as AI provider")
            return "groq"
        elif OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            logger.info("Auto-detected OpenAI as AI provider")
            return "openai"
        
        logger.warning("No AI provider API key found in environment")
        return None
    
    def _initialize_provider(self, provider: AIProvider, api_key: Optional[str] = None):
        """Initialize the specified AI provider."""
        try:
            if provider == "gemini":
                if not GEMINI_AVAILABLE:
                    raise ImportError("google-generativeai package not installed")
                
                key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                if not key:
                    raise ValueError("Gemini API key not provided")
                
                genai.configure(api_key=key)  # type: ignore
                # Use the latest stable Gemini model
                self.client = genai.GenerativeModel("gemini-2.5-flash")  # type: ignore
                logger.info("Initialized Gemini AI service with gemini-2.5-flash")
                
            elif provider == "groq":
                if not GROQ_AVAILABLE:
                    raise ImportError("groq package not installed")
                
                key = api_key or os.getenv("GROQ_API_KEY")
                if not key:
                    raise ValueError("Groq API key not provided")
                
                self.client = Groq(api_key=key)  # type: ignore
                logger.info("Initialized Groq AI service")
                
            elif provider == "openai":
                if not OPENAI_AVAILABLE:
                    raise ImportError("openai package not installed")
                
                key = api_key or os.getenv("OPENAI_API_KEY")
                if not key:
                    raise ValueError("OpenAI API key not provided")
                
                self.client = OpenAI(api_key=key)  # type: ignore
                logger.info("Initialized OpenAI AI service")
                
        except Exception as e:
            logger.error(f"Failed to initialize {provider}: {e}")
            self.client = None
            self.provider = None
    
    def generate_text(self, prompt: str, max_tokens: int = 1000) -> Optional[str]:
        """
        Generate text using the configured AI provider.
        
        Args:
            prompt: Text prompt for generation
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text or None if failed
        """
        if not self.client or not self.provider:
            logger.error("No AI provider initialized")
            return None
        
        try:
            if self.provider == "gemini":
                response = self.client.generate_content(prompt)  # type: ignore
                return response.text  # type: ignore
                
            elif self.provider == "groq":
                response = self.client.chat.completions.create(  # type: ignore
                    model="mixtral-8x7b-32768",  # Fast and high quality
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content  # type: ignore
                
            elif self.provider == "openai":
                response = self.client.chat.completions.create(  # type: ignore
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content  # type: ignore
                
        except Exception as e:
            logger.error(f"Error generating text with {self.provider}: {e}")
            return None
    
    def generate_cover_letter(
        self,
        job_title: str,
        company_name: str,
        job_description: str,
        resume_text: str,
        user_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a personalized cover letter.
        
        Args:
            job_title: Title of the job position
            company_name: Name of the company
            job_description: Full job description
            resume_text: User's resume content
            user_name: User's full name
            
        Returns:
            Generated cover letter or None if failed
        """
        prompt = f"""Generate a professional cover letter for the following job application:

Job Title: {job_title}
Company: {company_name}

Job Description:
{job_description}

Candidate's Resume:
{resume_text}

Requirements:
1. Write a compelling cover letter that highlights relevant experience
2. Match the candidate's skills to the job requirements
3. Be professional, concise, and engaging
4. Use a confident and enthusiastic tone
5. Keep it to 3-4 paragraphs
6. {f"Address it from {user_name}" if user_name else "Start with a professional greeting"}

Cover Letter:"""

        return self.generate_text(prompt, max_tokens=800)
    
    def answer_question(
        self,
        question: str,
        resume_text: str,
        job_context: Optional[str] = None
    ) -> Optional[str]:
        """
        Answer a job application question using resume context.
        
        Args:
            question: The question to answer
            resume_text: User's resume content
            job_context: Optional job description for context
            
        Returns:
            Generated answer or None if failed
        """
        context = f"\n\nJob Context:\n{job_context}" if job_context else ""
        
        prompt = f"""Based on the following resume, answer this job application question professionally and concisely.

Resume:
{resume_text}
{context}

Question: {question}

Provide a clear, honest, and professional answer (2-3 sentences):"""

        return self.generate_text(prompt, max_tokens=300)
    
    def evaluate_job_match(
        self,
        job_description: str,
        resume_text: str
    ) -> Dict[str, Any]:
        """
        Evaluate how well a job matches the candidate's profile.
        
        Args:
            job_description: Full job description
            resume_text: User's resume content
            
        Returns:
            Dictionary with match score and reasoning
        """
        prompt = f"""Evaluate how well this candidate matches the job requirements. Provide a score from 0-100 and brief reasoning.

Job Description:
{job_description}

Candidate Resume:
{resume_text}

Respond in this exact format:
SCORE: [0-100]
REASONING: [2-3 sentences explaining the match]"""

        response = self.generate_text(prompt, max_tokens=200)
        
        if not response:
            return {"score": 50, "reasoning": "Unable to evaluate match"}
        
        try:
            lines = response.strip().split('\n')
            score_line = [l for l in lines if l.startswith('SCORE:')][0]
            reasoning_line = [l for l in lines if l.startswith('REASONING:')][0]
            
            score = int(score_line.split(':')[1].strip())
            reasoning = reasoning_line.split(':', 1)[1].strip()
            
            return {"score": score, "reasoning": reasoning}
        except:
            return {"score": 50, "reasoning": response[:200]}
    
    def is_available(self) -> bool:
        """Check if the AI service is available and initialized."""
        return self.client is not None and self.provider is not None
    
    def get_provider_name(self) -> Optional[str]:
        """Get the name of the current AI provider."""
        return self.provider


# Backward compatibility - keep GeminiService for existing code
class GeminiService(MultiAIService):
    """Backward compatible Gemini service wrapper."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(provider="gemini", api_key=api_key, **kwargs)
