-- ============================================================================
-- ORACLE DATABASE 23ai: ADVANCED AI VECTOR SEARCH QUERIES
-- Implementasi Query Bisnis Relasional + Semantik AI Vector Search
-- ============================================================================

-- QUERY 1: PENCARIAN KESERUPAAN VEKTOR MURNI (EXACT TOP-K SIMILARITY SEARCH)
-- Menemukan 10 Pull Request yang paling mirip konteks semantik kodenya
-- dengan vektor pertanyaan pengembang (:search_vector)
SELECT 
    pr_id,
    repo_name,
    task_category,
    pr_title,
    time_to_merge_h,
    ROUND(VECTOR_DISTANCE(pr_vector, :search_vector, COSINE), 4) AS cosine_distance,
    ROUND((1 - VECTOR_DISTANCE(pr_vector, :search_vector, COSINE)) * 100, 2) AS similarity_score_pct
FROM github_pr_reviews
ORDER BY VECTOR_DISTANCE(pr_vector, :search_vector, COSINE)
FETCH FIRST 10 ROWS ONLY;


-- QUERY 2: PENCARIAN APPROXIMATE MENGGUNAKAN HNSW INDEX (ACCELERATED TOP-K)
-- Menggunakan klausa APPROX untuk memanfaatkan graf HNSW in-memory (100x lebih cepat)
SELECT 
    pr_id,
    repo_name,
    task_category,
    time_to_merge_h,
    VECTOR_DISTANCE(pr_vector, :search_vector, COSINE) AS distance
FROM github_pr_reviews
ORDER BY VECTOR_DISTANCE(pr_vector, :search_vector, COSINE)
FETCH APPROX FIRST 10 ROWS ONLY;


-- QUERY 3: QUERY HYBRID BISNIS + SEMANTIK (CORE ORACLE 23ai ADVANTAGE)
-- Menggabungkan atribut relasional bisnis (kematangan proyek, ukuran PR) dengan jarak vektor
-- Sesuai arsitektur Slide 37: "Combines relational and AI search in 6 lines of SQL!"
SELECT 
    pr_id,
    repo_name,
    repo_stars,
    project_age_month,
    pr_size,
    is_gpt_assisted,
    time_to_merge_h,
    ROUND(VECTOR_DISTANCE(pr_vector, :search_vector, COSINE), 4) AS semantic_dist
FROM github_pr_reviews
WHERE repo_stars >= 1000                    -- Filter 1: Repositori populer & matang
  AND pr_size <= 500                        -- Filter 2: Ukuran PR mudah direview
  AND project_age_month >= 12              -- Filter 3: Proyek aktif minimal 1 tahun
ORDER BY VECTOR_DISTANCE(pr_vector, :search_vector, COSINE)
FETCH FIRST 10 ROWS ONLY;


-- QUERY 4: API PENCARIAN HYBRID DENGAN DBMS_HYBRID_VECTOR
-- Melakukan fusi skor antara pencarian teks leksikal kata kunci (Regex/BM25)
-- dan AI Vector Search melalui metode Reciprocal Score Fusion (RSF)
SELECT DBMS_HYBRID_VECTOR.SEARCH(
    JSON('{
        "hybrid_index_name": "IDX_PR_HYBRID",
        "search_text"       : "refactor memory leak in thread pool async loop",
        "vector_weight"     : 0.65,
        "text_weight"       : 0.35,
        "top_k"             : 5
    }')
) AS hybrid_search_results
FROM DUAL;


-- QUERY 5: ANALISIS KUANTITATIF WAKTU RESOLUSI PER KATEGORI TUGAS GPT (EMPIRICAL SQL)
SELECT 
    is_gpt_assisted,
    task_category,
    COUNT(*) AS total_prs,
    ROUND(AVG(time_to_merge_h), 2) AS mean_merge_hours,
    ROUND(MEDIAN(time_to_merge_h), 2) AS median_merge_hours,
    ROUND(MEDIAN(phase_review_h), 2) AS median_review_hours,
    ROUND(MEDIAN(phase_waiting_h), 2) AS median_waiting_hours,
    ROUND(MEDIAN(phase_change_h), 2) AS median_change_hours
FROM github_pr_reviews
GROUP BY is_gpt_assisted, task_category
ORDER BY is_gpt_assisted DESC, median_merge_hours ASC;
