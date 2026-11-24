"""
oracle_vector_simulation.py
Python Simulation of Oracle Database 23ai AI Vector Search Engine
Features replicated from Oracle Academy slides:
1. VECTOR datatype and distance metrics (Cosine, Euclidean, Manhattan, Dot)
2. HNSW In-Memory Neighbor Graph Index & Memory Advisor (DBMS_VECTOR.INDEX_VECTOR_MEMORY_ADVISOR)
3. Combined Business Relational Filter + Vector Distance Ranking
4. Hybrid Vector Search (DBMS_HYBRID_VECTOR.SEARCH) combining Text Search and Vector Search
"""

import os
import json
import numpy as np
import pandas as pd

class Oracle23aiVectorEngine:
    def __init__(self, dataset_csv=None, embeddings_npy=None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.dataset_path = dataset_csv or os.path.join(base_dir, "dataset", "github_pr_dataset.csv")
        self.embeddings_path = embeddings_npy or os.path.join(base_dir, "dataset", "pr_embeddings_384d.npy")
        
        self.df = pd.read_csv(self.dataset_path)
        self.embeddings = np.load(self.embeddings_path)
        self.num_vectors, self.dim = self.embeddings.shape
        print(f"[Oracle 23ai Engine] Initialized with {self.num_vectors} records, dimension = {self.dim}")
    
    # --- Distance Metrics (Slide 8 & Slide 18) ---
    @staticmethod
    def vector_distance(v1, v2, metric="COSINE"):
        v1 = np.asarray(v1, dtype=np.float32)
        v2 = np.asarray(v2, dtype=np.float32)
        
        if metric == "COSINE":
            # Cosine distance = 1 - cosine_similarity
            dot = np.dot(v1, v2)
            norm_product = np.linalg.norm(v1) * np.linalg.norm(v2)
            sim = dot / (norm_product + 1e-12)
            return float(1.0 - sim)
        elif metric == "EUCLIDEAN":
            return float(np.linalg.norm(v1 - v2))
        elif metric == "EUCLIDEAN_SQUARED":
            return float(np.sum((v1 - v2) ** 2))
        elif metric == "MANHATTAN":
            return float(np.sum(np.abs(v1 - v2)))
        elif metric == "DOT":
            return float(-np.dot(v1, v2))
        else:
            raise ValueError(f"Unknown metric {metric}")

    # --- Oracle Memory Advisor (Slides 46-48) ---
    def index_vector_memory_advisor(self, index_type="HNSW", num_vectors=None, dim_count=384, dim_type="FLOAT32", neighbors=32):
        n_vecs = num_vectors or self.num_vectors
        bytes_per_dim = 4 if dim_type == "FLOAT32" else (8 if dim_type == "FLOAT64" else 1)
        raw_vector_size = n_vecs * dim_count * bytes_per_dim
        
        if index_type.upper() == "HNSW":
            # Graph connections: neighbors pointers per vector + graph levels overhead (~1.25x)
            graph_overhead = n_vecs * neighbors * 8 * 1.25
            total_bytes = int(raw_vector_size + graph_overhead)
        else: # IVF / PARTITIONS
            centroids_size = 100 * dim_count * bytes_per_dim
            total_bytes = int(raw_vector_size + centroids_size * 2)
            
        mb = round(total_bytes / (1024 * 1024), 2)
        advice = {
            "status": "SUCCESS",
            "index_type": index_type,
            "num_vectors": n_vecs,
            "dim_count": dim_count,
            "dim_type": dim_type,
            "suggested_vector_memory_bytes": total_bytes,
            "suggested_vector_memory_mb": mb,
            "recommendation": f"Configure VECTOR_MEMORY_SIZE >= {int(np.ceil(mb * 1.2))} MB in SGA"
        }
        return advice

    # --- Similarity Search with Relational Filtering (Slide 36-37) ---
    def search_similarity(self, query_vector, top_k=10, metric="COSINE", filters=None):
        """
        Equivalent to SQL:
        SELECT * FROM github_pr_reviews
        WHERE [filters]
        ORDER BY VECTOR_DISTANCE(pr_vector, :query_vec, COSINE)
        FETCH FIRST :top_k ROWS ONLY;
        """
        filtered_df = self.df.copy()
        valid_indices = filtered_df.index
        
        # Apply relational business filters
        if filters:
            if "min_stars" in filters:
                filtered_df = filtered_df[filtered_df["repo_stars"] >= filters["min_stars"]]
            if "max_pr_size" in filters:
                filtered_df = filtered_df[filtered_df["pr_size"] <= filters["max_pr_size"]]
            if "min_project_age" in filters:
                filtered_df = filtered_df[filtered_df["project_age_month"] >= filters["min_project_age"]]
            if "is_gpt_assisted" in filters:
                filtered_df = filtered_df[filtered_df["is_gpt_assisted"] == filters["is_gpt_assisted"]]
            valid_indices = filtered_df.index
            
        if len(valid_indices) == 0:
            return pd.DataFrame()
            
        cand_embeddings = self.embeddings[valid_indices]
        # Vectorized cosine distance
        query_vec = np.asarray(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        cand_norms = np.linalg.norm(cand_embeddings, axis=1)
        dots = np.dot(cand_embeddings, query_vec)
        cos_sims = dots / (cand_norms * query_norm + 1e-12)
        distances = 1.0 - cos_sims
        
        result_df = filtered_df.copy()
        result_df["cosine_distance"] = np.round(distances, 4)
        result_df["similarity_score_pct"] = np.round(cos_sims * 100, 2)
        
        sorted_results = result_df.sort_values(by="cosine_distance", ascending=True).head(top_k)
        return sorted_results[[
            "pr_id", "repo_name", "task_category", "pr_title", 
            "repo_stars", "pr_size", "time_to_merge_h", 
            "cosine_distance", "similarity_score_pct"
        ]]

    # --- Hybrid Vector Search (Slides 52-55: DBMS_HYBRID_VECTOR.SEARCH) ---
    def hybrid_vector_search(self, search_text, query_vector, top_k=5, vector_weight=0.65, text_weight=0.35):
        """
        Simulates DBMS_HYBRID_VECTOR.SEARCH using Reciprocal Score Fusion (RSF)
        between lexical keyword matching and semantic vector similarity.
        """
        terms = [t.lower() for t in search_text.split() if len(t) > 2]
        
        # 1. Lexical Scoring (BM25 / Keyword count approximation)
        lexical_scores = np.zeros(len(self.df))
        for i, row in self.df.iterrows():
            text = f"{str(row['pr_title'])} {str(row['pr_body'])}".lower()
            matches = sum(text.count(term) for term in terms)
            lexical_scores[i] = matches
            
        # 2. Vector Semantic Scoring
        query_vec = np.asarray(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        norms = np.linalg.norm(self.embeddings, axis=1)
        vector_sims = np.dot(self.embeddings, query_vec) / (norms * query_norm + 1e-12)
        
        # 3. Score Fusion (Normalized)
        max_lex = np.max(lexical_scores) if np.max(lexical_scores) > 0 else 1.0
        norm_lexical = (lexical_scores / max_lex) * 100.0
        norm_vector = np.clip(vector_sims * 100.0, 0, 100.0)
        
        fused_scores = (vector_weight * norm_vector) + (text_weight * norm_lexical)
        
        res_df = self.df.copy()
        res_df["text_score"] = np.round(norm_lexical, 2)
        res_df["vector_score"] = np.round(norm_vector, 2)
        res_df["hybrid_score"] = np.round(fused_scores, 2)
        
        top_results = res_df.sort_values(by="hybrid_score", ascending=False).head(top_k)
        
        output_records = []
        for rank, (_, row) in enumerate(top_results.iterrows(), start=1):
            output_records.append({
                "rank": rank,
                "pr_id": row["pr_id"],
                "repo_name": row["repo_name"],
                "task_category": row["task_category"],
                "pr_title": row["pr_title"],
                "vector_score": float(row["vector_score"]),
                "text_score": float(row["text_score"]),
                "hybrid_score": float(row["hybrid_score"])
            })
            
        return output_records

if __name__ == "__main__":
    engine = Oracle23aiVectorEngine()
    
    print("\n--- TEST 1: Oracle Vector Memory Advisor ---")
    advisor = engine.index_vector_memory_advisor(index_type="HNSW", num_vectors=25000, dim_count=384)
    print(json.dumps(advisor, indent=2))
    
    print("\n--- TEST 2: Relational + Vector Top-5 Similarity Search ---")
    sample_query_vector = engine.embeddings[0] # Use embedding of first record
    results = engine.search_similarity(
        query_vector=sample_query_vector,
        top_k=5,
        filters={"min_stars": 50, "max_pr_size": 1000}
    )
    print(results.to_string(index=False))
    
    print("\n--- TEST 3: Hybrid Vector Search (DBMS_HYBRID_VECTOR) ---")
    hybrid_res = engine.hybrid_vector_search(
        search_text="refactor thread pool memory leak",
        query_vector=sample_query_vector,
        top_k=3
    )
    print(json.dumps(hybrid_res, indent=2))
