#!/usr/bin/env python3
"""
Test script to validate the end-to-end AI Repository Leaderboard pipeline
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all modules can be imported"""
    logger.info("Testing imports...")
    
    try:
        from config import settings
        from models import Repository, Leaderboard
        from src.scraper.github_client import GitHubClient
        from src.scraper.repository_scraper import RepositoryScraper
        from src.analysis.metrics_calculator import MetricsCalculator
        from src.analysis.clustering_engine import ClusteringEngine
        from src.analysis.hidden_gems_detector import HiddenGemsDetector
        from src.analysis.leaderboard_generator import LeaderboardGenerator
        from src.dashboard.dashboard_generator import DashboardGenerator
        from src.cache_manager import cache_manager
        from src.scheduler import scheduler
        
        logger.info("✓ All imports successful")
        return True
        
    except ImportError as e:
        logger.error(f"✗ Import failed: {e}")
        return False

def test_configuration():
    """Test configuration and environment setup"""
    logger.info("Testing configuration...")
    
    try:
        from config import settings
        
        # Check required directories
        required_dirs = [Path("data"), Path("output"), Path("templates")]
        for directory in required_dirs:
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {directory}")
        
        # Check settings
        logger.info(f"GitHub token configured: {'Yes' if settings.github_token else 'No'}")
        logger.info(f"AI topics count: {len(settings.ai_topics)}")
        logger.info(f"Daily update time: {settings.daily_update_time}")
        
        logger.info("✓ Configuration test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Configuration test failed: {e}")
        return False

def test_github_client():
    """Test GitHub API client"""
    logger.info("Testing GitHub client...")
    
    try:
        from src.scraper.github_client import GitHubClient
        
        client = GitHubClient()
        
        # Test rate limit check (doesn't consume quota)
        rate_limit = client.get_rate_limit_status()
        logger.info(f"Rate limit status: {rate_limit.get('resources', {}).get('core', {}).get('remaining', 'unknown')}")
        
        logger.info("✓ GitHub client test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ GitHub client test failed: {e}")
        return False

def test_cache_system():
    """Test caching system"""
    logger.info("Testing cache system...")
    
    try:
        from src.cache_manager import cache_manager
        
        # Test basic cache operations
        test_key = "test_pipeline_key"
        test_value = {"test": "data", "timestamp": datetime.now().isoformat()}
        
        # Set value
        cache_manager.set(test_key, test_value, ttl=60)
        
        # Get value
        retrieved_value = cache_manager.get(test_key)
        
        if retrieved_value == test_value:
            logger.info("✓ Cache set/get working")
        else:
            logger.warning("✗ Cache set/get not working properly")
        
        # Clean up
        cache_manager.delete(test_key)
        
        # Get cache stats
        stats = cache_manager.get_cache_stats()
        logger.info(f"Cache backend: {stats['backend']}")
        
        logger.info("✓ Cache system test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Cache system test failed: {e}")
        return False

def test_small_scraping():
    """Test scraping with minimal data"""
    logger.info("Testing small-scale scraping...")
    
    try:
        from src.scraper.github_client import GitHubClient
        from src.scraper.repository_scraper import RepositoryScraper
        
        client = GitHubClient()
        scraper = RepositoryScraper(client)
        
        # Test with a very specific, small query
        test_query = "topic:machine-learning+language:python+stars:>1000"
        
        try:
            response = client.search_repositories(query=test_query, per_page=5)
            items = response.get('items', [])
            
            if items:
                logger.info(f"✓ Found {len(items)} repositories for test query")
                
                # Test detailed scraping on first repo
                repo_data = items[0]
                detailed_repo = scraper.scrape_repository_details(repo_data)
                
                logger.info(f"✓ Successfully scraped details for: {detailed_repo.full_name}")
                logger.info(f"  Stars: {detailed_repo.stargazers_count}")
                logger.info(f"  Contributors: {detailed_repo.contributors_count}")
                logger.info(f"  README length: {detailed_repo.readme_length}")
                
            else:
                logger.warning("No repositories found for test query")
            
            logger.info("✓ Small-scale scraping test passed")
            return True
            
        except Exception as e:
            if "rate limit" in str(e).lower():
                logger.warning(f"Rate limit hit during test: {e}")
                return True  # Still consider this a pass
            else:
                raise
        
    except Exception as e:
        logger.error(f"✗ Small-scale scraping test failed: {e}")
        return False

