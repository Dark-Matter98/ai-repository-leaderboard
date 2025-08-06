from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class LanguageEnum(str, Enum):
    PYTHON = "Python"
    JAVASCRIPT = "JavaScript"
    TYPESCRIPT = "TypeScript"
    JAVA = "Java"
    CPP = "C++"
    C = "C"
    GO = "Go"
    RUST = "Rust"
    R = "R"
    JULIA = "Julia"
    OTHER = "Other"

class Repository(BaseModel):
    id: int
    name: str
    full_name: str
    description: Optional[str] = None
    html_url: str
    clone_url: str
    
    # Owner information
    owner_login: str
    owner_type: str  # "User" or "Organization"
    owner_avatar_url: str
    
    # Statistics
    stargazers_count: int
    watchers_count: int
    forks_count: int
    open_issues_count: int
    size: int  # in KB
    
    # Metadata
    language: Optional[str] = None
    languages: Dict[str, int] = Field(default_factory=dict)  # language: bytes
    topics: List[str] = Field(default_factory=list)
    license_name: Optional[str] = None
    
    # Dates
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime
    
    # Additional metrics (populated by scraper)
    contributors_count: int = 0
    readme_length: int = 0
    readme_content: str = ""
    has_ci: bool = False
    has_tests: bool = False
    has_documentation: bool = False
    
    # Calculated scores
    momentum_score: float = 0.0
    quality_score: float = 0.0
    final_score: float = 0.0
    
    # Embedding for clustering
    readme_embedding: Optional[List[float]] = None
    cluster_id: Optional[int] = None

class ContributorInfo(BaseModel):
    login: str
    contributions: int
    avatar_url: str
    html_url: str

class RepositoryMetrics(BaseModel):
    repo_id: int
    full_name: str
    
    # Time-based metrics
    stars_growth_30d: int = 0
    stars_growth_7d: int = 0
    commit_frequency_30d: int = 0
    
    # Quality indicators
    test_coverage_score: float = 0.0  # 0-1
    documentation_score: float = 0.0  # 0-1
    code_quality_score: float = 0.0   # 0-1
    contributor_diversity_score: float = 0.0  # 0-1
    
    # Calculated at last update
    calculated_at: datetime = Field(default_factory=datetime.utcnow)

class Cluster(BaseModel):
    id: int
    name: str
    description: str
    repos: List[int]  # Repository IDs
    center_embedding: List[float]
    size: int

class LeaderboardEntry(BaseModel):
    rank: int
    repository: Repository
    metrics: RepositoryMetrics
    category: str  # "trending", "established", "hidden_gem"
    change_from_previous: Optional[int] = None  # Position change

class Leaderboard(BaseModel):
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    trending: List[LeaderboardEntry] = Field(default_factory=list)
    established: List[LeaderboardEntry] = Field(default_factory=list)
    hidden_gems: List[LeaderboardEntry] = Field(default_factory=list)
    clusters: List[Cluster] = Field(default_factory=list)
    
    # Metadata
    total_repos_analyzed: int = 0
    data_freshness_hours: float = 0.0

class ScrapingJob(BaseModel):
    id: str
    status: str  # "pending", "running", "completed", "failed"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    repos_found: int = 0
    repos_processed: int = 0
    error_message: Optional[str] = None