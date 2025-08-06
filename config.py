import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    cache_ttl: int = 3600  # 1 hour
    daily_update_time: str = "06:00"  # UTC
    
    # Search parameters
    min_stars: int = 50
    max_results_per_query: int = 100
    ai_topics: List[str] = [
        "machine-learning",
        "artificial-intelligence", 
        "deep-learning",
        "natural-language-processing",
        "llm",
        "rag",
        "computer-vision",
        "nlp",
        "transformers"
    ]
    
    # Scoring weights
    star_weight: float = 0.3
    recent_activity_weight: float = 0.25
    contributor_diversity_weight: float = 0.2
    code_quality_weight: float = 0.15
    documentation_weight: float = 0.1
    
    # Hidden gems criteria
    hidden_gem_max_stars: int = 1000
    hidden_gem_min_quality_score: float = 0.7
    
    class Config:
        env_file = ".env"

settings = Settings()