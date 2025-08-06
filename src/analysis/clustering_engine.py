import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sentence_transformers import SentenceTransformer
import re
import pickle
from pathlib import Path

from models import Repository, Cluster

logger = logging.getLogger(__name__)

class ClusteringEngine:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.scaler = StandardScaler()
        self.embeddings_cache = {}
        self.cache_dir = Path("data/embeddings")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def preprocess_readme_text(self, readme_content: str) -> str:
        if not readme_content:
            return ""
        
        # Remove code blocks
        readme_content = re.sub(r'```[\s\S]*?```', '', readme_content)
        readme_content = re.sub(r'`[^`]*`', '', readme_content)
        
        # Remove URLs
        readme_content = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', readme_content)
        
        # Remove markdown formatting
        readme_content = re.sub(r'[#*_\-\[\](){}]', ' ', readme_content)
        
        # Clean up whitespace
        readme_content = ' '.join(readme_content.split())
        
        # Take first 512 words for consistency
        words = readme_content.split()[:512]
        
        return ' '.join(words)
    
    def extract_text_features(self, repo: Repository) -> str:
        features = []
        
        # Repository name and description
        if repo.name:
            features.append(repo.name.replace('-', ' ').replace('_', ' '))
        
        if repo.description:
            features.append(repo.description)
        
        # Topics
        if repo.topics:
            features.append(' '.join(repo.topics))
        
        # README content (preprocessed)
        if repo.readme_content:
            preprocessed_readme = self.preprocess_readme_text(repo.readme_content)
            features.append(preprocessed_readme)
        
        # Language information
        if repo.language:
            features.append(f"programming language {repo.language}")
        
        return ' '.join(features)
    
    def generate_embeddings(self, repositories: List[Repository], force_refresh: bool = False) -> Dict[int, np.ndarray]:
        embeddings = {}
        texts_to_encode = []
        repo_ids_to_encode = []
        
        cache_file = self.cache_dir / "embeddings_cache.pkl"
        
        # Load existing cache
        if not force_refresh and cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    self.embeddings_cache = pickle.load(f)
                logger.info(f"Loaded {len(self.embeddings_cache)} cached embeddings")
            except Exception as e:
                logger.warning(f"Could not load embeddings cache: {e}")
                self.embeddings_cache = {}
        
        # Prepare texts for encoding
        for repo in repositories:
            if not force_refresh and repo.id in self.embeddings_cache:
                embeddings[repo.id] = self.embeddings_cache[repo.id]
            else:
                text = self.extract_text_features(repo)
                if text.strip():
                    texts_to_encode.append(text)
                    repo_ids_to_encode.append(repo.id)
        
        # Generate new embeddings
        if texts_to_encode:
            logger.info(f"Generating embeddings for {len(texts_to_encode)} repositories")
            try:
                new_embeddings = self.model.encode(
                    texts_to_encode,
                    batch_size=32,
                    show_progress_bar=True,
                    normalize_embeddings=True
                )
                
                for repo_id, embedding in zip(repo_ids_to_encode, new_embeddings):
                    embeddings[repo_id] = embedding
                    self.embeddings_cache[repo_id] = embedding
                
                # Save updated cache
                with open(cache_file, 'wb') as f:
                    pickle.dump(self.embeddings_cache, f)
                
                logger.info(f"Generated and cached {len(new_embeddings)} new embeddings")
                
            except Exception as e:
                logger.error(f"Error generating embeddings: {e}")
                return {}
        
        return embeddings
    
    def find_optimal_clusters(self, embeddings: np.ndarray, max_clusters: int = 15) -> int:
        if len(embeddings) < 4:
            return 2
        
        silhouette_scores = []
        k_range = range(2, min(max_clusters + 1, len(embeddings)))
        
        for k in k_range:
            try:
                kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                cluster_labels = kmeans.fit_predict(embeddings)
                
                if len(set(cluster_labels)) > 1:  # Need at least 2 clusters
                    score = silhouette_score(embeddings, cluster_labels)
                    silhouette_scores.append((k, score))
            except Exception as e:
                logger.warning(f"Error evaluating k={k}: {e}")
                continue
        
        if not silhouette_scores:
            return 5  # Default fallback
        
        # Find k with best silhouette score
        best_k = max(silhouette_scores, key=lambda x: x[1])[0]
        logger.info(f"Optimal number of clusters: {best_k}")
        
        return best_k
    
    def perform_clustering(self, embeddings_dict: Dict[int, np.ndarray], n_clusters: int = None) -> Dict[int, int]:
        if not embeddings_dict:
            return {}
        
        repo_ids = list(embeddings_dict.keys())
        embeddings = np.array(list(embeddings_dict.values()))
        
        if len(embeddings) < 2:
            return {repo_ids[0]: 0} if repo_ids else {}
        
        # Determine optimal number of clusters
        if n_clusters is None:
            n_clusters = self.find_optimal_clusters(embeddings)
        
        try:
            # Primary clustering with K-Means
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(embeddings)
            
            # Map repository IDs to cluster IDs
            repo_clusters = {}
            for repo_id, cluster_id in zip(repo_ids, cluster_labels):
                repo_clusters[repo_id] = int(cluster_id)
            
            logger.info(f"Successfully clustered {len(repo_ids)} repositories into {n_clusters} clusters")
            
            # Log cluster distribution
            cluster_counts = {}
            for cluster_id in cluster_labels:
                cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1
            
            logger.info(f"Cluster distribution: {dict(sorted(cluster_counts.items()))}")
            
            return repo_clusters
            
        except Exception as e:
            logger.error(f"Error performing clustering: {e}")
            # Fallback: assign all to cluster 0
            return {repo_id: 0 for repo_id in repo_ids}
    
    def generate_cluster_descriptions(self, repositories: List[Repository], repo_clusters: Dict[int, int]) -> Dict[int, Cluster]:
        clusters = {}
        
        # Group repositories by cluster
        cluster_repos = {}
        for repo in repositories:
            if repo.id in repo_clusters:
                cluster_id = repo_clusters[repo.id]
                if cluster_id not in cluster_repos:
                    cluster_repos[cluster_id] = []
                cluster_repos[cluster_id].append(repo)
        
        # Generate descriptions for each cluster
        for cluster_id, repos in cluster_repos.items():
            # Analyze common topics
            all_topics = []
            all_languages = []
            all_descriptions = []
            
            for repo in repos:
                all_topics.extend(repo.topics)
                if repo.language:
                    all_languages.append(repo.language)
                if repo.description:
                    all_descriptions.append(repo.description)
            
            # Find most common topics and languages
            topic_counts = {}
            for topic in all_topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
            
            lang_counts = {}
            for lang in all_languages:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1
            
            # Generate cluster name and description
            top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            top_languages = sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)[:2]
            
            cluster_name = "AI/ML"
            if top_topics:
                main_topic = top_topics[0][0].replace('-', ' ').title()
                cluster_name = f"{main_topic} Projects"
            
            description_parts = []
            if top_topics:
                topics_str = ", ".join([topic[0] for topic in top_topics])
                description_parts.append(f"Focus areas: {topics_str}")
            
            if top_languages:
                langs_str = ", ".join([lang[0] for lang in top_languages])
                description_parts.append(f"Primary languages: {langs_str}")
            
            description_parts.append(f"{len(repos)} repositories")
            
            cluster_description = ". ".join(description_parts)
            
            # Calculate center embedding (mean of all repo embeddings in cluster)
            if hasattr(self, 'current_embeddings'):
                cluster_embeddings = []
                for repo in repos:
                    if repo.id in self.current_embeddings:
                        cluster_embeddings.append(self.current_embeddings[repo.id])
                
                if cluster_embeddings:
                    center_embedding = np.mean(cluster_embeddings, axis=0).tolist()
                else:
                    center_embedding = []
            else:
                center_embedding = []
            
            clusters[cluster_id] = Cluster(
                id=cluster_id,
                name=cluster_name,
                description=cluster_description,
                repos=[repo.id for repo in repos],
                center_embedding=center_embedding,
                size=len(repos)
            )
        
        return clusters
    
    def cluster_repositories(self, repositories: List[Repository], n_clusters: int = None) -> Tuple[Dict[int, int], Dict[int, Cluster]]:
        logger.info(f"Starting clustering process for {len(repositories)} repositories")
        
        # Generate embeddings
        embeddings_dict = self.generate_embeddings(repositories)
        if not embeddings_dict:
            logger.error("No embeddings generated, clustering failed")
            return {}, {}
        
        # Store embeddings for cluster description generation
        self.current_embeddings = embeddings_dict
        
        # Perform clustering
        repo_clusters = self.perform_clustering(embeddings_dict, n_clusters)
        
        # Generate cluster descriptions
        clusters = self.generate_cluster_descriptions(repositories, repo_clusters)
        
        # Update repository objects with cluster assignments
        for repo in repositories:
            if repo.id in repo_clusters:
                repo.cluster_id = repo_clusters[repo.id]
                if repo.id in embeddings_dict:
                    repo.readme_embedding = embeddings_dict[repo.id].tolist()
        
        logger.info(f"Clustering completed. Generated {len(clusters)} clusters")
        
        return repo_clusters, clusters
    
    def find_similar_repositories(self, target_repo_id: int, repositories: List[Repository], top_k: int = 5) -> List[Tuple[Repository, float]]:
        embeddings_dict = self.generate_embeddings(repositories)
        
        if target_repo_id not in embeddings_dict:
            return []
        
        target_embedding = embeddings_dict[target_repo_id]
        similarities = []
        
        for repo in repositories:
            if repo.id != target_repo_id and repo.id in embeddings_dict:
                # Calculate cosine similarity
                repo_embedding = embeddings_dict[repo.id]
                similarity = np.dot(target_embedding, repo_embedding) / (
                    np.linalg.norm(target_embedding) * np.linalg.norm(repo_embedding)
                )
                similarities.append((repo, float(similarity)))
        
        # Sort by similarity and return top k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]