"""LLM-based paper analysis using Claude."""

import os
from dataclasses import dataclass
from typing import Optional

import anthropic


@dataclass
class PaperAnalysis:
    """Analysis results for a paper."""

    paper_id: str
    success: bool
    summary: Optional[str] = None
    methodology_evaluation: Optional[str] = None
    key_findings: Optional[list[str]] = None
    strengths: Optional[list[str]] = None
    limitations: Optional[list[str]] = None
    ai_techniques: Optional[list[str]] = None
    clinical_relevance: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "paper_id": self.paper_id,
            "success": self.success,
            "summary": self.summary,
            "methodology_evaluation": self.methodology_evaluation,
            "key_findings": self.key_findings,
            "strengths": self.strengths,
            "limitations": self.limitations,
            "ai_techniques": self.ai_techniques,
            "clinical_relevance": self.clinical_relevance,
            "error": self.error,
        }


class PaperAnalyzer:
    """Analyze papers using Claude LLM."""

    SUMMARY_PROMPT = """You are an expert at analyzing academic papers, particularly those involving artificial intelligence applications in medicine and neurology.

Please analyze the following academic paper and provide:

1. **Summary** (2-3 paragraphs): A comprehensive summary of the paper including the research question, approach, and main conclusions.

2. **Key Findings** (bullet points): List the 3-5 most important findings or contributions.

3. **AI Techniques Used** (bullet points): List any AI, machine learning, or deep learning techniques mentioned (e.g., CNNs, transformers, random forests, etc.).

4. **Clinical Relevance**: Briefly explain the potential clinical applications and impact.

Paper content:
{paper_text}

Please structure your response with clear headers for each section."""

    METHODOLOGY_PROMPT = """You are an expert methodologist specializing in AI/ML research in healthcare and neuroscience.

Please evaluate the methodology of the following academic paper:

1. **Methodology Overview**: Describe the study design and methods used.

2. **Strengths** (bullet points): List 3-5 methodological strengths.

3. **Limitations** (bullet points): List 3-5 methodological limitations or potential concerns.

4. **Data Quality Assessment**: Comment on the dataset size, quality, and appropriateness.

5. **Reproducibility**: Assess whether the methods are described with enough detail to reproduce.

6. **Statistical Rigor**: Evaluate the statistical methods and validation approaches.

7. **Overall Assessment**: Provide a brief overall assessment of the methodology (1-2 sentences).

Paper content:
{paper_text}

Please be constructive but critical in your evaluation. Structure your response with clear headers."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.3,
        api_key: Optional[str] = None,
    ):
        """Initialize the analyzer.

        Args:
            model: Claude model to use.
            max_tokens: Maximum tokens for responses.
            temperature: Sampling temperature.
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var).
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable."
            )

        self.client = anthropic.Anthropic(api_key=api_key)

    def _truncate_text(self, text: str, max_chars: int = 100000) -> str:
        """Truncate text to fit within token limits.

        Args:
            text: Text to truncate.
            max_chars: Maximum characters (rough approximation).

        Returns:
            Truncated text.
        """
        if len(text) <= max_chars:
            return text

        # Keep beginning and end, truncate middle
        half = max_chars // 2
        return (
            text[:half]
            + "\n\n[... content truncated for length ...]\n\n"
            + text[-half:]
        )

    def _call_llm(self, prompt: str) -> str:
        """Make a call to Claude.

        Args:
            prompt: The prompt to send.

        Returns:
            The response text.
        """
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        return message.content[0].text

    def _parse_bullet_points(self, text: str, section_header: str) -> list[str]:
        """Extract bullet points from a section.

        Args:
            text: Full response text.
            section_header: Header to look for.

        Returns:
            List of bullet points.
        """
        lines = text.split("\n")
        in_section = False
        bullets = []

        for line in lines:
            line_lower = line.lower().strip()

            # Check if we've entered the target section
            if section_header.lower() in line_lower and ("**" in line or "#" in line):
                in_section = True
                continue

            # Check if we've left the section
            if in_section and ("**" in line or line.startswith("#")) and section_header.lower() not in line_lower:
                break

            # Collect bullet points
            if in_section and line.strip().startswith(("-", "*", "•")):
                bullet_text = line.strip().lstrip("-*•").strip()
                if bullet_text:
                    bullets.append(bullet_text)

        return bullets

    def summarize(self, paper_text: str, paper_id: str) -> dict:
        """Generate a summary of the paper.

        Args:
            paper_text: Full text of the paper.
            paper_id: Unique identifier.

        Returns:
            Dictionary with summary components.
        """
        truncated = self._truncate_text(paper_text)
        prompt = self.SUMMARY_PROMPT.format(paper_text=truncated)

        response = self._call_llm(prompt)

        return {
            "full_response": response,
            "key_findings": self._parse_bullet_points(response, "Key Findings"),
            "ai_techniques": self._parse_bullet_points(response, "AI Techniques"),
        }

    def evaluate_methodology(self, paper_text: str, paper_id: str) -> dict:
        """Evaluate the methodology of the paper.

        Args:
            paper_text: Full text of the paper.
            paper_id: Unique identifier.

        Returns:
            Dictionary with methodology evaluation.
        """
        truncated = self._truncate_text(paper_text)
        prompt = self.METHODOLOGY_PROMPT.format(paper_text=truncated)

        response = self._call_llm(prompt)

        return {
            "full_response": response,
            "strengths": self._parse_bullet_points(response, "Strengths"),
            "limitations": self._parse_bullet_points(response, "Limitations"),
        }

    def analyze(self, paper_text: str, paper_id: str, title: str = "") -> PaperAnalysis:
        """Perform full analysis of a paper.

        Args:
            paper_text: Full text of the paper.
            paper_id: Unique identifier.
            title: Paper title for context.

        Returns:
            PaperAnalysis with all results.
        """
        try:
            # Add title context if available
            if title:
                paper_text = f"Title: {title}\n\n{paper_text}"

            # Get summary
            summary_result = self.summarize(paper_text, paper_id)

            # Get methodology evaluation
            methodology_result = self.evaluate_methodology(paper_text, paper_id)

            return PaperAnalysis(
                paper_id=paper_id,
                success=True,
                summary=summary_result["full_response"],
                methodology_evaluation=methodology_result["full_response"],
                key_findings=summary_result["key_findings"],
                strengths=methodology_result["strengths"],
                limitations=methodology_result["limitations"],
                ai_techniques=summary_result["ai_techniques"],
            )

        except anthropic.APIError as e:
            return PaperAnalysis(
                paper_id=paper_id,
                success=False,
                error=f"API error: {str(e)}",
            )
        except Exception as e:
            return PaperAnalysis(
                paper_id=paper_id,
                success=False,
                error=f"Analysis failed: {str(e)}",
            )

    def analyze_from_abstract(
        self,
        abstract: str,
        paper_id: str,
        title: str = "",
    ) -> PaperAnalysis:
        """Analyze a paper based on its abstract only.

        This is a fallback when full PDF is not available.

        Args:
            abstract: Paper abstract.
            paper_id: Unique identifier.
            title: Paper title.

        Returns:
            PaperAnalysis with limited results.
        """
        if not abstract:
            return PaperAnalysis(
                paper_id=paper_id,
                success=False,
                error="No abstract available",
            )

        try:
            context = f"Title: {title}\n\nAbstract:\n{abstract}" if title else abstract

            prompt = f"""Based on the following paper abstract, provide:

1. **Summary**: A brief summary of the research (1 paragraph).
2. **Key Points**: The main contributions or findings (2-3 bullet points).
3. **AI Techniques**: Any AI/ML methods mentioned.
4. **Limitations of this analysis**: Note that this analysis is based only on the abstract.

{context}"""

            response = self._call_llm(prompt)

            return PaperAnalysis(
                paper_id=paper_id,
                success=True,
                summary=response,
                key_findings=self._parse_bullet_points(response, "Key Points"),
                ai_techniques=self._parse_bullet_points(response, "AI Techniques"),
                limitations=["Analysis based on abstract only - full paper not available"],
            )

        except Exception as e:
            return PaperAnalysis(
                paper_id=paper_id,
                success=False,
                error=f"Abstract analysis failed: {str(e)}",
            )
