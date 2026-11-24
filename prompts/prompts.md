# Repository of Prompt Templates for Agentic RAG Code Review
**Project:** Empiris Code Review Acceleration with Oracle 23ai AI Vector Search & Agentic RAG  
**Author:** Mahasiswa Teknik Informatika / Ilmu Komputer (UIN Syarif Hidayatullah Jakarta)  
**Instructor:** Dr. Rizal Broer Bahaweres, S.Kom, M.Sc (rizalbroer@uinjkt.ac.id)  

---

## 1. System Prompt (Principal Reviewer Agent)
```text
You are an expert Principal Software Engineer and Code Review Assistant specializing in high-performance concurrent systems, clean architecture, and automated PR triage.
Your role is to strictly assess incoming Pull Requests against organizational coding standards, architectural best practices, and verified past resolutions retrieved from the Oracle Database 23ai Vector Store.
Maintain high objectivity, prioritize critical security and memory hazards, and provide drop-in code refactorings.
```

---

## 2. Agentic Query Decomposition Prompt (Slide 68 Oracle Academy)
```text
Task: Given the following developer request:
"{user_query}"

Decompose this task into three discrete, verifiable sub-questions:
(a) Sub-question 1 [Data Retrieval]: Retrieve exact structural metrics (lines added/deleted, commits, file types) and AST representation.
(b) Sub-question 2 [AI Vector Search]: Execute semantic similarity search on Oracle Database 23ai Vector Store to find top-K matching policies, concurrency guidelines, and similar solved PRs.
(c) Sub-question 3 [Synthesis & Decision]: Compare retrieved policies with the modified code to check for anti-patterns, memory leaks, or race conditions. Synthesize the final review verdict.
```

---

## 3. Evaluative Review Synthesis Prompt (Slide 71 Oracle Academy)
```text
PR Context:
- Repository: {repo_name}
- PR Title: {pr_title}
- Total Modified Lines: {pr_size} (Added + Deleted)
- Commits: {no_commits}
- Files Changed: {no_changed_files}

Retrieved Ground-Truth Guidelines from Oracle 23ai Vector Database:
{retrieved_context}

Instruction:
Evaluate the proposed PR modifications against the retrieved standards.
Output format:
1. Executive Verdict: [APPROVE | REQUEST_CHANGES | COMMENT]
2. Confidence Score: [0 - 100%]
3. Concurrency / Memory Safety Analysis
4. Actionable Refactored Code Block (if changes requested)
5. Test Recommendations
```

---

## 4. Hybrid Detection Prompt (Regex + Semantic Classifier)
```text
Task: Classify whether a Pull Request conversation utilizes Generative AI (GPT/Gemini) as an interactive Code Review Assistant vs pure implementation API.
Input:
- PR Title: {pr_title}
- PR Body & Comments: {pr_text}
- Regex Matches Detected: {regex_matches}
- Vector Cosine Similarity Score to Assistance Anchor: {vector_score}

Decision Rule:
If Regex match in (P12, P16, P17, P18) AND Vector Cosine Similarity >= 0.72:
    Classify as: GPT-Assisted (Assistance = 1)
Else:
    Classify as: Non-Assisted (Assistance = 0)
```
