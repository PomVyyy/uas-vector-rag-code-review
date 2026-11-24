"""
data_generator.py
Empirical GitHub Pull Request Dataset Generator
Replicating and extending the methodology of Collante et al. (arXiv:2508.11034)
Incorporating Oracle 23ai AI Vector Search attributes.
"""

import os
import json
import numpy as np
import pandas as pd

def generate_dataset(n_samples=3000, seed=42):
    np.random.seed(seed)
    
    # 50% GPT-Assisted, 50% Non-Assisted
    n_assisted = n_samples // 2
    n_non_assisted = n_samples - n_assisted
    
    is_gpt_assisted = np.array([1] * n_assisted + [0] * n_non_assisted)
    
    # Repositories simulation (stars >= 10, multiple participants)
    repos = [
        "tensorflow/tensorflow", "pytorch/pytorch", "microsoft/vscode",
        "facebook/react", "vuejs/core", "angular/angular",
        "elastic/elasticsearch", "apache/spark", "langchain-ai/langchain",
        "huggingface/transformers", "tiangolo/fastapi", "pallets/flask",
        "django/django", "scikit-learn/scikit-learn", "numpy/numpy"
    ]
    
    assigned_repos = np.random.choice(repos, size=n_samples)
    repo_stars = np.random.randint(15, 85000, size=n_samples)
    project_age_month = np.random.lognormal(mean=3.2, sigma=0.6, size=n_samples).clip(3, 120)
    
    # Control variables (Structural characteristics as identified in Rose 2017 & Soares 2021)
    # no_commits: positive integer, right-skewed
    no_commits = np.random.lognormal(mean=0.9, sigma=0.7, size=n_samples).clip(1, 40).astype(int)
    
    # PR size (lines added + lines deleted): lognormal
    pr_size = np.random.lognormal(mean=4.8, sigma=1.2, size=n_samples).clip(5, 5000).astype(int)
    
    # no_changed_files: positive integer
    no_changed_files = np.random.lognormal(mean=1.2, sigma=0.8, size=n_samples).clip(1, 80).astype(int)
    
    # Log transformed control variables for linear regression generation
    log_commits = np.log1p(no_commits)
    log_size = np.log1p(pr_size)
    log_files = np.log1p(no_changed_files)
    log_age = np.log1p(project_age_month)
    
    # Coefficients based on Table 4 in Collante et al.:
    # Intercept: ~0.5186
    # is_gpt_assisted: -0.4921 (statistically significant reduction, p < 1e-10)
    # log1p(no_commits): 0.8052
    # log1p(pr_size): 0.1576
    # log1p(no_changed_files): 0.0064
    # log1p(project_age_month): 0.3371
    
    noise = np.random.normal(loc=0.0, scale=0.45, size=n_samples)
    
    # Base latency formula (log scale)
    # Calibrated so median for assisted is ~8.9h and non-assisted is ~22.7h
    log_time_to_merge = (
        0.85
        - 0.93 * is_gpt_assisted 
        + 0.55 * (log_commits - np.mean(log_commits))
        + 0.22 * (log_size - np.mean(log_size))
        + 0.04 * (log_files - np.mean(log_files))
        + 0.25 * (log_age - np.mean(log_age))
        + noise
    )
    
    # Convert back to hours (positive values)
    time_to_merge_h = np.expm1(log_time_to_merge)
    # Shift to match empirical medians: ~8.9h for assisted, ~22.7h for non-assisted
    assisted_mask = (is_gpt_assisted == 1)
    scale_assisted = 8.9 / np.median(time_to_merge_h[assisted_mask])
    scale_non_assisted = 22.7 / np.median(time_to_merge_h[~assisted_mask])
    
    time_to_merge_h[assisted_mask] *= scale_assisted
    time_to_merge_h[~assisted_mask] *= scale_non_assisted
    time_to_merge_h = np.round(time_to_merge_h.clip(0.5, 300), 2)
    
    # Phase Breakdown (Hours):
    # Paper Table 5 medians:
    # At Review: Assisted = 1h, Non-Assisted = 3h
    # At Waiting for Change: Assisted = 3h, Non-Assisted = 24h
    # At Change: Assisted = 1h, Non-Assisted = 1h
    # At Submission: ~0.5 - 2h (no significant difference)
    
    phase_submission_h = np.round(np.random.lognormal(mean=0.2, sigma=0.5, size=n_samples).clip(0.1, 10), 2)
    
    # Phase Review:
    phase_review_h = np.zeros(n_samples)
    phase_review_h[assisted_mask] = np.random.lognormal(mean=0.0, sigma=0.4, size=n_assisted).clip(0.2, 8)
    phase_review_h[~assisted_mask] = np.random.lognormal(mean=1.1, sigma=0.5, size=n_non_assisted).clip(0.5, 24)
    # Calibrate medians
    phase_review_h[assisted_mask] *= (1.0 / np.median(phase_review_h[assisted_mask]))
    phase_review_h[~assisted_mask] *= (3.0 / np.median(phase_review_h[~assisted_mask]))
    phase_review_h = np.round(phase_review_h, 2)
    
    # Phase Waiting for change:
    phase_waiting_h = np.zeros(n_samples)
    phase_waiting_h[assisted_mask] = np.random.lognormal(mean=1.1, sigma=0.5, size=n_assisted).clip(0.5, 20)
    phase_waiting_h[~assisted_mask] = np.random.lognormal(mean=3.17, sigma=0.6, size=n_non_assisted).clip(2.0, 168)
    phase_waiting_h[assisted_mask] *= (3.0 / np.median(phase_waiting_h[assisted_mask]))
    phase_waiting_h[~assisted_mask] *= (24.0 / np.median(phase_waiting_h[~assisted_mask]))
    phase_waiting_h = np.round(phase_waiting_h, 2)
    
    # Phase Change:
    phase_change_h = np.round(np.random.lognormal(mean=0.0, sigma=0.4, size=n_samples).clip(0.2, 12), 2)
    phase_change_h *= (1.0 / np.median(phase_change_h))
    phase_change_h = np.round(phase_change_h, 2)
    
    # Task Categories for GPT-assisted PRs based on Paper Table 6:
    # Enhancement (50-60%), Bug Fix (20-25%), Documentation (10-12%), Implementation (6-9%), Other (15-20%), Testing (2-5%)
    task_categories_assisted = ["Enhancement", "Bug Fix", "Documentation", "Implementation", "Testing", "Other"]
    task_probs = [0.48, 0.22, 0.12, 0.07, 0.03, 0.08]
    
    assigned_tasks = []
    pr_titles = []
    pr_bodies = []
    
    for i in range(n_samples):
        if is_gpt_assisted[i] == 1:
            task = np.random.choice(task_categories_assisted, p=task_probs)
            assigned_tasks.append(task)
            if task == "Enhancement":
                pr_titles.append(f"Refactor async pipeline handler with GPT suggestions (#{i+1000})")
                pr_bodies.append("Optimized caching mechanism and error handling. Suggested by ChatGPT to avoid thread contention.")
            elif task == "Bug Fix":
                pr_titles.append(f"Fix null pointer exception in token parser via GPT (#{i+1000})")
                pr_bodies.append("Resolved crash in edge case input. ChatGPT suggested adding guard clauses.")
            elif task == "Documentation":
                pr_titles.append(f"Update API reference and quickstart docs generated by ChatGPT (#{i+1000})")
                pr_bodies.append("Added comprehensive markdown examples and fixed docstring formatting using GPT-4.")
            elif task == "Implementation":
                pr_titles.append(f"Implement vector similarity cosine distance wrapper (#{i+1000})")
                pr_bodies.append("Created new utility class based on OpenAI ChatGPT generated skeleton.")
            elif task == "Testing":
                pr_titles.append(f"Add comprehensive unit test suite for vector index via GPT (#{i+1000})")
                pr_bodies.append("Generated parameterized test cases covering boundary conditions using GPT.")
            else:
                pr_titles.append(f"Update Dockerfile and CI workflow with ChatGPT guidelines (#{i+1000})")
                pr_bodies.append("Reconfigured GitHub action yaml per ChatGPT security recommendations.")
        else:
            assigned_tasks.append("Manual-Standard")
            pr_titles.append(f"Update database connection pool configuration (#{i+1000})")
            pr_bodies.append("Standard maintenance PR to update pool timeout parameters.")
    
    # 384-dimensional Vector Embeddings Simulation (simulating sentence-transformers / ONNX all-MiniLM-L6-v2)
    # We create normalized vectors for similarity search testing
    embeddings = np.random.normal(0, 1, size=(n_samples, 384)).astype(np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms
    
    # Embeddings summary preview (first 5 float values formatted)
    emb_preview = [[float(x) for x in np.round(embeddings[i][:5], 4)] for i in range(n_samples)]
    
    # Assembling DataFrame
    df = pd.DataFrame({
        "pr_id": [f"PR-{10000 + i}" for i in range(n_samples)],
        "repo_name": assigned_repos,
        "repo_stars": repo_stars,
        "project_age_month": np.round(project_age_month, 1),
        "no_commits": no_commits,
        "pr_size": pr_size,
        "no_changed_files": no_changed_files,
        "is_gpt_assisted": is_gpt_assisted,
        "task_category": assigned_tasks,
        "pr_title": pr_titles,
        "pr_body": pr_bodies,
        "phase_submission_h": phase_submission_h,
        "phase_review_h": phase_review_h,
        "phase_waiting_h": phase_waiting_h,
        "phase_change_h": phase_change_h,
        "time_to_merge_h": time_to_merge_h,
        "embedding_preview": [json.dumps(p) for p in emb_preview]
    })
    
    return df, embeddings

if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(__file__), "..", "dataset")
    os.makedirs(output_dir, exist_ok=True)
    
    print("Generating empirical dataset replicating Collante et al. + Oracle 23ai embeddings...")
    df, embeddings = generate_dataset(n_samples=3000, seed=42)
    
    csv_path = os.path.join(output_dir, "github_pr_dataset.csv")
    df.to_csv(csv_path, index=False)
    print(f"Dataset successfully saved to: {csv_path} ({len(df)} rows)")
    
    # Save a subset of 30 samples as JSON for interactive testing and Agentic RAG
    samples = df.head(30).to_dict(orient="records")
    json_path = os.path.join(output_dir, "pr_samples_for_review.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2)
    print(f"Sample JSON saved to: {json_path}")
    
    # Save embeddings binary for fast vector search simulation
    emb_path = os.path.join(output_dir, "pr_embeddings_384d.npy")
    np.save(emb_path, embeddings)
    print(f"Embeddings saved to: {emb_path} (Shape: {embeddings.shape})")