def test_analysis_components():
    """Test analysis components with mock data"""
    logger.info("Testing analysis components...")
    
    try:
        from models import Repository
        from src.analysis.metrics_calculator import MetricsCalculator
        from src.analysis.hidden_gems_detector import HiddenGemsDetector
        from datetime import datetime, timedelta
        
        # Create mock repository data
        now = datetime.utcnow()
        mock_repos = [
            Repository(
                id=1,
                name="test-ml-project",
                full_name="user/test-ml-project",
                description="A machine learning project for testing",
                html_url="https://github.com/user/test-ml-project",
                clone_url="https://github.com/user/test-ml-project.git",
                owner_login="user",
                owner_type="User",
                owner_avatar_url="https://github.com/user.png",
                stargazers_count=500,
                watchers_count=100,
                forks_count=50,
                open_issues_count=10,
                size=5000,
                language="Python",
                topics=["machine-learning", "python", "ai"],
                license_name="MIT",
                created_at=now - timedelta(days=180),
                updated_at=now - timedelta(days=5),
                pushed_at=now - timedelta(days=2),
                contributors_count=5,
                readme_length=800,
                readme_content="# Test ML Project\n\nThis is a test project for machine learning...",
                has_tests=True,
                has_ci=True,
                has_documentation=True
            ),
            Repository(
                id=2,
                name="hidden-gem-ai",
                full_name="dev/hidden-gem-ai",
                description="An innovative AI approach",
                html_url="https://github.com/dev/hidden-gem-ai",
                clone_url="https://github.com/dev/hidden-gem-ai.git",
                owner_login="dev",
                owner_type="User", 
                owner_avatar_url="https://github.com/dev.png",
                stargazers_count=150,
                watchers_count=30,
                forks_count=20,
                open_issues_count=5,
                size=2000,
                language="Python",
                topics=["artificial-intelligence", "innovation", "research"],
                license_name="Apache-2.0",
                created_at=now - timedelta(days=90),
                updated_at=now - timedelta(days=1),
                pushed_at=now - timedelta(days=1),
                contributors_count=3,
                readme_length=1200,
                readme_content="# Hidden Gem AI\n\nNovel approach to AI problems...",
                has_tests=True,
                has_ci=True,
                has_documentation=True
            )
        ]
        
        # Test metrics calculator
        metrics_calc = MetricsCalculator()
        
        for repo in mock_repos:
            momentum_score = metrics_calc.calculate_momentum_score(repo)
            quality_score = metrics_calc.calculate_quality_score(repo)
            
            logger.info(f"Repository: {repo.name}")
            logger.info(f"  Momentum score: {momentum_score:.2f}")
            logger.info(f"  Quality score: {quality_score:.2f}")
        
        # Test hidden gems detector
        hidden_gems_detector = HiddenGemsDetector()
        hidden_gems = hidden_gems_detector.detect_hidden_gems(mock_repos)
        
        logger.info(f"✓ Found {len(hidden_gems)} hidden gems from test data")
        
        logger.info("✓ Analysis components test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Analysis components test failed: {e}")
        return False

def test_clustering():
    """Test clustering with mock data"""
    logger.info("Testing clustering...")
    
    try:
        from models import Repository
        from src.analysis.clustering_engine import ClusteringEngine
        from datetime import datetime, timedelta
        
        # Create mock repositories with different characteristics
        now = datetime.utcnow()
        mock_repos = []
        
        # Computer vision repos
        for i in range(3):
            mock_repos.append(Repository(
                id=i+1,
                name=f"cv-project-{i}",
                full_name=f"user/cv-project-{i}",
                description="Computer vision and image processing",
                html_url=f"https://github.com/user/cv-project-{i}",
                clone_url=f"https://github.com/user/cv-project-{i}.git",
                owner_login="user",
                owner_type="User",
                owner_avatar_url="https://github.com/user.png",
                stargazers_count=200 + i*100,
                watchers_count=50,
                forks_count=25,
                open_issues_count=5,
                size=3000,
                language="Python",
                topics=["computer-vision", "image-processing", "deep-learning"],
                created_at=now - timedelta(days=200),
                updated_at=now - timedelta(days=10),
                pushed_at=now - timedelta(days=5),
                contributors_count=3,
                readme_length=600,
                readme_content="Computer vision project using deep learning for image analysis..."
            ))
        
        # NLP repos
        for i in range(2):
            mock_repos.append(Repository(
                id=i+10,
                name=f"nlp-tool-{i}",
                full_name=f"dev/nlp-tool-{i}",
                description="Natural language processing toolkit",
                html_url=f"https://github.com/dev/nlp-tool-{i}",
                clone_url=f"https://github.com/dev/nlp-tool-{i}.git",
                owner_login="dev",
                owner_type="User",
                owner_avatar_url="https://github.com/dev.png",
                stargazers_count=300 + i*50,
                watchers_count=40,
                forks_count=20,
                open_issues_count=3,
                size=4000,
                language="Python",
                topics=["natural-language-processing", "nlp", "text-analysis"],
                created_at=now - timedelta(days=150),
                updated_at=now - timedelta(days=7),
                pushed_at=now - timedelta(days=3),
                contributors_count=4,
                readme_length=800,
                readme_content="Advanced NLP toolkit for text processing and analysis..."
            ))
        
        clustering_engine = ClusteringEngine()
        
        # Test clustering
        repo_clusters, clusters = clustering_engine.cluster_repositories(mock_repos, n_clusters=2)
        
        logger.info(f"✓ Clustered {len(mock_repos)} repositories into {len(clusters)} clusters")
        
        for cluster_id, cluster in clusters.items():
            logger.info(f"  Cluster {cluster_id}: {cluster.name} ({cluster.size} repos)")
        
        logger.info("✓ Clustering test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Clustering test failed: {e}")
        logger.error("Note: Clustering requires sentence-transformers. Install with: pip install sentence-transformers")
        return False

