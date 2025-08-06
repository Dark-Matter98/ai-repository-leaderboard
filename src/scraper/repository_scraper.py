import logging
from typing import List, Dict, Any, Set
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path

from config import settings
from models import Repository, ContributorInfo, RepositoryMetrics
from .github_client import GitHubClient

logger = logging.getLogger(__name__)

class RepositoryScraper:
    def __init__(self, github_client: GitHubClient = None):
        self.client = github_client or GitHubClient()
        self.scraped_repos: Dict[int, Repository] = {}
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
    
    def build_search_queries(self) -> List[str]:
        queries = []
        
        # Simplified queries that are more likely to work
        # Use individual topics instead of complex OR queries
        primary_topics = ["machine-learning", "artificial-intelligence", "deep-learning", "llm"]
        
        for topic in primary_topics:
            # Basic topic search with stars filter
            queries.append(f"topic:{topic} stars:>{settings.min_stars}")
            
            # Python is the most common AI/ML language
            queries.append(f"topic:{topic} language:python stars:>{settings.min_stars}")
        
        # Add some general searches
        queries.extend([
            "machine-learning stars:>1000",
            "artificial-intelligence stars:>500", 
            "deep-learning stars:>500",
            "neural-network stars:>200",
            "pytorch stars:>100",
            "tensorflow stars:>100"
        ])
        
        return queries
    
    def search_repositories(self, max_results_per_query: int = None) -> Set[int]:
        max_results = max_results_per_query or settings.max_results_per_query
        queries = self.build_search_queries()
        repo_ids = set()
        
        for query in queries:
            logger.info(f"Executing search query: {query}")
            
            page = 1
            results_count = 0
            
            while results_count < max_results:
                try:
                    response = self.client.search_repositories(
                        query=query,
                        per_page=min(100, max_results - results_count),
                        page=page
                    )
                    
                    items = response.get('items', [])
                    if not items:
                        break
                    
                    for item in items:
                        repo_ids.add(item['id'])
                        results_count += 1
                    
                    # GitHub Search API limits to 1000 results total
                    if results_count >= max_results or len(items) < 100:
                        break
                    
                    page += 1
                    
                except Exception as e:
                    logger.error(f"Error searching repositories: {e}")
                    break
        
        logger.info(f"Found {len(repo_ids)} unique repositories across all queries")
        return repo_ids
    
    def scrape_repository_details(self, repo_data: Dict[str, Any]) -> Repository:
        full_name = repo_data['full_name']
        logger.debug(f"Scraping details for {full_name}")
        
        try:
            # Get additional details
            languages = self.client.get_repository_languages(full_name)
            contributors = self.client.get_repository_contributors(full_name)
            readme_content = self.client.get_repository_readme(full_name)
            features = self.client.check_repository_features(full_name)
            
            # Create Repository object
            repo = Repository(
                id=repo_data['id'],
                name=repo_data['name'],
                full_name=full_name,
                description=repo_data.get('description'),
                html_url=repo_data['html_url'],
                clone_url=repo_data['clone_url'],
                
                owner_login=repo_data['owner']['login'],
                owner_type=repo_data['owner']['type'],
                owner_avatar_url=repo_data['owner']['avatar_url'],
                
                stargazers_count=repo_data['stargazers_count'],
                watchers_count=repo_data['watchers_count'],
                forks_count=repo_data['forks_count'],
                open_issues_count=repo_data['open_issues_count'],
                size=repo_data['size'],
                
                language=repo_data.get('language'),
                languages=languages,
                topics=repo_data.get('topics', []),
                license_name=repo_data.get('license', {}).get('name') if repo_data.get('license') else None,
                
                created_at=datetime.fromisoformat(repo_data['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(repo_data['updated_at'].replace('Z', '+00:00')),
                pushed_at=datetime.fromisoformat(repo_data['pushed_at'].replace('Z', '+00:00')),
                
                contributors_count=len(contributors),
                readme_length=len(readme_content) if readme_content else 0,
                readme_content=readme_content or "",
                has_ci=features.get('has_ci', False),
                has_tests=features.get('has_tests', False),
                has_documentation=features.get('has_documentation', False)
            )
            
            return repo
            
        except Exception as e:
            logger.error(f"Error scraping repository {full_name}: {e}")
            # Return basic repository info even if detailed scraping fails
            return Repository(
                id=repo_data['id'],
                name=repo_data['name'],
                full_name=full_name,
                description=repo_data.get('description'),
                html_url=repo_data['html_url'],
                clone_url=repo_data['clone_url'],
                
                owner_login=repo_data['owner']['login'],
                owner_type=repo_data['owner']['type'],
                owner_avatar_url=repo_data['owner']['avatar_url'],
                
                stargazers_count=repo_data['stargazers_count'],
                watchers_count=repo_data['watchers_count'],
                forks_count=repo_data['forks_count'],
                open_issues_count=repo_data['open_issues_count'],
                size=repo_data['size'],
                
                language=repo_data.get('language'),
                topics=repo_data.get('topics', []),
                license_name=repo_data.get('license', {}).get('name') if repo_data.get('license') else None,
                
                created_at=datetime.fromisoformat(repo_data['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(repo_data['updated_at'].replace('Z', '+00:00')),
                pushed_at=datetime.fromisoformat(repo_data['pushed_at'].replace('Z', '+00:00'))
            )
    
    def scrape_repositories_parallel(self, repo_ids: Set[int], max_workers: int = 5) -> List[Repository]:
        repositories = []
        failed_repos = []
        
        # First, get basic repo data for all IDs
        repo_data_map = {}
        for repo_id in repo_ids:
            try:
                # We need to search again to get the repo data by ID
                # This is inefficient but necessary with current GitHub API structure
                pass
            except Exception as e:
                logger.error(f"Could not fetch basic data for repo ID {repo_id}: {e}")
                failed_repos.append(repo_id)
        
        # For now, let's modify this to work with the search results directly
        # We'll collect repo data during the search phase instead
        logger.warning("Parallel scraping needs search results data - using sequential approach")
        return repositories
    
    def scrape_all_repositories(self, max_results_per_query: int = None) -> List[Repository]:
        repositories = []
        queries = self.build_search_queries()
        seen_repo_ids = set()
        
        for query in queries:
            logger.info(f"Processing query: {query}")
            page = 1
            max_results = max_results_per_query or settings.max_results_per_query
            results_count = 0
            
            while results_count < max_results:
                try:
                    response = self.client.search_repositories(
                        query=query,
                        per_page=min(100, max_results - results_count),
                        page=page
                    )
                    
                    items = response.get('items', [])
                    if not items:
                        break
                    
                    for repo_data in items:
                        if repo_data['id'] in seen_repo_ids:
                            continue
                        
                        seen_repo_ids.add(repo_data['id'])
                        
                        try:
                            repo = self.scrape_repository_details(repo_data)
                            repositories.append(repo)
                            results_count += 1
                            
                            # Rate limiting - be conservative
                            if len(repositories) % 10 == 0:
                                logger.info(f"Scraped {len(repositories)} repositories...")
                                
                        except Exception as e:
                            logger.error(f"Failed to scrape {repo_data['full_name']}: {e}")
                            continue
                    
                    if len(items) < 100:
                        break
                    
                    page += 1
                    
                except Exception as e:
                    logger.error(f"Error in search query: {e}")
                    break
        
        logger.info(f"Successfully scraped {len(repositories)} repositories")
        return repositories
    
    def save_repositories(self, repositories: List[Repository], filename: str = None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filename or f"scraped_repos_{timestamp}.json"
        filepath = self.data_dir / filename
        
        # Convert to serializable format
        repo_dicts = []
        for repo in repositories:
            repo_dict = repo.model_dump()
            # Convert datetime objects to strings
            for field in ['created_at', 'updated_at', 'pushed_at']:
                if repo_dict.get(field):
                    repo_dict[field] = repo_dict[field].isoformat()
            repo_dicts.append(repo_dict)
        
        with open(filepath, 'w') as f:
            json.dump(repo_dicts, f, indent=2)
        
        logger.info(f"Saved {len(repositories)} repositories to {filepath}")
        return filepath
    
    def load_repositories(self, filename: str) -> List[Repository]:
        filepath = self.data_dir / filename
        
        with open(filepath, 'r') as f:
            repo_dicts = json.load(f)
        
        repositories = []
        for repo_dict in repo_dicts:
            # Convert datetime strings back to datetime objects
            for field in ['created_at', 'updated_at', 'pushed_at']:
                if repo_dict.get(field):
                    repo_dict[field] = datetime.fromisoformat(repo_dict[field])
            
            repositories.append(Repository(**repo_dict))
        
        logger.info(f"Loaded {len(repositories)} repositories from {filepath}")
        return repositories