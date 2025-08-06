import logging
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any, List
import json
from pathlib import Path

from config import settings
from src.scraper.repository_scraper import RepositoryScraper
from src.scraper.github_client import GitHubClient
from src.analysis.leaderboard_generator import LeaderboardGenerator
from src.cache_manager import cache_manager, repo_cache
from models import ScrapingJob

logger = logging.getLogger(__name__)

class LeaderboardScheduler:
    def __init__(self):
        self.github_client = GitHubClient()
        self.scraper = RepositoryScraper(self.github_client)
        self.leaderboard_generator = LeaderboardGenerator()
        self.is_running = False
        self.current_job: Optional[ScrapingJob] = None
        self.scheduler_thread: Optional[threading.Thread] = None
        self.jobs_history: list = []
        self.max_history = 50
        
        # Job state persistence
        self.state_file = Path("data/scheduler_state.json")
        self.load_state()
    
    def load_state(self):
        """Load scheduler state from disk"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                self.jobs_history = state.get('jobs_history', [])
                logger.info(f"Loaded scheduler state with {len(self.jobs_history)} historical jobs")
        except Exception as e:
            logger.warning(f"Could not load scheduler state: {e}")
            self.jobs_history = []
    
    def save_state(self):
        """Save scheduler state to disk"""
        try:
            state = {
                'jobs_history': self.jobs_history[-self.max_history:],  # Keep only recent history
                'last_saved': datetime.utcnow().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Could not save scheduler state: {e}")
    
    def create_scraping_job(self) -> ScrapingJob:
        """Create a new scraping job"""
        job_id = f"job_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        job = ScrapingJob(
            id=job_id,
            status="pending",
            started_at=None,
            completed_at=None,
            repos_found=0,
            repos_processed=0,
            error_message=None
        )
        
        return job
    
    def update_job_status(self, job: ScrapingJob, status: str, **kwargs):
        """Update job status and additional fields"""
        job.status = status
        
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)
        
        if status == "running" and job.started_at is None:
            job.started_at = datetime.utcnow()
        elif status in ["completed", "failed"]:
            job.completed_at = datetime.utcnow()
    
    def run_daily_update(self):
        """Execute the daily leaderboard update"""
        logger.info("Starting daily leaderboard update")
        
        job = self.create_scraping_job()
        self.current_job = job
        
        try:
            self.update_job_status(job, "running")
            
            # Step 1: Scrape repositories
            logger.info("Step 1: Scraping repositories from GitHub")
            repositories = self.scraper.scrape_all_repositories(max_results_per_query=200)
            
            if not repositories:
                raise Exception("No repositories were scraped")
            
            self.update_job_status(job, "running", repos_found=len(repositories))
            logger.info(f"Scraped {len(repositories)} repositories")
            
            # Step 2: Save scraped data
            logger.info("Step 2: Saving scraped repository data")
            scraped_file = self.scraper.save_repositories(repositories)
            
            # Step 3: Generate leaderboard
            logger.info("Step 3: Generating leaderboard")
            leaderboard = self.leaderboard_generator.generate_leaderboard(
                repositories, 
                include_clustering=True
            )
            
            # Step 4: Save leaderboard
            logger.info("Step 4: Saving leaderboard")
            leaderboard_file = self.leaderboard_generator.save_leaderboard(leaderboard)
            
            # Step 5: Generate summary statistics
            logger.info("Step 5: Generating summary statistics")
            stats = self.leaderboard_generator.generate_summary_stats(leaderboard)
            
            # Save stats
            stats_file = Path("data") / f"stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(stats_file, 'w') as f:
                json.dump(stats, f, indent=2)
            
            # Step 6: Clean up old cache entries
            logger.info("Step 6: Cleaning up cache")
            repo_cache.cleanup_expired_entries()
            
            # Mark job as completed
            self.update_job_status(
                job, 
                "completed",
                repos_processed=len(repositories),
                completed_at=datetime.utcnow()
            )
            
            # Add to history
            self.jobs_history.append(job.model_dump())
            self.save_state()
            
            logger.info(f"Daily update completed successfully. Job ID: {job.id}")
            logger.info(f"Generated leaderboard: {len(leaderboard.trending)} trending, "
                       f"{len(leaderboard.established)} established, {len(leaderboard.hidden_gems)} hidden gems")
            
            return leaderboard
            
        except Exception as e:
            error_msg = f"Daily update failed: {str(e)}"
            logger.error(error_msg)
            
            self.update_job_status(
                job, 
                "failed", 
                error_message=error_msg,
                completed_at=datetime.utcnow()
            )
            
            # Add to history even if failed
            self.jobs_history.append(job.model_dump())
            self.save_state()
            
            raise
        
        finally:
            self.current_job = None
    
    def run_quick_update(self, max_repos: int = 50):
        """Run a quick update with limited repositories for testing"""
        logger.info(f"Starting quick update (max {max_repos} repos)")
        
        job = self.create_scraping_job()
        self.current_job = job
        
        try:
            self.update_job_status(job, "running")
            
            # Scrape limited repositories
            repositories = self.scraper.scrape_all_repositories(max_results_per_query=max_repos)
            
            if not repositories:
                raise Exception("No repositories were scraped")
            
            self.update_job_status(job, "running", repos_found=len(repositories))
            
            # Generate leaderboard (without clustering for speed)
            leaderboard = self.leaderboard_generator.generate_leaderboard(
                repositories, 
                include_clustering=False
            )
            
            # Save results
            leaderboard_file = self.leaderboard_generator.save_leaderboard(leaderboard)
            
            # Mark as completed
            self.update_job_status(
                job, 
                "completed",
                repos_processed=len(repositories)
            )
            
            self.jobs_history.append(job.model_dump())
            self.save_state()
            
            logger.info(f"Quick update completed. Job ID: {job.id}")
            return leaderboard
            
        except Exception as e:
            error_msg = f"Quick update failed: {str(e)}"
            logger.error(error_msg)
            
            self.update_job_status(job, "failed", error_message=error_msg)
            self.jobs_history.append(job.model_dump())
            self.save_state()
            
            raise
        
        finally:
            self.current_job = None
    
    def schedule_daily_updates(self):
        """Schedule daily updates"""
        update_time = settings.daily_update_time
        
        schedule.clear()  # Clear any existing schedules
        
        # Schedule daily update
        schedule.every().day.at(update_time).do(self._safe_run_daily_update)
        
        # Schedule cache cleanup every 6 hours
        schedule.every(6).hours.do(self._cleanup_cache)
        
        # Schedule rate limit monitoring every hour
        schedule.every().hour.do(self._check_rate_limits)
        
        logger.info(f"Scheduled daily updates at {update_time} UTC")
        logger.info("Additional schedules: cache cleanup every 6 hours, rate limit check every hour")
    
    def _safe_run_daily_update(self):
        """Wrapper for daily update with error handling"""
        try:
            self.run_daily_update()
        except Exception as e:
            logger.error(f"Scheduled daily update failed: {e}")
    
    def _cleanup_cache(self):
        """Scheduled cache cleanup"""
        try:
            logger.info("Running scheduled cache cleanup")
            repo_cache.cleanup_expired_entries()
            
            # Get cache stats
            stats = cache_manager.get_cache_stats()
            logger.info(f"Cache stats: {stats['total_keys']} keys, {stats['total_size_mb']:.2f} MB")
            
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
    
    def _check_rate_limits(self):
        """Check GitHub API rate limits"""
        try:
            rate_limit_info = self.github_client.get_rate_limit_status()
            
            core_remaining = rate_limit_info.get('resources', {}).get('core', {}).get('remaining', 0)
            search_remaining = rate_limit_info.get('resources', {}).get('search', {}).get('remaining', 0)
            
            logger.info(f"GitHub rate limits - Core: {core_remaining}, Search: {search_remaining}")
            
            # Log warning if rate limits are low
            if core_remaining < 1000:
                logger.warning(f"Core API rate limit is low: {core_remaining}")
            if search_remaining < 10:
                logger.warning(f"Search API rate limit is low: {search_remaining}")
                
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
    
    def start_scheduler(self):
        """Start the scheduler in a separate thread"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self.schedule_daily_updates()
        
        def run_scheduler():
            logger.info("Scheduler started")
            
            while self.is_running:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    logger.error(f"Scheduler error: {e}")
                    time.sleep(60)
            
            logger.info("Scheduler stopped")
        
        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        if self.is_running:
            self.is_running = False
            if self.scheduler_thread:
                self.scheduler_thread.join(timeout=10)
            logger.info("Scheduler stopped")
    
    def get_job_status(self) -> Dict[str, Any]:
        """Get current job status"""
        if self.current_job:
            job_dict = self.current_job.model_dump()
            # Convert datetime objects to strings
            for field in ['started_at', 'completed_at']:
                if job_dict.get(field):
                    job_dict[field] = job_dict[field].isoformat()
            return job_dict
        
        return {"status": "idle", "message": "No job currently running"}
    
    def get_jobs_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent jobs history"""
        return self.jobs_history[-limit:]
    
    def get_next_scheduled_run(self) -> Optional[str]:
        """Get the next scheduled run time"""
        next_run = schedule.next_run()
        if next_run:
            return next_run.isoformat()
        return None
    
    def force_update_now(self, quick: bool = False):
        """Force an immediate update"""
        if self.current_job and self.current_job.status == "running":
            raise Exception("A job is already running")
        
        if quick:
            return self.run_quick_update()
        else:
            return self.run_daily_update()

# Global scheduler instance
scheduler = LeaderboardScheduler()