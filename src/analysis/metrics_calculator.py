import logging
import numpy as np
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import math

from config import settings
from models import Repository, RepositoryMetrics

logger = logging.getLogger(__name__)

class MetricsCalculator:
    def __init__(self):
        self.weights = {
            'stars': settings.star_weight,
            'recent_activity': settings.recent_activity_weight,
            'contributor_diversity': settings.contributor_diversity_weight,
            'code_quality': settings.code_quality_weight,
            'documentation': settings.documentation_weight
        }
    
    def calculate_momentum_score(self, repo: Repository, historical_data: Dict = None) -> float:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
        # Convert to timezone-aware if needed
        created_at = repo.created_at
        pushed_at = repo.pushed_at
        
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if pushed_at.tzinfo is None:
            pushed_at = pushed_at.replace(tzinfo=timezone.utc)
        
        # Age factor (newer repos get slight boost)
        repo_age_days = (now - created_at).days
        age_factor = max(0.5, 1.0 - (repo_age_days / 365.0) * 0.1)  # Slight decay over years
        
        # Recent activity factor
        days_since_push = (now - pushed_at).days
        if days_since_push <= 7:
            activity_factor = 1.0
        elif days_since_push <= 30:
            activity_factor = 0.8
        elif days_since_push <= 90:
            activity_factor = 0.6
        else:
            activity_factor = 0.3
        
        # Star velocity (stars per day since creation)
        star_velocity = repo.stargazers_count / max(repo_age_days, 1)
        
        # Engagement ratio (stars vs forks vs watchers)
        total_engagement = repo.stargazers_count + repo.forks_count + repo.watchers_count
        if total_engagement > 0:
            star_engagement_ratio = repo.stargazers_count / total_engagement
        else:
            star_engagement_ratio = 0
        
        # Size factor (penalize extremely large repos, boost medium-sized ones)
        if repo.size < 1000:  # < 1MB
            size_factor = 0.8
        elif repo.size < 10000:  # 1-10MB
            size_factor = 1.0
        elif repo.size < 100000:  # 10-100MB
            size_factor = 0.9
        else:  # > 100MB
            size_factor = 0.7
        
        # Combine factors
        momentum_score = (
            math.log(repo.stargazers_count + 1) * 0.4 +
            star_velocity * 100 * 0.2 +
            activity_factor * 0.2 +
            age_factor * 0.1 +
            star_engagement_ratio * 0.05 +
            size_factor * 0.05
        )
        
        return min(momentum_score, 10.0)  # Cap at 10
    
    def calculate_quality_score(self, repo: Repository) -> float:
        score_components = []
        
        # Documentation score
        doc_score = 0.0
        if repo.readme_length > 0:
            if repo.readme_length > 500:
                doc_score += 0.4
            elif repo.readme_length > 200:
                doc_score += 0.3
            else:
                doc_score += 0.2
        
        if repo.has_documentation:
            doc_score += 0.3
        
        if repo.description and len(repo.description) > 20:
            doc_score += 0.2
        
        doc_score = min(doc_score, 1.0)
        score_components.append(('documentation', doc_score))
        
        # Code quality indicators
        code_score = 0.0
        if repo.has_tests:
            code_score += 0.4
        if repo.has_ci:
            code_score += 0.3
        if repo.license_name:
            code_score += 0.2
        if len(repo.topics) >= 3:
            code_score += 0.1
        
        code_score = min(code_score, 1.0)
        score_components.append(('code_quality', code_score))
        
        # Contributor diversity score
        contrib_score = 0.0
        if repo.contributors_count > 0:
            if repo.contributors_count >= 50:
                contrib_score = 1.0
            elif repo.contributors_count >= 20:
                contrib_score = 0.8
            elif repo.contributors_count >= 10:
                contrib_score = 0.6
            elif repo.contributors_count >= 5:
                contrib_score = 0.4
            elif repo.contributors_count >= 2:
                contrib_score = 0.2
            else:
                contrib_score = 0.1
        
        score_components.append(('contributor_diversity', contrib_score))
        
        # Maintenance score
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
        # Convert to timezone-aware if needed
        updated_at = repo.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        
        days_since_update = (now - updated_at).days
        
        if days_since_update <= 30:
            maintenance_score = 1.0
        elif days_since_update <= 90:
            maintenance_score = 0.8
        elif days_since_update <= 180:
            maintenance_score = 0.6
        elif days_since_update <= 365:
            maintenance_score = 0.4
        else:
            maintenance_score = 0.2
        
        score_components.append(('maintenance', maintenance_score))
        
        # Calculate weighted average
        total_score = (
            doc_score * 0.3 +
            code_score * 0.3 +
            contrib_score * 0.2 +
            maintenance_score * 0.2
        )
        
        return min(total_score, 1.0)
    
    def calculate_hidden_gem_potential(self, repo: Repository) -> float:
        if repo.stargazers_count > settings.hidden_gem_max_stars:
            return 0.0
        
        quality_score = self.calculate_quality_score(repo)
        if quality_score < settings.hidden_gem_min_quality_score:
            return 0.0
        
        # Factors that indicate hidden gem potential
        factors = []
        
        # Recent creation with good documentation
        repo_age_days = (datetime.utcnow() - repo.created_at).days
        if repo_age_days < 365 and repo.readme_length > 300:
            factors.append(0.3)
        
        # Good contributor-to-star ratio
        if repo.contributors_count > 0:
            contrib_star_ratio = repo.contributors_count / max(repo.stargazers_count, 1)
            if contrib_star_ratio > 0.05:  # More than 5% contributor ratio
                factors.append(0.2)
        
        # Active maintenance
        days_since_push = (datetime.utcnow() - repo.pushed_at).days
        if days_since_push <= 7:
            factors.append(0.2)
        elif days_since_push <= 30:
            factors.append(0.1)
        
        # Good topic coverage
        if len([t for t in repo.topics if t in settings.ai_topics]) >= 2:
            factors.append(0.15)
        
        # Has testing and CI
        if repo.has_tests and repo.has_ci:
            factors.append(0.15)
        
        hidden_gem_score = quality_score * sum(factors)
        return min(hidden_gem_score, 1.0)
    
    def calculate_repository_metrics(self, repo: Repository, historical_data: Dict = None) -> RepositoryMetrics:
        momentum_score = self.calculate_momentum_score(repo, historical_data)
        quality_score = self.calculate_quality_score(repo)
        
        # Calculate growth metrics if historical data is available
        stars_growth_30d = 0
        stars_growth_7d = 0
        commit_frequency_30d = 0
        
        if historical_data:
            # These would be calculated from historical data
            # For now, we'll estimate based on current data
            pass
        
        # Calculate final composite score
        final_score = (
            momentum_score * 0.4 +
            quality_score * 0.4 +
            (repo.stargazers_count / 10000) * 0.2  # Normalize stars
        )
        final_score = min(final_score, 10.0)
        
        return RepositoryMetrics(
            repo_id=repo.id,
            full_name=repo.full_name,
            stars_growth_30d=stars_growth_30d,
            stars_growth_7d=stars_growth_7d,
            commit_frequency_30d=commit_frequency_30d,
            test_coverage_score=0.8 if repo.has_tests else 0.0,
            documentation_score=min(repo.readme_length / 1000, 1.0),
            code_quality_score=quality_score,
            contributor_diversity_score=min(repo.contributors_count / 50, 1.0),
            calculated_at=datetime.utcnow()
        )
    
    def calculate_all_metrics(self, repositories: List[Repository]) -> Dict[int, RepositoryMetrics]:
        logger.info(f"Calculating metrics for {len(repositories)} repositories")
        
        metrics_map = {}
        for repo in repositories:
            try:
                metrics = self.calculate_repository_metrics(repo)
                metrics_map[repo.id] = metrics
                
                # Update repository with calculated scores
                repo.momentum_score = self.calculate_momentum_score(repo)
                repo.quality_score = self.calculate_quality_score(repo)
                repo.final_score = (repo.momentum_score * 0.5 + repo.quality_score * 5.0) / 2
                
            except Exception as e:
                logger.error(f"Error calculating metrics for {repo.full_name}: {e}")
                continue
        
        logger.info(f"Successfully calculated metrics for {len(metrics_map)} repositories")
        return metrics_map
    
    def rank_repositories(self, repositories: List[Repository]) -> Dict[str, List[Repository]]:
        # Calculate scores for all repositories
        for repo in repositories:
            if repo.final_score == 0.0:
                repo.momentum_score = self.calculate_momentum_score(repo)
                repo.quality_score = self.calculate_quality_score(repo)
                repo.final_score = (repo.momentum_score * 0.5 + repo.quality_score * 5.0) / 2
        
        # Separate into categories
        trending = []
        established = []
        hidden_gems = []
        
        for repo in repositories:
            # Hidden gems: low stars but high quality
            hidden_gem_score = self.calculate_hidden_gem_potential(repo)
            if hidden_gem_score > 0.5:
                hidden_gems.append(repo)
            # Established: high stars
            elif repo.stargazers_count >= 5000:
                established.append(repo)
            # Trending: everything else
            else:
                trending.append(repo)
        
        # Sort each category by final score
        trending.sort(key=lambda x: x.final_score, reverse=True)
        established.sort(key=lambda x: x.final_score, reverse=True)
        hidden_gems.sort(key=lambda x: self.calculate_hidden_gem_potential(x), reverse=True)
        
        return {
            'trending': trending[:50],  # Top 50 trending
            'established': established[:30],  # Top 30 established
            'hidden_gems': hidden_gems[:20]  # Top 20 hidden gems
        }