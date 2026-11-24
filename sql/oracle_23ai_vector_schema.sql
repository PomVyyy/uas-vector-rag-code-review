-- ============================================================================
-- ORACLE DATABASE 23ai: AI VECTOR SEARCH SCHEMA & CONFIGURATION
-- Mata Kuliah: AI / Big Data / Software Engineering - Lab Eksperimen UAS
-- Integrasi Materi Oracle Academy (OA) dengan Mining GitHub Pull Requests
-- ============================================================================

-- 1. KONFIGURASI MEMORY POOL SISTEM (SGA)
-- Parameter VECTOR_MEMORY_SIZE mengalokasikan area khusus di SGA untuk HNSW graph
ALTER SYSTEM SET VECTOR_MEMORY_SIZE = 1G SCOPE = BOTH;

-- 2. PEMBUATAN TABEL REPOSITORI & PULL REQUEST DENGAN TIPE DATA VECTOR
-- Tipe data VECTOR(384, FLOAT32) menyimpan representasi semantik deskripsi & diff kode PR
DROP TABLE github_pr_reviews CASCADE CONSTRAINTS;

CREATE TABLE github_pr_reviews (
    pr_id               VARCHAR2(50) PRIMARY KEY,
    repo_name           VARCHAR2(150) NOT NULL,
    repo_stars          NUMBER DEFAULT 0,
    project_age_month   NUMBER(5, 1),
    no_commits          NUMBER DEFAULT 1,
    pr_size             NUMBER DEFAULT 1,
    no_changed_files    NUMBER DEFAULT 1,
    is_gpt_assisted     NUMBER(1) CHECK (is_gpt_assisted IN (0, 1)),
    task_category       VARCHAR2(50),
    pr_title            VARCHAR2(500),
    pr_body             CLOB,
    review_comments     CLOB,
    phase_submission_h  NUMBER(8, 2),
    phase_review_h      NUMBER(8, 2),
    phase_waiting_h     NUMBER(8, 2),
    phase_change_h      NUMBER(8, 2),
    time_to_merge_h     NUMBER(8, 2),
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    -- Fitur Utama Oracle 23ai: Native Vector Data Type (384 Dimensi, FLOAT32)
    pr_vector           VECTOR(384, FLOAT32)
);

COMMENT ON COLUMN github_pr_reviews.pr_vector IS 'Semantic embedding vector derived from PR content via all-MiniLM-L6-v2 ONNX model';

-- 3. MEMORY ADVISOR UNTUK ESTIMASI KEBUTUHAN MEMORI INDEKS VEKTOR
-- Menggunakan paket DBMS_VECTOR.INDEX_VECTOR_MEMORY_ADVISOR
SET SERVEROUTPUT ON;
DECLARE
    v_response_json CLOB;
BEGIN
    DBMS_VECTOR.INDEX_VECTOR_MEMORY_ADVISOR(
        INDEX_TYPE     => 'HNSW',
        NUM_VECTORS    => 25000,
        DIM_COUNT      => 384,
        DIM_TYPE       => 'FLOAT32',
        PARAMETER_JSON => '{"neighbors": 32, "efConstruction": 128}',
        RESPONSE_JSON  => v_response_json
    );
    DBMS_OUTPUT.PUT_LINE('Hasil Estimasi Oracle Vector Memory Advisor:');
    DBMS_OUTPUT.PUT_LINE(v_response_json);
END;
/

-- 4. PEMBUATAN INDEKS VEKTOR HNSW (NEIGHBOR GRAPH)
-- Indeks In-Memory graph berkecepatan tinggi dengan metrik jarak COSINE
CREATE VECTOR INDEX idx_pr_hnsw_vector
ON github_pr_reviews(pr_vector)
ORGANIZATION INMEMORY NEIGHBOR GRAPH
DISTANCE COSINE
TARGET ACCURACY 95
PARAMETERS (NEIGHBORS 32, EFCONSTRUCTION 128);

-- 5. MONITORING STATUS PROGRES PEMBUATAN INDEKS
-- Menggunakan DBMS_VECTOR.GET_INDEX_STATUS
BEGIN
    DBMS_VECTOR.GET_INDEX_STATUS(
        OWNER_NAME => USER,
        INDEX_NAME => 'IDX_PR_HNSW_VECTOR'
    );
END;
/

-- 6. PEMBUATAN INDEKS VEKTOR HYBRID (HYBRID VECTOR INDEX)
-- Menggabungkan pencarian teks leksikal (token/regex) dan semantik vektor secara terpadu
-- Sesuai arsitektur slide 52-55 Oracle Academy
CREATE HYBRID VECTOR INDEX idx_pr_hybrid
ON github_pr_reviews(pr_body)
PARAMETERS('MODEL pr_embedding_onnx');
