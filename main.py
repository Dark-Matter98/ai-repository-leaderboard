#!/usr/bin/env python3
"""
AI Repository Leaderboard - Main CLI Interface

This script provides a command-line interface for running the AI repository leaderboard
system, including scraping GitHub repositories, generating leaderboards, and starting
the scheduler for daily updates.
"""

import logging
import click
import sys
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('leaderboard.log')
    ]
)

logger = logging.getLogger(__name__)

# Import our modules
from config import settings
from src.scraper.repository_scraper import RepositoryScraper
from src.scraper.github_client import GitHubClient
from src.analysis.leaderboard_generator import LeaderboardGenerator
from src.dashboard.dashboard_generator import DashboardGenerator
from src.scheduler import scheduler
from src.cache_manager import cache_manager, repo_cache

@click.group()
@click.option('--verbose', is_flag=True, help='Enable verbose logging')
def cli(verbose):
    """AI Repository Leaderboard - Discover trending AI/ML projects on GitHub"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("AI Repository Leaderboard CLI started")

@cli.command()
@click.option('--max-repos', default=100, help='Maximum repositories to scrape per query')
@click.option('--save-data', is_flag=True, help='Save scraped data to file')
def scrape(max_repos, save_data):
    """Scrape GitHub repositories"""
    logger.info(f"Starting repository scraping (max {max_repos} repos per query)")
    
    try:
        github_client = GitHubClient()
        scraper = RepositoryScraper(github_client)
        
        # Check rate limits first
        rate_limit = github_client.get_rate_limit_status()
        logger.info(f"Rate limit status: {rate_limit}")
        
        repositories = scraper.scrape_all_repositories(max_results_per_query=max_repos)
        
        logger.info(f"Successfully scraped {len(repositories)} repositories")
        
        if save_data:
            saved_file = scraper.save_repositories(repositories)
            logger.info(f"Saved data to: {saved_file}")
        
        # Print summary
        languages = {}
        for repo in repositories:
            if repo.language:
                languages[repo.language] = languages.get(repo.language, 0) + 1
        
        click.echo(f"\nScraping Summary:")
        click.echo(f"Total repositories: {len(repositories)}")
        click.echo(f"Top languages: {dict(list(sorted(languages.items(), key=lambda x: x[1], reverse=True))[:5])}")
        
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--input-file', help='Load repositories from JSON file instead of scraping')
@click.option('--max-repos', default=200, help='Maximum repositories to process')
@click.option('--include-clustering', is_flag=True, default=True, help='Include semantic clustering')
@click.option('--generate-html', is_flag=True, default=True, help='Generate HTML dashboard')
@click.option('--generate-json', is_flag=True, default=True, help='Generate JSON exports')
def generate(input_file, max_repos, include_clustering, generate_html, generate_json):
    """Generate leaderboard from scraped data"""
    logger.info("Starting leaderboard generation")
    
    try:
        repositories = []
        
        if input_file:
            # Load from file
            scraper = RepositoryScraper()
            repositories = scraper.load_repositories(input_file)
            logger.info(f"Loaded {len(repositories)} repositories from {input_file}")
        else:
            # Scrape fresh data
            github_client = GitHubClient()
            scraper = RepositoryScraper(github_client)
            repositories = scraper.scrape_all_repositories(max_results_per_query=max_repos)
            logger.info(f"Scraped {len(repositories)} repositories")
        
        if not repositories:
            click.echo("No repositories found. Please scrape data first.", err=True)
            sys.exit(1)
        
        # Generate leaderboard
        leaderboard_generator = LeaderboardGenerator()
        leaderboard = leaderboard_generator.generate_leaderboard(
            repositories, 
            include_clustering=include_clustering
        )
        
        # Save leaderboard data
        leaderboard_file = leaderboard_generator.save_leaderboard(leaderboard)
        logger.info(f"Saved leaderboard to: {leaderboard_file}")
        
        # Generate outputs
        dashboard_generator = DashboardGenerator()
        outputs = {}
        
        if generate_html:
            outputs['html'] = dashboard_generator.generate_html_dashboard(leaderboard)
        
        if generate_json:
            outputs['json'] = dashboard_generator.generate_json_export(leaderboard)
            outputs.update(dashboard_generator.generate_api_endpoints(leaderboard))
        
        # Print summary
        click.echo(f"\nLeaderboard Generation Summary:")
        click.echo(f"Total repositories analyzed: {leaderboard.total_repos_analyzed}")
        click.echo(f"Trending projects: {len(leaderboard.trending)}")
        click.echo(f"Established projects: {len(leaderboard.established)}")
        click.echo(f"Hidden gems: {len(leaderboard.hidden_gems)}")
        click.echo(f"Clusters: {len(leaderboard.clusters)}")
        
        click.echo(f"\nGenerated outputs:")
        for output_type, file_path in outputs.items():
            click.echo(f"  {output_type}: {file_path}")
        
    except Exception as e:
        logger.error(f"Leaderboard generation failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--quick', is_flag=True, help='Run quick update with limited repositories')
def update(quick):
    """Run a full update cycle (scrape + generate + output)"""
    logger.info("Starting full update cycle")
    
    try:
        if quick:
            leaderboard = scheduler.run_quick_update(max_repos=50)
            click.echo("Quick update completed")
        else:
            leaderboard = scheduler.run_daily_update()
            click.echo("Full update completed")
        
        # Generate dashboard
        dashboard_generator = DashboardGenerator()
        outputs = dashboard_generator.generate_all_outputs(leaderboard)
        
        click.echo(f"\nUpdate Summary:")
        click.echo(f"Trending: {len(leaderboard.trending)}")
        click.echo(f"Established: {len(leaderboard.established)}")
        click.echo(f"Hidden gems: {len(leaderboard.hidden_gems)}")
        
        click.echo(f"\nGenerated files:")
        for output_type, file_path in outputs.items():
            click.echo(f"  {output_type}: {file_path}")
            
    except Exception as e:
        logger.error(f"Update failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--daemon', is_flag=True, help='Run scheduler as daemon')
def schedule(daemon):
    """Start the daily update scheduler"""
    logger.info("Starting scheduler")
    
    try:
        scheduler.start_scheduler()
        
        next_run = scheduler.get_next_scheduled_run()
        click.echo(f"Scheduler started. Next run: {next_run}")
        click.echo(f"Daily updates scheduled at {settings.daily_update_time} UTC")
        
        if daemon:
            click.echo("Running as daemon. Press Ctrl+C to stop.")
            try:
                while True:
                    import time
                    time.sleep(60)
                    
                    # Show status every hour
                    if datetime.now().minute == 0:
                        status = scheduler.get_job_status()
                        if status['status'] != 'idle':
                            click.echo(f"Current job: {status}")
                        
                        cache_stats = cache_manager.get_cache_stats()
                        click.echo(f"Cache: {cache_stats['total_keys']} keys, {cache_stats['total_size_mb']:.1f}MB")
                        
            except KeyboardInterrupt:
                click.echo("\nStopping scheduler...")
                scheduler.stop_scheduler()
        
    except Exception as e:
        logger.error(f"Scheduler failed: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

@cli.command()
def status():
    """Show current system status"""
    try:
        # Job status
        job_status = scheduler.get_job_status()
        click.echo(f"Job Status: {job_status['status']}")
        
        if job_status['status'] != 'idle':
            click.echo(f"  Current job: {job_status}")
        
        # Cache status
        cache_stats = cache_manager.get_cache_stats()
        click.echo(f"\nCache Status:")
        click.echo(f"  Backend: {cache_stats['backend']}")
        click.echo(f"  Total keys: {cache_stats['total_keys']}")
        click.echo(f"  Size: {cache_stats['total_size_mb']:.2f} MB")
        
        # Recent jobs
        recent_jobs = scheduler.get_jobs_history(limit=5)
        if recent_jobs:
            click.echo(f"\nRecent Jobs:")
            for job in recent_jobs[-5:]:
                status_icon = "✓" if job['status'] == 'completed' else "✗" if job['status'] == 'failed' else "⏳"
                click.echo(f"  {status_icon} {job['id']} - {job['status']} ({job.get('repos_processed', 0)} repos)")
        
        # Next scheduled run
        next_run = scheduler.get_next_scheduled_run()
        if next_run:
            click.echo(f"\nNext scheduled run: {next_run}")
        
        # GitHub rate limits
        github_client = GitHubClient()
        rate_limit = github_client.get_rate_limit_status()
        core_remaining = rate_limit.get('resources', {}).get('core', {}).get('remaining', 'unknown')
        search_remaining = rate_limit.get('resources', {}).get('search', {}).get('remaining', 'unknown')
        
        click.echo(f"\nGitHub Rate Limits:")
        click.echo(f"  Core API: {core_remaining}")
        click.echo(f"  Search API: {search_remaining}")
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        click.echo(f"Error: {e}", err=True)

@cli.command()
@click.option('--all', is_flag=True, help='Clear all cache data')
@click.option('--expired', is_flag=True, help='Clear only expired entries')
def clear_cache(all, expired):
    """Clear cache data"""
    try:
        if all:
            cache_manager.clear_all()
            click.echo("Cleared all cache data")
        elif expired:
            repo_cache.cleanup_expired_entries()
            click.echo("Cleared expired cache entries")
        else:
            click.echo("Please specify --all or --expired")
        
        # Show updated stats
        cache_stats = cache_manager.get_cache_stats()
        click.echo(f"Cache now has {cache_stats['total_keys']} keys, {cache_stats['total_size_mb']:.2f} MB")
        
    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        click.echo(f"Error: {e}", err=True)

@cli.command()
def check_config():
    """Check configuration and requirements"""
    click.echo("Configuration Check:")
    click.echo(f"  GitHub Token: {'✓ Set' if settings.github_token else '✗ Missing'}")
    click.echo(f"  Redis URL: {settings.redis_url}")
    click.echo(f"  Daily Update Time: {settings.daily_update_time}")
    click.echo(f"  Min Stars: {settings.min_stars}")
    click.echo(f"  AI Topics: {len(settings.ai_topics)} configured")
    
    # Test GitHub connection
    try:
        github_client = GitHubClient()
        rate_limit = github_client.get_rate_limit_status()
        click.echo(f"  GitHub API: ✓ Connected")
    except Exception as e:
        click.echo(f"  GitHub API: ✗ Failed ({e})")
    
    # Test cache connection
    try:
        cache_manager.set("test", "value", 10)
        test_value = cache_manager.get("test")
        cache_manager.delete("test")
        
        if test_value == "value":
            click.echo(f"  Cache: ✓ Working ({cache_manager.use_redis and 'Redis' or 'File'})")
        else:
            click.echo(f"  Cache: ✗ Not working properly")
    except Exception as e:
        click.echo(f"  Cache: ✗ Failed ({e})")
    
    # Check required directories
    directories = [Path("data"), Path("output"), Path("templates")]
    for directory in directories:
        if directory.exists():
            click.echo(f"  Directory {directory}: ✓ Exists")
        else:
            click.echo(f"  Directory {directory}: ✗ Missing")

if __name__ == '__main__':
    cli()