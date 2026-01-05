from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Iterable
import re
from difflib import SequenceMatcher

from .models import PowerSpec


@dataclass
class RouteMatch:
    name: str
    score: int
    reasons: list[str]


def _calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two strings using sequence matching."""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text."""
    # Remove common stop words and extract meaningful terms
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
        'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
    }
    
    # Extract words (alphanumeric sequences)
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
    
    # Filter out stop words and short words
    keywords = {word for word in words if len(word) > 2 and word not in stop_words}
    
    return keywords


def _score_keyword_overlap(prompt_keywords: set[str], target_keywords: set[str]) -> float:
    """Score keyword overlap between prompt and target."""
    if not prompt_keywords or not target_keywords:
        return 0.0
    
    intersection = prompt_keywords & target_keywords
    union = prompt_keywords | target_keywords
    
    # Jaccard similarity
    return len(intersection) / len(union) if union else 0.0


def score_power(
    spec: PowerSpec, prompt: str, files: Iterable[str] | None = None
) -> RouteMatch:
    """Score a power against a prompt with improved intelligence."""
    score = 0
    reasons: list[str] = []
    prompt_lower = prompt.lower()
    prompt_keywords = _extract_keywords(prompt)

    # Exact phrase matching (highest weight)
    for phrase in spec.triggers.phrases:
        phrase_lower = phrase.lower()
        if phrase_lower in prompt_lower:
            score += 10  # Increased from 3
            reasons.append(f"exact_phrase:{phrase}")
        else:
            # Fuzzy phrase matching
            similarity = _calculate_similarity(phrase_lower, prompt_lower)
            if similarity > 0.6:  # 60% similarity threshold
                fuzzy_score = int(similarity * 5)  # 0-5 points
                score += fuzzy_score
                reasons.append(f"fuzzy_phrase:{phrase}({similarity:.2f})")

    # Domain matching with keyword overlap
    for domain in spec.triggers.domains:
        domain_lower = domain.lower()
        if domain_lower in prompt_lower:
            score += 5  # Increased from 2
            reasons.append(f"exact_domain:{domain}")
        else:
            # Check if domain keywords overlap with prompt
            domain_keywords = _extract_keywords(domain)
            overlap_score = _score_keyword_overlap(prompt_keywords, domain_keywords)
            if overlap_score > 0.3:  # 30% overlap threshold
                keyword_score = int(overlap_score * 3)  # 0-3 points
                score += keyword_score
                reasons.append(f"keyword_domain:{domain}({overlap_score:.2f})")

    # Enhanced file pattern matching
    if files:
        for pattern in spec.triggers.files:
            matched_files = [f for f in files if fnmatch(f, pattern)]
            if matched_files:
                # Score based on number of matching files
                file_score = min(len(matched_files) * 2, 8)  # Cap at 8 points
                score += file_score
                reasons.append(f"files:{pattern}({len(matched_files)})")

    # Semantic matching based on description
    if spec.meta.description:
        desc_keywords = _extract_keywords(spec.meta.description)
        desc_overlap = _score_keyword_overlap(prompt_keywords, desc_keywords)
        if desc_overlap > 0.2:  # 20% overlap threshold
            semantic_score = int(desc_overlap * 4)  # 0-4 points
            score += semantic_score
            reasons.append(f"semantic:{spec.meta.name}({desc_overlap:.2f})")

    # Boost score for powers with more comprehensive triggers
    trigger_completeness = (
        (1 if spec.triggers.phrases else 0) +
        (1 if spec.triggers.domains else 0) +
        (1 if spec.triggers.files else 0)
    )
    if trigger_completeness > 1:
        score += trigger_completeness  # 1-3 bonus points
        reasons.append(f"completeness_bonus:{trigger_completeness}")

    return RouteMatch(name=spec.meta.name, score=score, reasons=reasons)


def select_powers(
    specs: Iterable[PowerSpec], prompt: str, files: Iterable[str] | None = None,
    min_score: int = 1, max_results: int = 10
) -> list[RouteMatch]:
    """Select and rank powers with improved intelligence.
    
    Args:
        specs: Available power specifications
        prompt: User prompt to match against
        files: Optional file paths for context
        min_score: Minimum score threshold for inclusion
        max_results: Maximum number of results to return
        
    Returns:
        List of matching powers, ranked by score
    """
    matches = [score_power(spec, prompt, files=files) for spec in specs]
    
    # Filter by minimum score and sort by score (descending)
    ranked = [match for match in matches if match.score >= min_score]
    ranked.sort(key=lambda match: match.score, reverse=True)
    
    # Limit results
    return ranked[:max_results]
