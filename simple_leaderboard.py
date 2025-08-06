#!/usr/bin/env python3
"""
Simple leaderboard generator to bypass datetime issues
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_scraped_data(filename):
    """Load scraped repository data"""
    with open(filename, 'r') as f:
        return json.load(f)

def calculate_simple_score(repo):
    """Calculate a simple composite score for ranking"""
    stars = repo['stargazers_count']
    forks = repo['forks_count']
    contributors = repo['contributors_count']
    
    # Simple scoring formula
    score = (
        (stars * 0.6) +
        (forks * 0.3) + 
        (contributors * 0.1)
    )
    
    # Add recency bonus
    created_at = datetime.fromisoformat(repo['created_at'].replace('Z', '+00:00'))
    updated_at = datetime.fromisoformat(repo['updated_at'].replace('Z', '+00:00'))
    pushed_at = datetime.fromisoformat(repo['pushed_at'].replace('Z', '+00:00'))
    
    now = datetime.now(timezone.utc)
    days_since_push = (now - pushed_at).days
    
    # Recent activity bonus
    if days_since_push <= 7:
        score *= 1.2
    elif days_since_push <= 30:
        score *= 1.1
    elif days_since_push <= 90:
        score *= 1.05
    
    return score

def categorize_repos(repos):
    """Categorize repositories into trending, established, and hidden gems"""
    trending = []
    established = []
    hidden_gems = []
    
    now = datetime.now(timezone.utc)
    
    for repo in repos:
        stars = repo['stargazers_count']
        
        # Calculate days since push for activity check
        pushed_at = datetime.fromisoformat(repo['pushed_at'].replace('Z', '+00:00'))
        days_since_push = (now - pushed_at).days
        
        # Calculate age
        created_at = datetime.fromisoformat(repo['created_at'].replace('Z', '+00:00'))
        age_days = (now - created_at).days
        
        # Calculate simple score
        repo['simple_score'] = calculate_simple_score(repo)
        
        # Categorize
        if stars >= 5000 and age_days >= 180:
            established.append(repo)
        elif stars <= 1000 and repo['contributors_count'] >= 3 and days_since_push <= 90:
            hidden_gems.append(repo)  
        else:
            trending.append(repo)
    
    # Sort by score
    trending.sort(key=lambda x: x['simple_score'], reverse=True)
    established.sort(key=lambda x: x['simple_score'], reverse=True)
    hidden_gems.sort(key=lambda x: x['simple_score'], reverse=True)
    
    return trending[:50], established[:30], hidden_gems[:20]

def generate_leaderboard_json(trending, established, hidden_gems):
    """Generate JSON leaderboard output"""
    
    def create_entry(rank, repo, category):
        return {
            "rank": rank,
            "name": repo["name"],
            "full_name": repo["full_name"], 
            "description": repo.get("description", ""),
            "html_url": repo["html_url"],
            "stargazers_count": repo["stargazers_count"],
            "forks_count": repo["forks_count"],
            "language": repo.get("language"),
            "topics": repo.get("topics", []),
            "updated_at": repo["updated_at"],
            "simple_score": round(repo["simple_score"], 2),
            "category": category
        }
    
    leaderboard = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_repositories": len(trending) + len(established) + len(hidden_gems),
        "trending": [create_entry(i+1, repo, "trending") for i, repo in enumerate(trending)],
        "established": [create_entry(i+1, repo, "established") for i, repo in enumerate(established)],
        "hidden_gems": [create_entry(i+1, repo, "hidden_gem") for i, repo in enumerate(hidden_gems)]
    }
    
    return leaderboard

def main():
    logger.info("Starting simple leaderboard generation")
    
    # Load data
    repos = load_scraped_data('data/scraped_repos_20250805_211411.json')
    logger.info(f"Loaded {len(repos)} repositories")
    
    # Categorize
    trending, established, hidden_gems = categorize_repos(repos)
    logger.info(f"Categorized: {len(trending)} trending, {len(established)} established, {len(hidden_gems)} hidden gems")
    
    # Generate leaderboard
    leaderboard = generate_leaderboard_json(trending, established, hidden_gems)
    
    # Save results
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Save full leaderboard
    with open(output_dir / "simple_leaderboard.json", 'w') as f:
        json.dump(leaderboard, f, indent=2)
    
    # Save individual categories
    api_dir = output_dir / "api"
    api_dir.mkdir(exist_ok=True)
    
    with open(api_dir / "trending.json", 'w') as f:
        json.dump({"count": len(trending), "repositories": leaderboard["trending"]}, f, indent=2)
        
    with open(api_dir / "established.json", 'w') as f:
        json.dump({"count": len(established), "repositories": leaderboard["established"]}, f, indent=2)
        
    with open(api_dir / "hidden_gems.json", 'w') as f:
        json.dump({"count": len(hidden_gems), "repositories": leaderboard["hidden_gems"]}, f, indent=2)
    
    # Generate summary
    languages = {}
    all_repos = trending + established + hidden_gems
    for repo in all_repos:
        lang = repo.get('language', 'Unknown')
        languages[lang] = languages.get(lang, 0) + 1
    
    summary = {
        "generated_at": leaderboard["generated_at"],
        "total_repositories": len(all_repos),
        "categories": {
            "trending": len(trending),
            "established": len(established), 
            "hidden_gems": len(hidden_gems)
        },
        "top_languages": dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)[:10]),
        "top_trending": [{"name": r["name"], "stars": r["stargazers_count"]} for r in trending[:5]],
        "top_established": [{"name": r["name"], "stars": r["stargazers_count"]} for r in established[:5]],
        "top_hidden_gems": [{"name": r["name"], "stars": r["stargazers_count"]} for r in hidden_gems[:5]]
    }
    
    with open(api_dir / "summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info("✅ Generated leaderboard successfully!")
    logger.info(f"📊 Results saved to {output_dir}")
    logger.info(f"   • Full leaderboard: simple_leaderboard.json")  
    logger.info(f"   • API endpoints: api/trending.json, established.json, hidden_gems.json, summary.json")
    
    # Print summary
    print(f"\n🎉 AI Repository Leaderboard Generated!")
    print(f"📈 {len(trending)} Trending | 👑 {len(established)} Established | 💎 {len(hidden_gems)} Hidden Gems")
    print(f"🔝 Top Languages: {', '.join(list(languages.keys())[:5])}")
    
    if trending:
        print(f"\n🔥 Top 5 Trending:")
        for i, repo in enumerate(trending[:5], 1):
            print(f"   {i}. {repo['name']} - {repo['stargazers_count']:,} ⭐")
    
    if established:
        print(f"\n👑 Top 5 Established:")
        for i, repo in enumerate(established[:5], 1):
            print(f"   {i}. {repo['name']} - {repo['stargazers_count']:,} ⭐")
    
    if hidden_gems:
        print(f"\n💎 Top 5 Hidden Gems:")
        for i, repo in enumerate(hidden_gems[:5], 1):
            print(f"   {i}. {repo['name']} - {repo['stargazers_count']:,} ⭐")

if __name__ == "__main__":
    main()