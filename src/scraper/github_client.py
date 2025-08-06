import requests
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import settings
from models import Repository, ContributorInfo

logger = logging.getLogger(__name__)

class GitHubClient:
    def __init__(self, token: str = None):
        self.token = token or settings.github_token
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json"
            })
        
        self.rate_limit_remaining = None
        self.rate_limit_reset = None
    
    def _handle_rate_limit(self, response: requests.Response):
        self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
        self.rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', 0))
        
        if response.status_code == 403 and 'rate limit' in response.text.lower():
            reset_time = datetime.fromtimestamp(self.rate_limit_reset)
            sleep_time = (reset_time - datetime.now()).total_seconds() + 10
            logger.warning(f"Rate limit hit. Sleeping for {sleep_time} seconds")
            time.sleep(max(sleep_time, 0))
            return True
        return False
    
    def _make_request(self, url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                
                if self._handle_rate_limit(response):
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise
        
        raise Exception(f"Failed to make request after {max_retries} attempts")
    
    def search_repositories(
        self, 
        query: str, 
        sort: str = "stars", 
        order: str = "desc",
        per_page: int = 100,
        page: int = 1
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/search/repositories"
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": per_page,
            "page": page
        }
        
        logger.info(f"Searching repositories: {query} (page {page})")
        return self._make_request(url, params)
    
    def get_repository_details(self, full_name: str) -> Dict[str, Any]:
        url = f"{self.base_url}/repos/{full_name}"
        return self._make_request(url)
    
    def get_repository_languages(self, full_name: str) -> Dict[str, int]:
        url = f"{self.base_url}/repos/{full_name}/languages"
        return self._make_request(url)
    
    def get_repository_contributors(self, full_name: str, per_page: int = 100) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/repos/{full_name}/contributors"
        params = {"per_page": per_page, "anon": "false"}
        return self._make_request(url, params)
    
    def get_repository_readme(self, full_name: str) -> Optional[str]:
        try:
            url = f"{self.base_url}/repos/{full_name}/readme"
            response = self._make_request(url)
            
            # README content is base64 encoded
            import base64
            content = base64.b64decode(response.get('content', '')).decode('utf-8')
            return content
        except Exception as e:
            logger.warning(f"Could not fetch README for {full_name}: {e}")
            return None
    
    def get_repository_commits(self, full_name: str, since: str = None, per_page: int = 100) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/repos/{full_name}/commits"
        params = {"per_page": per_page}
        if since:
            params["since"] = since
        return self._make_request(url, params)
    
    def check_repository_features(self, full_name: str) -> Dict[str, bool]:
        # Simplified feature detection to avoid excessive API calls
        features = {
            "has_ci": False,
            "has_tests": False, 
            "has_documentation": True  # Assume most repos have some documentation
        }
        
        # For now, just return basic assumptions to speed up scraping
        # This can be enhanced later with more intelligent checks
        return features
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        url = f"{self.base_url}/rate_limit"
        return self._make_request(url)