import logging
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from sklearn.preprocessing import MinMaxScaler
import re

from config import settings
from models import Repository, RepositoryMetrics

logger = logging.getLogger(__name__)

@dataclass
class HiddenGemCriteria:
    max_stars: int = 1000
    min_quality_score: float = 0.7
    min_contributors: int = 2
    max_age_days: int = 730  # 2 years
    min_readme_length: int = 200
    require_active_maintenance: bool = True
    max_days_since_push: int = 90

class HiddenGemsDetector:
    def __init__(self, criteria: HiddenGemCriteria = None):
        self.criteria = criteria or HiddenGemCriteria()
        self.scaler = MinMaxScaler()
    
    def calculate_code_quality_indicators(self, repo: Repository) -> Dict[str, float]:
        indicators = {}
        
        # Testing infrastructure score
        testing_score = 0.0
        if repo.has_tests:
            testing_score += 0.6
        
        # Look for test patterns in topics or description
        test_keywords = ['test', 'testing', 'pytest', 'jest', 'unittest', 'mocha', 'jasmine']
        if repo.topics:
            if any(keyword in ' '.join(repo.topics).lower() for keyword in test_keywords):
                testing_score += 0.2
        if repo.description:
            if any(keyword in repo.description.lower() for keyword in test_keywords):
                testing_score += 0.2
        
        indicators['testing'] = min(testing_score, 1.0)
        
        # CI/CD infrastructure score
        ci_score = 0.8 if repo.has_ci else 0.0
        indicators['ci_cd'] = ci_score
        
        # Documentation completeness
        doc_score = 0.0
        if repo.readme_length > 0:
            # Score based on README length (normalized)
            if repo.readme_length >= 1000:
                doc_score += 0.4
            elif repo.readme_length >= 500:
                doc_score += 0.3
            elif repo.readme_length >= 200:
                doc_score += 0.2
        
        if repo.has_documentation:
            doc_score += 0.3
        
        if repo.description and len(repo.description) > 30:
            doc_score += 0.2
        
        # Check for documentation keywords in topics
        doc_keywords = ['documentation', 'docs', 'tutorial', 'guide', 'examples']
        if repo.topics and any(keyword in ' '.join(repo.topics).lower() for keyword in doc_keywords):
            doc_score += 0.1
        
        indicators['documentation'] = min(doc_score, 1.0)
        
        # Code organization score
        org_score = 0.0
        if repo.license_name:
            org_score += 0.3
        
        if len(repo.topics) >= 3:
            org_score += 0.2
        
        # Check for good project structure indicators
        structure_keywords = ['api', 'cli', 'framework', 'library', 'tool', 'sdk']
        if repo.topics and any(keyword in ' '.join(repo.topics).lower() for keyword in structure_keywords):
            org_score += 0.2
        
        # Repository size suggests good structure (not too small, not too large)
        if 100 <= repo.size <= 50000:  # 100KB to 50MB
            org_score += 0.3
        
        indicators['organization'] = min(org_score, 1.0)
        
        return indicators
    
    def calculate_community_engagement(self, repo: Repository) -> Dict[str, float]:
        engagement = {}
        
        # Contributor diversity score
        contrib_score = 0.0
        if repo.contributors_count >= 10:
            contrib_score = 1.0
        elif repo.contributors_count >= 5:
            contrib_score = 0.8
        elif repo.contributors_count >= 3:
            contrib_score = 0.6
        elif repo.contributors_count >= 2:
            contrib_score = 0.4
        else:
            contrib_score = 0.1
        
        engagement['contributor_diversity'] = contrib_score
        
        # Activity ratio (contributors per star)
        if repo.stargazers_count > 0:
            contrib_star_ratio = repo.contributors_count / repo.stargazers_count
            # Higher ratio indicates more active community relative to popularity
            activity_ratio_score = min(contrib_star_ratio * 20, 1.0)  # Scale appropriately
        else:
            activity_ratio_score = 0.0
        
        engagement['activity_ratio'] = activity_ratio_score
        
        # Issue engagement (open issues vs stars)
        if repo.stargazers_count > 0 and repo.open_issues_count > 0:
            issue_engagement = min(repo.open_issues_count / repo.stargazers_count * 10, 1.0)
        else:
            issue_engagement = 0.0
        
        engagement['issue_engagement'] = issue_engagement
        
        # Fork engagement
        if repo.stargazers_count > 0:
            fork_ratio = repo.forks_count / max(repo.stargazers_count, 1)
            fork_engagement = min(fork_ratio * 5, 1.0)
        else:
            fork_engagement = 0.0
        
        engagement['fork_engagement'] = fork_engagement
        
        return engagement
    
    def calculate_innovation_potential(self, repo: Repository) -> Dict[str, float]:
        innovation = {}
        
        # Novelty in AI/ML space
        novelty_score = 0.0
        
        # Check for cutting-edge AI topics
        cutting_edge_topics = [
            'transformer', 'attention', 'gpt', 'llm', 'large-language-model',
            'diffusion', 'stable-diffusion', 'generative', 'multimodal',
            'reinforcement-learning', 'federated-learning', 'few-shot',
            'zero-shot', 'prompt-engineering', 'rag', 'retrieval-augmented',
            'neural-architecture-search', 'automl', 'explainable-ai'
        ]
        
        if repo.topics:
            topic_text = ' '.join(repo.topics).lower()
            cutting_edge_matches = sum(1 for topic in cutting_edge_topics if topic in topic_text)
            novelty_score += min(cutting_edge_matches * 0.2, 0.8)
        
        # Check description for innovation indicators
        if repo.description:
            desc_lower = repo.description.lower()
            innovation_keywords = [
                'novel', 'new', 'innovative', 'breakthrough', 'state-of-the-art',
                'sota', 'cutting-edge', 'advanced', 'next-generation'
            ]
            innovation_matches = sum(1 for keyword in innovation_keywords if keyword in desc_lower)
            novelty_score += min(innovation_matches * 0.1, 0.2)
        
        innovation['novelty'] = min(novelty_score, 1.0)
        
        # Research orientation
        research_score = 0.0
        research_keywords = [
            'paper', 'research', 'arxiv', 'publication', 'experiment',
            'benchmark', 'evaluation', 'dataset', 'model', 'algorithm'
        ]
        
        if repo.topics:
            topic_text = ' '.join(repo.topics).lower()
            research_matches = sum(1 for keyword in research_keywords if keyword in topic_text)
            research_score += min(research_matches * 0.15, 0.6)
        
        if repo.description:
            desc_lower = repo.description.lower()
            research_matches = sum(1 for keyword in research_keywords if keyword in desc_lower)
            research_score += min(research_matches * 0.1, 0.4)
        
        innovation['research_orientation'] = min(research_score, 1.0)
        
        return innovation
    
    def calculate_maintenance_quality(self, repo: Repository) -> Dict[str, float]:
        maintenance = {}
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
        # Convert to timezone-aware if needed
        pushed_at = repo.pushed_at
        updated_at = repo.updated_at
        created_at = repo.created_at
        
        if pushed_at.tzinfo is None:
            pushed_at = pushed_at.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        # Recent activity score
        days_since_push = (now - pushed_at).days
        if days_since_push <= 7:
            activity_score = 1.0
        elif days_since_push <= 30:
            activity_score = 0.8
        elif days_since_push <= 90:
            activity_score = 0.6
        elif days_since_push <= 180:
            activity_score = 0.4
        else:
            activity_score = 0.2
        
        maintenance['recent_activity'] = activity_score
        
        # Consistency of updates
        days_since_update = (now - updated_at).days
        if days_since_update <= days_since_push + 1:
            consistency_score = 1.0
        elif days_since_update <= 30:
            consistency_score = 0.8
        else:
            consistency_score = 0.5
        
        maintenance['update_consistency'] = consistency_score
        
        # Project maturity vs recency balance
        repo_age_days = (now - created_at).days
        if 30 <= repo_age_days <= 365:  # Sweet spot: not too new, not too old
            maturity_score = 1.0
        elif repo_age_days <= 730:  # Up to 2 years
            maturity_score = 0.8
        elif repo_age_days <= 30:  # Very new
            maturity_score = 0.6
        else:  # Older projects
            maturity_score = 0.4
        
        maintenance['maturity_balance'] = maturity_score
        
        return maintenance
    
    def calculate_hidden_gem_score(self, repo: Repository) -> float:
        # Basic eligibility check
        if repo.stargazers_count > self.criteria.max_stars:
            return 0.0
        
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
        # Convert to timezone-aware if needed
        created_at = repo.created_at
        pushed_at = repo.pushed_at
        
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if pushed_at.tzinfo is None:
            pushed_at = pushed_at.replace(tzinfo=timezone.utc)
        
        repo_age_days = (now - created_at).days
        days_since_push = (now - pushed_at).days
        
        if repo_age_days > self.criteria.max_age_days:
            return 0.0
        
        if repo.contributors_count < self.criteria.min_contributors:
            return 0.0
        
        if repo.readme_length < self.criteria.min_readme_length:
            return 0.0
        
        if self.criteria.require_active_maintenance and days_since_push > self.criteria.max_days_since_push:
            return 0.0
        
        # Calculate component scores
        code_quality = self.calculate_code_quality_indicators(repo)
        community = self.calculate_community_engagement(repo)
        innovation = self.calculate_innovation_potential(repo)
        maintenance = self.calculate_maintenance_quality(repo)
        
        # Weighted combination
        weights = {
            'code_quality': 0.3,
            'community': 0.25,
            'innovation': 0.25,
            'maintenance': 0.2
        }
        
        # Average component scores
        code_avg = np.mean(list(code_quality.values()))
        community_avg = np.mean(list(community.values()))
        innovation_avg = np.mean(list(innovation.values()))
        maintenance_avg = np.mean(list(maintenance.values()))
        
        final_score = (
            code_avg * weights['code_quality'] +
            community_avg * weights['community'] +
            innovation_avg * weights['innovation'] +
            maintenance_avg * weights['maintenance']
        )
        
        # Apply star penalty (fewer stars = higher potential)
        star_penalty = min(repo.stargazers_count / self.criteria.max_stars, 1.0)
        star_boost = 1.0 - (star_penalty * 0.2)  # Up to 20% boost for very low stars
        
        final_score *= star_boost
        
        return min(final_score, 1.0)
    
    def detect_hidden_gems(self, repositories: List[Repository], top_k: int = 20) -> List[Tuple[Repository, float, Dict[str, Any]]]:
        logger.info(f"Analyzing {len(repositories)} repositories for hidden gems")
        
        hidden_gems = []
        
        for repo in repositories:
            try:
                score = self.calculate_hidden_gem_score(repo)
                
                if score >= self.criteria.min_quality_score:
                    # Calculate detailed breakdown for insights
                    code_quality = self.calculate_code_quality_indicators(repo)
                    community = self.calculate_community_engagement(repo)
                    innovation = self.calculate_innovation_potential(repo)
                    maintenance = self.calculate_maintenance_quality(repo)
                    
                    insights = {
                        'code_quality': code_quality,
                        'community_engagement': community,
                        'innovation_potential': innovation,
                        'maintenance_quality': maintenance,
                        'overall_score': score
                    }
                    
                    hidden_gems.append((repo, score, insights))
                    
            except Exception as e:
                logger.error(f"Error analyzing {repo.full_name} for hidden gem potential: {e}")
                continue
        
        # Sort by score
        hidden_gems.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"Found {len(hidden_gems)} hidden gems (top {top_k} will be returned)")
        
        return hidden_gems[:top_k]
    
    def generate_hidden_gem_insights(self, hidden_gems: List[Tuple[Repository, float, Dict[str, Any]]]) -> Dict[str, Any]:
        if not hidden_gems:
            return {}
        
        insights = {
            'total_gems_found': len(hidden_gems),
            'average_score': np.mean([gem[1] for gem in hidden_gems]),
            'score_distribution': {},
            'common_characteristics': {},
            'top_languages': {},
            'top_topics': {},
            'age_distribution': {}
        }
        
        # Score distribution
        scores = [gem[1] for gem in hidden_gems]
        insights['score_distribution'] = {
            'min': float(np.min(scores)),
            'max': float(np.max(scores)),
            'median': float(np.median(scores)),
            'std': float(np.std(scores))
        }
        
        # Language distribution
        languages = {}
        for repo, _, _ in hidden_gems:
            if repo.language:
                languages[repo.language] = languages.get(repo.language, 0) + 1
        
        insights['top_languages'] = dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5])
        
        # Topic analysis
        topics = {}
        for repo, _, _ in hidden_gems:
            for topic in repo.topics:
                topics[topic] = topics.get(topic, 0) + 1
        
        insights['top_topics'] = dict(sorted(topics.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Age distribution
        now = datetime.utcnow()
        age_buckets = {'<3 months': 0, '3-6 months': 0, '6-12 months': 0, '1-2 years': 0}
        
        for repo, _, _ in hidden_gems:
            age_days = (now - repo.created_at).days
            if age_days < 90:
                age_buckets['<3 months'] += 1
            elif age_days < 180:
                age_buckets['3-6 months'] += 1
            elif age_days < 365:
                age_buckets['6-12 months'] += 1
            else:
                age_buckets['1-2 years'] += 1
        
        insights['age_distribution'] = age_buckets
        
        # Common characteristics
        total_with_tests = sum(1 for repo, _, _ in hidden_gems if repo.has_tests)
        total_with_ci = sum(1 for repo, _, _ in hidden_gems if repo.has_ci)
        total_with_docs = sum(1 for repo, _, _ in hidden_gems if repo.has_documentation)
        total_with_license = sum(1 for repo, _, _ in hidden_gems if repo.license_name)
        
        insights['common_characteristics'] = {
            'has_tests_percentage': (total_with_tests / len(hidden_gems)) * 100,
            'has_ci_percentage': (total_with_ci / len(hidden_gems)) * 100,
            'has_docs_percentage': (total_with_docs / len(hidden_gems)) * 100,
            'has_license_percentage': (total_with_license / len(hidden_gems)) * 100,
            'avg_contributors': np.mean([repo.contributors_count for repo, _, _ in hidden_gems]),
            'avg_readme_length': np.mean([repo.readme_length for repo, _, _ in hidden_gems])
        }
        
        return insights