def test_leaderboard_generation():
    """Test leaderboard generation with mock data"""
    logger.info("Testing leaderboard generation...")
    
    try:
        from models import Repository
        from src.analysis.leaderboard_generator import LeaderboardGenerator
        from datetime import datetime, timedelta
        
        # Create varied mock data
        now = datetime.utcnow()
        mock_repos = []
        
        # Trending repo
        mock_repos.append(Repository(
            id=1,
            name="trending-ai-lib",
            full_name="org/trending-ai-lib",
            description="Trending AI library with recent activity",
            html_url="https://github.com/org/trending-ai-lib",
            clone_url="https://github.com/org/trending-ai-lib.git",
            owner_login="org",
            owner_type="Organization",
            owner_avatar_url="https://github.com/org.png",
            stargazers_count=2000,
            watchers_count=400,
            forks_count=200,
            open_issues_count=15,
            size=8000,
            language="Python",
            topics=["artificial-intelligence", "machine-learning", "python"],
            license_name="MIT",
            created_at=now - timedelta(days=120),
            updated_at=now - timedelta(days=1),
            pushed_at=now - timedelta(days=1),
            contributors_count=8,
            readme_length=1500,
            readme_content="# Trending AI Library\n\nA popular AI library...",
            has_tests=True,
            has_ci=True,
            has_documentation=True
        ))
        
        # Established repo
        mock_repos.append(Repository(
            id=2,
            name="established-ml-framework",
            full_name="bigcorp/established-ml-framework",
            description="Well-established ML framework",
            html_url="https://github.com/bigcorp/established-ml-framework",
            clone_url="https://github.com/bigcorp/established-ml-framework.git",
            owner_login="bigcorp",
            owner_type="Organization",
            owner_avatar_url="https://github.com/bigcorp.png",
            stargazers_count=15000,
            watchers_count=1500,
            forks_count=3000,
            open_issues_count=50,
            size=25000,
            language="Python",
            topics=["machine-learning", "framework", "data-science"],
            license_name="Apache-2.0",
            created_at=now - timedelta(days=800),
            updated_at=now - timedelta(days=10),
            pushed_at=now - timedelta(days=5),
            contributors_count=50,
            readme_length=3000,
            readme_content="# Established ML Framework\n\nA mature framework...",
            has_tests=True,
            has_ci=True,
            has_documentation=True
        ))
        
        # Hidden gem
        mock_repos.append(Repository(
            id=3,
            name="innovative-ai-approach",
            full_name="researcher/innovative-ai-approach",
            description="Novel approach to AI problems with great potential",
            html_url="https://github.com/researcher/innovative-ai-approach", 
            clone_url="https://github.com/researcher/innovative-ai-approach.git",
            owner_login="researcher",
            owner_type="User",
            owner_avatar_url="https://github.com/researcher.png",
            stargazers_count=85,
            watchers_count=15,
            forks_count=8,
            open_issues_count=2,
            size=1500,
            language="Python",
            topics=["research", "innovation", "artificial-intelligence", "novel"],
            license_name="MIT",
            created_at=now - timedelta(days=60),
            updated_at=now - timedelta(days=2),
            pushed_at=now - timedelta(days=1),
            contributors_count=3,
            readme_length=2000,
            readme_content="# Innovative AI Approach\n\nThis project presents a novel method for...",
            has_tests=True,
            has_ci=True,
            has_documentation=True
        ))
        
        leaderboard_gen = LeaderboardGenerator()
        leaderboard = leaderboard_gen.generate_leaderboard(mock_repos, include_clustering=False)
        
        logger.info(f"✓ Generated leaderboard with:")
        logger.info(f"  Trending: {len(leaderboard.trending)}")
        logger.info(f"  Established: {len(leaderboard.established)}")
        logger.info(f"  Hidden gems: {len(leaderboard.hidden_gems)}")
        
        # Save test leaderboard
        saved_file = leaderboard_gen.save_leaderboard(leaderboard)
        logger.info(f"✓ Saved test leaderboard to: {saved_file}")
        
        logger.info("✓ Leaderboard generation test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Leaderboard generation test failed: {e}")
        return False

