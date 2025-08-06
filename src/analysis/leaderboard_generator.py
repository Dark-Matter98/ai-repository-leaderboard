import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
from pathlib import Path

from config import settings
from models import Repository, RepositoryMetrics, LeaderboardEntry, Leaderboard, Cluster
from .metrics_calculator import MetricsCalculator
from .hidden_gems_detector import HiddenGemsDetector, HiddenGemCriteria
from .clustering_engine import ClusteringEngine

logger = logging.getLogger(__name__)

class LeaderboardGenerator:
    def __init__(self):
        self.metrics_calculator = MetricsCalculator()
        self.hidden_gems_detector = HiddenGemsDetector()
        self.clustering_engine = ClusteringEngine()
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
    
    def load_previous_leaderboard(self, filename: str = None) -> Optional[Leaderboard]:
        if not filename:
            # Find the most recent leaderboard file
            leaderboard_files = list(self.data_dir.glob("leaderboard_*.json"))
            if not leaderboard_files:
                return None
            filename = max(leaderboard_files, key=lambda f: f.stat().st_mtime).name
        
        filepath = self.data_dir / filename
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Convert back to Leaderboard object
            leaderboard = Leaderboard(**data)
            logger.info(f"Loaded previous leaderboard from {filepath}")
            return leaderboard
            
        except Exception as e:
            logger.warning(f"Could not load previous leaderboard: {e}")
            return None
    
    def calculate_position_changes(self, current_entries: List[LeaderboardEntry], previous_leaderboard: Optional[Leaderboard], category: str) -> List[LeaderboardEntry]:
        if not previous_leaderboard:
            return current_entries
        
        # Get previous entries for the category
        previous_entries = getattr(previous_leaderboard, category, [])
        previous_positions = {entry.repository.id: entry.rank for entry in previous_entries}
        
        # Update current entries with position changes
        for entry in current_entries:
            repo_id = entry.repository.id
            if repo_id in previous_positions:
                previous_rank = previous_positions[repo_id]
                entry.change_from_previous = previous_rank - entry.rank
            else:
                entry.change_from_previous = None  # New entry
        
        return current_entries
    
    def create_trending_leaderboard(self, repositories: List[Repository], previous_leaderboard: Optional[Leaderboard] = None) -> List[LeaderboardEntry]:
        # Filter for trending criteria (active repos with moderate to high stars)
        trending_repos = []
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
        for repo in repositories:
            # Convert to timezone-aware if needed
            pushed_at = repo.pushed_at
            created_at = repo.created_at
            
            if pushed_at.tzinfo is None:
                pushed_at = pushed_at.replace(tzinfo=timezone.utc)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            
            # Trending criteria
            days_since_push = (now - pushed_at).days
            repo_age_days = (now - created_at).days
            
            if (repo.stargazers_count >= 100 and 
                repo.stargazers_count <= 10000 and
                days_since_push <= 90 and
                repo_age_days >= 30):  # At least 30 days old
                trending_repos.append(repo)
        
        # Calculate scores and sort
        for repo in trending_repos:
            if repo.final_score == 0.0:
                repo.momentum_score = self.metrics_calculator.calculate_momentum_score(repo)
                repo.quality_score = self.metrics_calculator.calculate_quality_score(repo)
                repo.final_score = repo.momentum_score * 0.7 + repo.quality_score * 3.0
        
        trending_repos.sort(key=lambda x: x.final_score, reverse=True)
        
        # Create leaderboard entries
        entries = []
        for rank, repo in enumerate(trending_repos[:50], 1):
            entry = LeaderboardEntry(
                rank=rank,
                repository=repo,
                metrics=self.metrics_calculator.calculate_repository_metrics(repo),
                category="trending"
            )
            entries.append(entry)
        
        # Calculate position changes
        entries = self.calculate_position_changes(entries, previous_leaderboard, "trending")
        
        logger.info(f"Generated trending leaderboard with {len(entries)} entries")
        return entries
    
    def create_established_leaderboard(self, repositories: List[Repository], previous_leaderboard: Optional[Leaderboard] = None) -> List[LeaderboardEntry]:
        # Filter for established repos (high stars, mature)
        established_repos = []
        now = datetime.utcnow()
        
        for repo in repositories:
            repo_age_days = (now - repo.created_at).days
            
            if (repo.stargazers_count >= 5000 and 
                repo_age_days >= 180):  # At least 6 months old
                established_repos.append(repo)
        
        # Calculate scores focusing on quality and community
        for repo in established_repos:
            if repo.final_score == 0.0:
                repo.momentum_score = self.metrics_calculator.calculate_momentum_score(repo)
                repo.quality_score = self.metrics_calculator.calculate_quality_score(repo)
                # For established repos, weight quality higher
                repo.final_score = repo.momentum_score * 0.3 + repo.quality_score * 5.0 + (repo.stargazers_count / 1000) * 0.1
        
        established_repos.sort(key=lambda x: x.final_score, reverse=True)
        
        # Create leaderboard entries
        entries = []
        for rank, repo in enumerate(established_repos[:30], 1):
            entry = LeaderboardEntry(
                rank=rank,
                repository=repo,
                metrics=self.metrics_calculator.calculate_repository_metrics(repo),
                category="established"
            )
            entries.append(entry)
        
        # Calculate position changes
        entries = self.calculate_position_changes(entries, previous_leaderboard, "established")
        
        logger.info(f"Generated established leaderboard with {len(entries)} entries")
        return entries
    
    def create_hidden_gems_leaderboard(self, repositories: List[Repository], previous_leaderboard: Optional[Leaderboard] = None) -> List[LeaderboardEntry]:
        # Use hidden gems detector to find gems
        hidden_gems_results = self.hidden_gems_detector.detect_hidden_gems(repositories, top_k=20)
        
        # Create leaderboard entries
        entries = []
        for rank, (repo, score, insights) in enumerate(hidden_gems_results, 1):
            # Update repository with hidden gem score
            repo.final_score = score
            
            entry = LeaderboardEntry(
                rank=rank,
                repository=repo,
                metrics=self.metrics_calculator.calculate_repository_metrics(repo),
                category="hidden_gem"
            )
            entries.append(entry)
        
        # Calculate position changes
        entries = self.calculate_position_changes(entries, previous_leaderboard, "hidden_gems")
        
        logger.info(f"Generated hidden gems leaderboard with {len(entries)} entries")
        return entries
    
    def generate_clusters(self, repositories: List[Repository]) -> List[Cluster]:
        # Perform clustering
        repo_clusters, clusters_dict = self.clustering_engine.cluster_repositories(repositories)
        
        # Convert to list and sort by size
        clusters = list(clusters_dict.values())
        clusters.sort(key=lambda x: x.size, reverse=True)
        
        logger.info(f"Generated {len(clusters)} clusters")
        return clusters
    
    def calculate_data_freshness(self, repositories: List[Repository]) -> float:
        if not repositories:
            return 0.0
        
        now = datetime.utcnow()
        # Use the most recent repository update as a proxy for data freshness
        most_recent_update = max(repo.updated_at for repo in repositories)
        hours_since_update = (now - most_recent_update).total_seconds() / 3600
        
        return hours_since_update
    
    def generate_leaderboard(self, repositories: List[Repository], include_clustering: bool = True) -> Leaderboard:
        logger.info(f"Generating leaderboard for {len(repositories)} repositories")
        
        # Load previous leaderboard for position tracking
        previous_leaderboard = self.load_previous_leaderboard()
        
        # Calculate all metrics
        metrics_map = self.metrics_calculator.calculate_all_metrics(repositories)
        
        # Generate leaderboard categories
        trending = self.create_trending_leaderboard(repositories, previous_leaderboard)
        established = self.create_established_leaderboard(repositories, previous_leaderboard)
        hidden_gems = self.create_hidden_gems_leaderboard(repositories, previous_leaderboard)
        
        # Generate clusters if requested
        clusters = []
        if include_clustering:
            clusters = self.generate_clusters(repositories)
        
        # Calculate data freshness
        data_freshness_hours = self.calculate_data_freshness(repositories)
        
        # Create leaderboard
        leaderboard = Leaderboard(
            generated_at=datetime.utcnow(),
            trending=trending,
            established=established,
            hidden_gems=hidden_gems,
            clusters=clusters,
            total_repos_analyzed=len(repositories),
            data_freshness_hours=data_freshness_hours
        )
        
        logger.info(f"Generated complete leaderboard: {len(trending)} trending, {len(established)} established, {len(hidden_gems)} hidden gems")
        
        return leaderboard
    
    def save_leaderboard(self, leaderboard: Leaderboard, filename: str = None) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filename or f"leaderboard_{timestamp}.json"
        filepath = self.data_dir / filename
        
        # Convert to serializable format
        leaderboard_dict = leaderboard.model_dump()
        
        # Convert datetime objects to strings
        def convert_datetime(obj):
            if isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()
            else:
                return obj
        
        leaderboard_dict = convert_datetime(leaderboard_dict)
        
        with open(filepath, 'w') as f:
            json.dump(leaderboard_dict, f, indent=2)
        
        logger.info(f"Saved leaderboard to {filepath}")
        return filepath
    
    def generate_summary_stats(self, leaderboard: Leaderboard) -> Dict[str, Any]:
        stats = {
            'generation_time': leaderboard.generated_at.isoformat(),
            'total_repositories': leaderboard.total_repos_analyzed,
            'data_freshness_hours': leaderboard.data_freshness_hours,
            'categories': {
                'trending': len(leaderboard.trending),
                'established': len(leaderboard.established),
                'hidden_gems': len(leaderboard.hidden_gems)
            },
            'clusters': len(leaderboard.clusters),
            'top_languages': {},
            'top_topics': {},
            'position_changes': {
                'trending_new': 0,
                'trending_up': 0,
                'trending_down': 0,
                'established_new': 0,
                'established_up': 0,
                'established_down': 0,
                'hidden_gems_new': 0
            }
        }
        
        # Analyze all repositories across categories
        all_repos = []
        all_repos.extend([entry.repository for entry in leaderboard.trending])
        all_repos.extend([entry.repository for entry in leaderboard.established])
        all_repos.extend([entry.repository for entry in leaderboard.hidden_gems])
        
        # Language distribution
        languages = {}
        for repo in all_repos:
            if repo.language:
                languages[repo.language] = languages.get(repo.language, 0) + 1
        stats['top_languages'] = dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Topic distribution
        topics = {}
        for repo in all_repos:
            for topic in repo.topics:
                topics[topic] = topics.get(topic, 0) + 1
        stats['top_topics'] = dict(sorted(topics.items(), key=lambda x: x[1], reverse=True)[:15])
        
        # Position changes analysis
        for category in ['trending', 'established', 'hidden_gems']:
            entries = getattr(leaderboard, category, [])
            for entry in entries:
                if entry.change_from_previous is None:
                    stats['position_changes'][f'{category}_new'] += 1
                elif entry.change_from_previous > 0:
                    stats['position_changes'][f'{category}_up'] += 1
                elif entry.change_from_previous < 0:
                    stats['position_changes'][f'{category}_down'] += 1
        
        return stats
    
    def update_leaderboard_with_historical_data(self, leaderboard: Leaderboard, historical_data: Dict[int, Dict] = None):
        if not historical_data:
            return leaderboard
        
        # Update metrics with historical growth data
        all_entries = leaderboard.trending + leaderboard.established + leaderboard.hidden_gems
        
        for entry in all_entries:
            repo_id = entry.repository.id
            if repo_id in historical_data:
                hist_data = historical_data[repo_id]
                
                # Update growth metrics
                entry.metrics.stars_growth_30d = hist_data.get('stars_growth_30d', 0)
                entry.metrics.stars_growth_7d = hist_data.get('stars_growth_7d', 0)
                entry.metrics.commit_frequency_30d = hist_data.get('commit_frequency_30d', 0)
                
                # Recalculate final scores with growth data
                growth_factor = 1.0 + (entry.metrics.stars_growth_30d / max(entry.repository.stargazers_count, 1))
                entry.repository.final_score *= min(growth_factor, 2.0)  # Cap growth boost
        
        # Re-sort categories by updated scores
        leaderboard.trending.sort(key=lambda x: x.repository.final_score, reverse=True)
        leaderboard.established.sort(key=lambda x: x.repository.final_score, reverse=True)
        leaderboard.hidden_gems.sort(key=lambda x: x.repository.final_score, reverse=True)
        
        # Update ranks
        for rank, entry in enumerate(leaderboard.trending, 1):
            entry.rank = rank
        for rank, entry in enumerate(leaderboard.established, 1):
            entry.rank = rank
        for rank, entry in enumerate(leaderboard.hidden_gems, 1):
            entry.rank = rank
        
        return leaderboard