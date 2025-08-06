# 🧠 AI Repository Leaderboard

> **Interactive dashboard showcasing trending AI, Machine Learning, RAG, and Agent projects on GitHub**

[![GitHub Pages](https://img.shields.io/badge/GitHub_Pages-Live_Demo-blue?style=for-the-badge&logo=github)](https://dark-matter98.github.io/ai-repository-leaderboard/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

## 🌟 **Live Demo**

**👉 [View Live Dashboard](https://dark-matter98.github.io/ai-repository-leaderboard/) 👈**

A comprehensive system for discovering, analyzing, and ranking trending open-source AI repositories on GitHub. This project automatically scrapes GitHub for AI/ML repositories, calculates various metrics, performs semantic clustering, identifies hidden gems, and generates interactive leaderboards.

## Features

- **🔍 Intelligent Scraping**: Advanced GitHub API integration with rate limiting and caching
- **📊 Multi-dimensional Scoring**: Combines stars, activity, code quality, and community metrics
- **🧠 Semantic Clustering**: Groups similar repositories using README embeddings
- **💎 Hidden Gems Detection**: Identifies high-quality, underrated repositories
- **📈 Interactive Dashboard**: Beautiful HTML dashboard with charts and analytics
- **🚀 Automated Updates**: Daily scheduled updates with configurable timing
- **⚡ Performance Optimized**: Redis/file-based caching and parallel processing
- **🔌 API Endpoints**: JSON exports for integration with other tools

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd ai-repository-leaderboard

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env
```

### 2. Configuration

Edit `.env` file with your settings:

```bash
GITHUB_TOKEN=your_github_personal_access_token_here
REDIS_URL=redis://localhost:6379  # Optional: for better performance
DAILY_UPDATE_TIME=06:00
```

**Note**: You'll need a GitHub Personal Access Token for API access. Create one at [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens).

### 3. Test the Setup

```bash
# Run comprehensive pipeline tests
python test_pipeline.py

# Check configuration
python main.py check-config
```

### 4. Generate Your First Leaderboard

```bash
# Quick update with limited data (for testing)
python main.py update --quick

# Full update with comprehensive data
python main.py update
```

### 5. View Results

After running an update, check the `output/` directory:
- `leaderboard_latest.html` - Interactive dashboard
- `leaderboard_latest.json` - Complete data export
- `api/` - Individual API endpoints

## CLI Commands

### Core Commands

```bash
# Scrape repositories (without generating leaderboard)
python main.py scrape --max-repos 100 --save-data

# Generate leaderboard from existing data
python main.py generate --input-file data/scraped_repos_20240101_120000.json

# Run complete update cycle
python main.py update [--quick]

# Start automated daily updates
python main.py schedule [--daemon]

# Check system status
python main.py status

# Clear cache
python main.py clear-cache [--all|--expired]
```

### Examples

```bash
# Test run with minimal data
python main.py update --quick

# Full production run
python main.py update

# Start scheduler in background
python main.py schedule --daemon

# Generate leaderboard without clustering (faster)
python main.py generate --input-file data/repos.json --no-include-clustering
```

## Architecture

### Components

1. **Scraper Module** (`src/scraper/`)
   - `GitHubClient`: API wrapper with rate limiting
   - `RepositoryScraper`: Multi-query repository discovery

2. **Analysis Module** (`src/analysis/`)
   - `MetricsCalculator`: Scoring algorithms
   - `ClusteringEngine`: Semantic similarity clustering
   - `HiddenGemsDetector`: Quality-based discovery
   - `LeaderboardGenerator`: Ranking and categorization

3. **Dashboard Module** (`src/dashboard/`)
   - `DashboardGenerator`: HTML/JSON output generation

4. **Infrastructure**
   - `CacheManager`: Redis/file-based caching
   - `Scheduler`: Automated daily updates
   - `Models`: Pydantic data models

### Data Flow

```
GitHub API → Scraper → Cache → Analysis → Leaderboard → Dashboard
     ↓                           ↓            ↓
Rate Limiting              Clustering    Scoring
Authentication             Embeddings    Ranking
```

## Leaderboard Categories

### 🔥 Trending
- **Criteria**: 100-10K stars, active in last 90 days, at least 30 days old
- **Scoring**: Weighted combination of momentum and quality (70% momentum, 30% quality)
- **Focus**: Recent activity and growing popularity

### 👑 Established  
- **Criteria**: 5K+ stars, at least 6 months old
- **Scoring**: Quality-focused with star count normalization (30% momentum, 70% quality)
- **Focus**: Mature, reliable projects

### 💎 Hidden Gems
- **Criteria**: <1K stars, high quality score (>0.7), active maintenance
- **Scoring**: Multi-factor quality assessment
- **Focus**: Underrated projects with potential

## Scoring Methodology

### Momentum Score (0-10)
- Star velocity (stars per day since creation)
- Recent activity (days since last push)
- Age factor (slight boost for newer projects)
- Engagement ratio (stars vs forks vs watchers)
- Repository size factor

### Quality Score (0-1)
- **Documentation**: README length, additional docs, description quality
- **Code Quality**: Tests, CI/CD, license, topic coverage
- **Community**: Contributor count and diversity
- **Maintenance**: Update frequency and consistency

### Hidden Gem Score (0-1)
- Code quality indicators (tests, CI, documentation)
- Community engagement relative to popularity
- Innovation potential (cutting-edge topics, research orientation)
- Maintenance quality and consistency

## Clustering

Uses sentence-transformers to create embeddings from:
- Repository  and description
- README content (preprocessed)
- Topics and language information

Clustering algorithm:
- K-means with optimal cluster count selection
- Silhouette score optimization
- Automatic cluster naming based on common topics

## API Endpoints

The system generates several JSON endpoints in the `output/api/` directory:

- `trending.json` - Top trending repositories
- `established.json` - Top established repositories  
- `hidden_gems.json` - Top hidden gems
- `clusters.json` - Repository clusters
- `summary.json` - Overall statistics

Example API response:
```json
{
  "category": "trending",
  "count": 50,
  "generated_at": "2024-01-01T12:00:00",
  "repositories": [
    {
      "rank": 1,
      "name": "awesome-ai-project",
      "full_name": "user/awesome-ai-project",
      "description": "An awesome AI project",
      "stargazers_count": 2500,
      "final_score": 8.5,
      "change_from_previous": 2
    }
  ]
}
```

## Configuration

### Settings (config.py)

Key configuration options:

```python
# Search parameters
min_stars = 50
max_results_per_query = 100
ai_topics = ["machine-learning", "artificial-intelligence", ...]

# Scoring weights
star_weight = 0.3
recent_activity_weight = 0.25
contributor_diversity_weight = 0.2
code_quality_weight = 0.15
documentation_weight = 0.1

# Hidden gems criteria
hidden_gem_max_stars = 1000
hidden_gem_min_quality_score = 0.7

# Cache settings
cache_ttl = 3600  # 1 hour
daily_update_time = "06:00"  # UTC
```

### Environment Variables

- `GITHUB_TOKEN`: GitHub Personal Access Token (required)
- `REDIS_URL`: Redis connection URL (optional, defaults to file cache)
- `DAILY_UPDATE_TIME`: UTC time for daily updates (default: 06:00)

## Performance Optimization

### Caching Strategy
- **Repository Details**: 2 hours TTL
- **Metrics**: 1 hour TTL
- **Search Results**: 30 minutes TTL
- **Embeddings**: 24 hours TTL

### Rate Limiting
- Automatic GitHub API rate limit handling
- Exponential backoff on rate limit hits
- Conservative request pacing
- Authenticated requests (5000/hour vs 60/hour)

### Parallel Processing
- Concurrent repository detail fetching
- Batch embedding generation
- Parallel search query execution

## Monitoring

### Logging
- Comprehensive logging to `leaderboard.log`
- Structured logging with timestamps
- Rate limit monitoring
- Error tracking and debugging

### Status Monitoring
```bash
# Check system status
python main.py status

# View recent job history
python main.py status | grep "Recent Jobs"

# Monitor cache performance
python main.py status | grep "Cache"
```

## Troubleshooting

### Common Issues

1. **Rate Limit Errors**
   ```bash
   # Check current rate limits
   python main.py status
   
   # Use authenticated requests
   export GITHUB_TOKEN=your_token_here
   ```

2. **Cache Issues**
   ```bash
   # Clear all cache
   python main.py clear-cache --all
   
   # Test cache connectivity
   python test_pipeline.py
   ```

3. **Import Errors**
   ```bash
   # Install missing dependencies
   pip install -r requirements.txt
   
   # Check for sentence-transformers
   pip install sentence-transformers
   ```

4. **No Repositories Found**
   - Check GitHub token validity
   - Verify network connectivity
   - Check rate limit status
   - Try with `--quick` flag first

### Debug Mode
```bash
# Enable verbose logging
python main.py --verbose <command>

# Run pipeline tests
python test_pipeline.py

# Check configuration
python main.py check-config
```

## Development

### Project Structure
```
├── config.py              # Configuration settings
├── models.py              # Pydantic data models
├── main.py                # CLI interface
├── test_pipeline.py       # Comprehensive tests
├── requirements.txt       # Python dependencies
├── src/
│   ├── scraper/           # GitHub API integration
│   ├── analysis/          # Scoring and clustering
│   ├── dashboard/         # Output generation
│   ├── cache_manager.py   # Caching system
│   └── scheduler.py       # Automated updates
├── data/                  # Cached data and results
├── output/                # Generated dashboards and APIs
└── templates/             # HTML templates
```

### Adding New Features

1. **New Scoring Metrics**: Extend `MetricsCalculator`
2. **Custom Filters**: Modify search queries in `RepositoryScraper`
3. **Output Formats**: Add generators in `DashboardGenerator`
4. **New Categories**: Update `LeaderboardGenerator`

### Testing
```bash
# Run full test suite
python test_pipeline.py

# Test specific components
python -c "from test_pipeline import test_clustering; test_clustering()"

# Integration testing
python main.py update --quick
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- GitHub API for repository data
- sentence-transformers for semantic embeddings
- Plotly for interactive visualizations
- Click for CLI interface
- Pydantic for data validation
