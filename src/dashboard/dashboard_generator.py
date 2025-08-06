import logging
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder

from models import Leaderboard, LeaderboardEntry, Repository, Cluster

logger = logging.getLogger(__name__)

class DashboardGenerator:
    def __init__(self):
        self.output_dir = Path("output")
        self.templates_dir = Path("templates")
        self.static_dir = Path("static")
        
        # Create directories
        for dir_path in [self.output_dir, self.templates_dir, self.static_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=True
        )
        
        # Create templates if they don't exist
        self._create_templates()
    
    def _create_templates(self):
        """Create HTML templates if they don't exist"""
        
        # Main leaderboard template
        main_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Repository Leaderboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        .repo-card { transition: transform 0.2s; }
        .repo-card:hover { transform: translateY(-2px); }
        .category-section { margin-bottom: 3rem; }
        .stats-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .cluster-tag { font-size: 0.8em; }
        .position-change.up { color: #28a745; }
        .position-change.down { color: #dc3545; }
        .position-change.new { color: #6c757d; }
        .hidden-gem-badge { background: linear-gradient(45deg, #FFD700, #FFA500); }
    </style>
</head>
<body class="bg-light">
    <nav class="navbar navbar-dark bg-primary mb-4">
        <div class="container">
            <span class="navbar-brand mb-0 h1">
                <i class="fas fa-star"></i> AI Repository Leaderboard
            </span>
            <span class="navbar-text">
                Updated: {{ leaderboard.generated_at.strftime('%Y-%m-%d %H:%M UTC') }}
            </span>
        </div>
    </nav>

    <div class="container">
        <!-- Statistics Overview -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card stats-card text-white">
                    <div class="card-body text-center">
                        <h3>{{ leaderboard.total_repos_analyzed }}</h3>
                        <p class="mb-0">Total Repositories</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-success text-white">
                    <div class="card-body text-center">
                        <h3>{{ leaderboard.trending|length }}</h3>
                        <p class="mb-0">Trending Projects</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-info text-white">
                    <div class="card-body text-center">
                        <h3>{{ leaderboard.established|length }}</h3>
                        <p class="mb-0">Established Projects</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-warning text-white">
                    <div class="card-body text-center">
                        <h3>{{ leaderboard.hidden_gems|length }}</h3>
                        <p class="mb-0">Hidden Gems</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <ul class="nav nav-tabs mb-4" id="leaderboardTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="trending-tab" data-bs-toggle="tab" data-bs-target="#trending" type="button">
                    <i class="fas fa-fire"></i> Trending
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="established-tab" data-bs-toggle="tab" data-bs-target="#established" type="button">
                    <i class="fas fa-crown"></i> Established
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="hidden-gems-tab" data-bs-toggle="tab" data-bs-target="#hidden-gems" type="button">
                    <i class="fas fa-gem"></i> Hidden Gems
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="clusters-tab" data-bs-toggle="tab" data-bs-target="#clusters" type="button">
                    <i class="fas fa-project-diagram"></i> Clusters
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="analytics-tab" data-bs-toggle="tab" data-bs-target="#analytics" type="button">
                    <i class="fas fa-chart-bar"></i> Analytics
                </button>
            </li>
        </ul>

        <!-- Tab Content -->
        <div class="tab-content" id="leaderboardTabsContent">
            <!-- Trending Tab -->
            <div class="tab-pane fade show active" id="trending" role="tabpanel">
                {{ render_repository_list(leaderboard.trending, "trending") }}
            </div>

            <!-- Established Tab -->
            <div class="tab-pane fade" id="established" role="tabpanel">
                {{ render_repository_list(leaderboard.established, "established") }}
            </div>

            <!-- Hidden Gems Tab -->
            <div class="tab-pane fade" id="hidden-gems" role="tabpanel">
                {{ render_repository_list(leaderboard.hidden_gems, "hidden-gems") }}
            </div>

            <!-- Clusters Tab -->
            <div class="tab-pane fade" id="clusters" role="tabpanel">
                <div class="row">
                    {% for cluster in leaderboard.clusters %}
                    <div class="col-md-6 mb-4">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0">{{ cluster.name }}</h5>
                                <small class="text-muted">{{ cluster.size }} repositories</small>
                            </div>
                            <div class="card-body">
                                <p class="card-text">{{ cluster.description }}</p>
                                <div class="mt-2">
                                    {% for repo_id in cluster.repos[:5] %}
                                        {% set repo = get_repo_by_id(repo_id) %}
                                        {% if repo %}
                                        <span class="badge bg-secondary me-1 mb-1">{{ repo.name }}</span>
                                        {% endif %}
                                    {% endfor %}
                                    {% if cluster.repos|length > 5 %}
                                    <span class="text-muted">... and {{ cluster.repos|length - 5 }} more</span>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <!-- Analytics Tab -->
            <div class="tab-pane fade" id="analytics" role="tabpanel">
                <div class="row">
                    <div class="col-md-6 mb-4">
                        <div class="card">
                            <div class="card-header">
                                <h5>Language Distribution</h5>
                            </div>
                            <div class="card-body">
                                <div id="languageChart"></div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6 mb-4">
                        <div class="card">
                            <div class="card-header">
                                <h5>Stars Distribution</h5>
                            </div>
                            <div class="card-body">
                                <div id="starsChart"></div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-12 mb-4">
                        <div class="card">
                            <div class="card-header">
                                <h5>Top Topics</h5>
                            </div>
                            <div class="card-body">
                                <div id="topicsChart"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Render charts
        {{ charts_js | safe }}
    </script>
</body>
</html>

{% macro render_repository_list(entries, category) %}
<div class="row">
    {% for entry in entries %}
    <div class="col-md-6 mb-4">
        <div class="card repo-card h-100">
            <div class="card-header d-flex justify-content-between align-items-center">
                <div>
                    <span class="badge bg-primary me-2">#{{ entry.rank }}</span>
                    {% if entry.change_from_previous is not none %}
                        {% if entry.change_from_previous > 0 %}
                        <span class="position-change up"><i class="fas fa-arrow-up"></i> +{{ entry.change_from_previous }}</span>
                        {% elif entry.change_from_previous < 0 %}
                        <span class="position-change down"><i class="fas fa-arrow-down"></i> {{ entry.change_from_previous }}</span>
                        {% endif %}
                    {% else %}
                    <span class="position-change new"><i class="fas fa-plus"></i> NEW</span>
                    {% endif %}
                </div>
                <div>
                    {% if category == "hidden-gems" %}
                    <span class="badge hidden-gem-badge">Hidden Gem</span>
                    {% endif %}
                    <span class="badge bg-secondary">{{ entry.repository.language or 'Unknown' }}</span>
                </div>
            </div>
            <div class="card-body">
                <h6 class="card-title">
                    <a href="{{ entry.repository.html_url }}" target="_blank" class="text-decoration-none">
                        {{ entry.repository.name }}
                    </a>
                </h6>
                <p class="card-text text-muted small">{{ entry.repository.description or 'No description available' }}</p>
                
                <div class="row text-center mb-3">
                    <div class="col-4">
                        <strong>{{ entry.repository.stargazers_count }}</strong><br>
                        <small class="text-muted">Stars</small>
                    </div>
                    <div class="col-4">
                        <strong>{{ entry.repository.forks_count }}</strong><br>
                        <small class="text-muted">Forks</small>
                    </div>
                    <div class="col-4">
                        <strong>{{ entry.repository.contributors_count }}</strong><br>
                        <small class="text-muted">Contributors</small>
                    </div>
                </div>

                {% if entry.repository.topics %}
                <div class="mb-2">
                    {% for topic in entry.repository.topics[:5] %}
                    <span class="badge bg-light text-dark cluster-tag me-1">{{ topic }}</span>
                    {% endfor %}
                </div>
                {% endif %}

                <div class="row">
                    <div class="col-6">
                        <small class="text-muted">
                            Updated: {{ entry.repository.updated_at.strftime('%m/%d/%Y') }}
                        </small>
                    </div>
                    <div class="col-6 text-end">
                        <small class="text-muted">
                            Score: {{ "%.2f"|format(entry.repository.final_score) }}
                        </small>
                    </div>
                </div>
            </div>
        </div>
    </div>
    {% endfor %}
</div>
{% endmacro %}
"""

        template_file = self.templates_dir / "leaderboard.html"
        if not template_file.exists():
            with open(template_file, 'w') as f:
                f.write(main_template)
    
    def generate_charts_data(self, leaderboard: Leaderboard) -> Dict[str, Any]:
        """Generate data for charts"""
        all_repos = []
        all_repos.extend([entry.repository for entry in leaderboard.trending])
        all_repos.extend([entry.repository for entry in leaderboard.established])
        all_repos.extend([entry.repository for entry in leaderboard.hidden_gems])
        
        # Language distribution
        languages = {}
        for repo in all_repos:
            if repo.language:
                languages[repo.language] = languages.get(repo.language, 0) + 1
        
        top_languages = dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Stars distribution
        star_ranges = {
            '1-100': 0,
            '101-1K': 0,
            '1K-10K': 0,
            '10K-50K': 0,
            '50K+': 0
        }
        
        for repo in all_repos:
            stars = repo.stargazers_count
            if stars <= 100:
                star_ranges['1-100'] += 1
            elif stars <= 1000:
                star_ranges['101-1K'] += 1
            elif stars <= 10000:
                star_ranges['1K-10K'] += 1
            elif stars <= 50000:
                star_ranges['10K-50K'] += 1
            else:
                star_ranges['50K+'] += 1
        
        # Top topics
        topics = {}
        for repo in all_repos:
            for topic in repo.topics:
                topics[topic] = topics.get(topic, 0) + 1
        
        top_topics = dict(sorted(topics.items(), key=lambda x: x[1], reverse=True)[:15])
        
        return {
            'languages': top_languages,
            'star_ranges': star_ranges,
            'topics': top_topics
        }
    
    def generate_charts_js(self, charts_data: Dict[str, Any]) -> str:
        """Generate JavaScript code for charts"""
        
        # Language pie chart
        language_fig = px.pie(
            values=list(charts_data['languages'].values()),
            names=list(charts_data['languages'].keys()),
            title="Language Distribution"
        )
        language_fig.update_layout(height=400)
        
        # Stars histogram
        stars_fig = px.bar(
            x=list(charts_data['star_ranges'].keys()),
            y=list(charts_data['star_ranges'].values()),
            title="Stars Distribution"
        )
        stars_fig.update_layout(height=400)
        
        # Topics bar chart
        topics_fig = px.bar(
            x=list(charts_data['topics'].values()),
            y=list(charts_data['topics'].keys()),
            orientation='h',
            title="Top Topics"
        )
        topics_fig.update_layout(height=600)
        
        js_code = f"""
        // Language Distribution Chart
        var languageData = {json.dumps(language_fig, cls=PlotlyJSONEncoder)};
        Plotly.newPlot('languageChart', languageData.data, languageData.layout);
        
        // Stars Distribution Chart
        var starsData = {json.dumps(stars_fig, cls=PlotlyJSONEncoder)};
        Plotly.newPlot('starsChart', starsData.data, starsData.layout);
        
        // Topics Chart
        var topicsData = {json.dumps(topics_fig, cls=PlotlyJSONEncoder)};
        Plotly.newPlot('topicsChart', topicsData.data, topicsData.layout);
        """
        
        return js_code
    
    def generate_html_dashboard(self, leaderboard: Leaderboard) -> Path:
        """Generate HTML dashboard"""
        logger.info("Generating HTML dashboard")
        
        # Generate charts data
        charts_data = self.generate_charts_data(leaderboard)
        charts_js = self.generate_charts_js(charts_data)
        
        # Helper function to get repository by ID
        def get_repo_by_id(repo_id: int) -> Optional[Repository]:
            all_repos = []
            all_repos.extend([entry.repository for entry in leaderboard.trending])
            all_repos.extend([entry.repository for entry in leaderboard.established])
            all_repos.extend([entry.repository for entry in leaderboard.hidden_gems])
            
            for repo in all_repos:
                if repo.id == repo_id:
                    return repo
            return None
        
        # Render template
        template = self.jinja_env.get_template("leaderboard.html")
        
        html_content = template.render(
            leaderboard=leaderboard,
            charts_js=charts_js,
            get_repo_by_id=get_repo_by_id
        )
        
        # Save HTML file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_file = self.output_dir / f"leaderboard_{timestamp}.html"
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Also save as latest
        latest_file = self.output_dir / "leaderboard_latest.html"
        with open(latest_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Generated HTML dashboard: {html_file}")
        return html_file
    
    def generate_json_export(self, leaderboard: Leaderboard) -> Path:
        """Generate JSON export of leaderboard data"""
        logger.info("Generating JSON export")
        
        # Convert leaderboard to dict and handle datetime serialization
        def convert_datetime(obj):
            if isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()
            else:
                return obj
        
        leaderboard_dict = convert_datetime(leaderboard.model_dump())
        
        # Save JSON file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = self.output_dir / f"leaderboard_{timestamp}.json"
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(leaderboard_dict, f, indent=2, ensure_ascii=False)
        
        # Also save as latest
        latest_file = self.output_dir / "leaderboard_latest.json"
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(leaderboard_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Generated JSON export: {json_file}")
        return json_file
    
    def generate_api_endpoints(self, leaderboard: Leaderboard) -> Dict[str, Path]:
        """Generate individual API endpoint files"""
        logger.info("Generating API endpoint files")
        
        api_dir = self.output_dir / "api"
        api_dir.mkdir(exist_ok=True)
        
        endpoints = {}
        
        # Individual category endpoints
        for category in ['trending', 'established', 'hidden_gems']:
            entries = getattr(leaderboard, category, [])
            category_data = {
                'category': category,
                'count': len(entries),
                'generated_at': leaderboard.generated_at.isoformat(),
                'repositories': [
                    {
                        'rank': entry.rank,
                        'id': entry.repository.id,
                        'name': entry.repository.name,
                        'full_name': entry.repository.full_name,
                        'description': entry.repository.description,
                        'html_url': entry.repository.html_url,
                        'stargazers_count': entry.repository.stargazers_count,
                        'forks_count': entry.repository.forks_count,
                        'language': entry.repository.language,
                        'topics': entry.repository.topics,
                        'updated_at': entry.repository.updated_at.isoformat(),
                        'final_score': entry.repository.final_score,
                        'change_from_previous': entry.change_from_previous
                    }
                    for entry in entries
                ]
            }
            
            endpoint_file = api_dir / f"{category}.json"
            with open(endpoint_file, 'w') as f:
                json.dump(category_data, f, indent=2)
            
            endpoints[category] = endpoint_file
        
        # Clusters endpoint
        clusters_data = {
            'count': len(leaderboard.clusters),
            'generated_at': leaderboard.generated_at.isoformat(),
            'clusters': [
                {
                    'id': cluster.id,
                    'name': cluster.name,
                    'description': cluster.description,
                    'size': cluster.size,
                    'repos': cluster.repos
                }
                for cluster in leaderboard.clusters
            ]
        }
        
        clusters_file = api_dir / "clusters.json"
        with open(clusters_file, 'w') as f:
            json.dump(clusters_data, f, indent=2)
        
        endpoints['clusters'] = clusters_file
        
        # Summary stats endpoint
        all_repos = []
        all_repos.extend([entry.repository for entry in leaderboard.trending])
        all_repos.extend([entry.repository for entry in leaderboard.established])
        all_repos.extend([entry.repository for entry in leaderboard.hidden_gems])
        
        # Calculate summary statistics
        total_stars = sum(repo.stargazers_count for repo in all_repos)
        total_forks = sum(repo.forks_count for repo in all_repos)
        
        languages = {}
        for repo in all_repos:
            if repo.language:
                languages[repo.language] = languages.get(repo.language, 0) + 1
        
        summary_data = {
            'generated_at': leaderboard.generated_at.isoformat(),
            'total_repositories': leaderboard.total_repos_analyzed,
            'categories': {
                'trending': len(leaderboard.trending),
                'established': len(leaderboard.established),
                'hidden_gems': len(leaderboard.hidden_gems)
            },
            'clusters': len(leaderboard.clusters),
            'total_stars': total_stars,
            'total_forks': total_forks,
            'top_languages': dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)[:10]),
            'data_freshness_hours': leaderboard.data_freshness_hours
        }
        
        summary_file = api_dir / "summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2)
        
        endpoints['summary'] = summary_file
        
        logger.info(f"Generated {len(endpoints)} API endpoint files")
        return endpoints
    
    def generate_all_outputs(self, leaderboard: Leaderboard) -> Dict[str, Path]:
        """Generate all output formats"""
        outputs = {}
        
        outputs['html'] = self.generate_html_dashboard(leaderboard)
        outputs['json'] = self.generate_json_export(leaderboard)
        outputs.update(self.generate_api_endpoints(leaderboard))
        
        logger.info(f"Generated all outputs: {list(outputs.keys())}")
        return outputs