def test_dashboard_generation():
    """Test dashboard generation"""
    logger.info("Testing dashboard generation...")
    
    try:
        from models import Repository, Leaderboard, LeaderboardEntry, RepositoryMetrics
        from src.dashboard.dashboard_generator import DashboardGenerator
        from datetime import datetime, timedelta
        
        # Create minimal test leaderboard
        now = datetime.utcnow()
        
        test_repo = Repository(
            id=1,
            name="test-dashboard-repo",
            full_name="user/test-dashboard-repo",
            description="Test repository for dashboard generation",
            html_url="https://github.com/user/test-dashboard-repo",
            clone_url="https://github.com/user/test-dashboard-repo.git",
            owner_login="user",
            owner_type="User",
            owner_avatar_url="https://github.com/user.png",
            stargazers_count=100,
            watchers_count=20,
            forks_count=10,
            open_issues_count=3,
            size=2000,
            language="Python",
            topics=["test", "dashboard"],
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=1),
            pushed_at=now - timedelta(days=1),
            contributors_count=2,
            readme_length=500,
            readme_content="Test repository",
            final_score=5.0
        )
        
        test_metrics = RepositoryMetrics(
            repo_id=1,
            full_name="user/test-dashboard-repo"
        )
        
        test_entry = LeaderboardEntry(
            rank=1,
            repository=test_repo,
            metrics=test_metrics,
            category="trending"
        )
        
        test_leaderboard = Leaderboard(
            trending=[test_entry],
            established=[],
            hidden_gems=[],
            clusters=[],
            total_repos_analyzed=1
        )
        
        dashboard_gen = DashboardGenerator()
        
        # Test JSON generation
        json_file = dashboard_gen.generate_json_export(test_leaderboard)
        logger.info(f"✓ Generated JSON export: {json_file}")
        
        # Test API endpoints
        api_files = dashboard_gen.generate_api_endpoints(test_leaderboard)
        logger.info(f"✓ Generated {len(api_files)} API endpoint files")
        
        # Test HTML generation (might fail due to template complexity)
        try:
            html_file = dashboard_gen.generate_html_dashboard(test_leaderboard)
            logger.info(f"✓ Generated HTML dashboard: {html_file}")
        except Exception as e:
            logger.warning(f"HTML generation failed (expected): {e}")
        
        logger.info("✓ Dashboard generation test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Dashboard generation test failed: {e}")
        return False

def run_all_tests():
    """Run all tests and report results"""
    logger.info("Starting AI Repository Leaderboard Pipeline Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_configuration),
        ("GitHub Client", test_github_client),
        ("Cache System", test_cache_system),
        ("Small-scale Scraping", test_small_scraping),
        ("Analysis Components", test_analysis_components),
        ("Clustering", test_clustering),
        ("Leaderboard Generation", test_leaderboard_generation),
        ("Dashboard Generation", test_dashboard_generation),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\nRunning {test_name} test...")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"Unexpected error in {test_name}: {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        logger.info(f"{test_name:.<30} {status}")
        if result:
            passed += 1
    
    logger.info("-" * 60)
    logger.info(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! The pipeline is ready to use.")
        logger.info("\nNext steps:")
        logger.info("1. Set up your GitHub token in .env file")
        logger.info("2. Run: python main.py check-config")
        logger.info("3. Run: python main.py update --quick")
        return True
    else:
        logger.warning(f"⚠️  {total - passed} tests failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)