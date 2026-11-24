"""
agentic_rag_system.py
Implementation of Agentic RAG for GitHub Code Review
Directly applying the workflow architecture from Oracle Academy slides 66-72.
"""

import os
import json
import numpy as np
import pandas as pd
from oracle_vector_simulation import Oracle23aiVectorEngine

class AgenticRAGReviewSystem:
    def __init__(self):
        self.vector_engine = Oracle23aiVectorEngine()
        self.prompts_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "prompts", 
            "agentic_rag_prompts.json"
        )
        with open(self.prompts_path, "r", encoding="utf-8") as f:
            self.prompts = json.load(f)
            
        # Knowledge Base of Coding Guidelines and Security Rules stored in Vector DB
        self.guidelines_db = [
            {
                "id": "RULE-CONC-01",
                "title": "Thread Pool Contention & Deadlock Prevention",
                "content": "When dispatching asynchronous tasks, always specify bounded task queues and explicit timeouts. Never block on Future.get() within the worker thread pool.",
                "category": "Concurrency"
            },
            {
                "id": "RULE-MEM-02",
                "title": "Memory Leak Prevention in Async Generators",
                "content": "Ensure resources are released using try-finally or context managers (with / using statements). Clear references in long-lived event listeners.",
                "category": "Memory"
            },
            {
                "id": "RULE-SEC-03",
                "title": "Input Validation and Sanitization",
                "content": "All external user inputs, file paths, and query parameters must be validated and sanitized against injection attacks before database execution.",
                "category": "Security"
            },
            {
                "id": "RULE-ERR-04",
                "title": "Structured Error Handling & Guard Clauses",
                "content": "Avoid catching generic Exception. Handle specific checked exceptions and provide structured error logs with context metadata.",
                "category": "Reliability"
            }
        ]

    def step1_decompose_query(self, user_query):
        """
        Oracle Academy Slide 68:
        Step 1: Decompose user question into multiple sub-questions
        """
        decomposition = {
            "original_query": user_query,
            "sub_questions": [
                {
                    "step": "a",
                    "question": "What files, commits, and diff sizes are involved in this PR?",
                    "type": "Data Retrieval",
                    "target_source": "GitHub REST API / Repo Metadata"
                },
                {
                    "step": "b",
                    "question": "Which organizational engineering guidelines and past PR solutions are semantically relevant to this change?",
                    "type": "AI Vector Search + RAG",
                    "target_source": "Oracle 23ai Vector Database (HNSW Index)"
                },
                {
                    "step": "c",
                    "question": "Do the proposed changes violate identified guidelines, and what specific refactoring or bug fix should be recommended?",
                    "type": "Reasoning & Action",
                    "target_source": "LLM Synthesis Engine"
                }
            ]
        }
        return decomposition

    def step2_execute_data_retrieval(self, pr_record):
        """
        Oracle Academy Slide 69:
        Step 2: Run actions corresponding to sub-question (a) - Data Retrieval
        """
        context = {
            "pr_id": pr_record.get("pr_id", "PR-UNKNOWN"),
            "repo_name": pr_record.get("repo_name", "generic/repo"),
            "pr_title": pr_record.get("pr_title", ""),
            "pr_body": pr_record.get("pr_body", ""),
            "pr_size": pr_record.get("pr_size", 0),
            "no_commits": pr_record.get("no_commits", 0),
            "no_changed_files": pr_record.get("no_changed_files", 0)
        }
        return context

    def step3_execute_vector_rag(self, pr_context, top_k=2):
        """
        Oracle Academy Slide 70:
        Step 3: Run actions corresponding to sub-question (b) - AI Vector Search
        """
        # Formulate search intent text from PR title & body
        search_query = f"{pr_context['pr_title']} {pr_context['pr_body']}"
        
        # Match guidelines based on keyword and semantic intent
        relevant_rules = []
        for rule in self.guidelines_db:
            score = 0.5
            if any(term in search_query.lower() for term in ["thread", "async", "pipeline", "concurrency"]):
                if rule["category"] == "Concurrency":
                    score = 0.95
            elif any(term in search_query.lower() for term in ["null", "exception", "guard", "error", "leak"]):
                if rule["category"] in ["Reliability", "Memory"]:
                    score = 0.90
            elif any(term in search_query.lower() for term in ["doc", "docs", "readme", "markdown"]):
                score = 0.75
            relevant_rules.append((score, rule))
            
        relevant_rules.sort(key=lambda x: x[0], reverse=True)
        top_rules = [r[1] for r in relevant_rules[:top_k]]
        return top_rules

    def step4_synthesize_review(self, pr_context, retrieved_guidelines):
        """
        Oracle Academy Slide 71:
        Step 4: Run actions corresponding to sub-question (c) - Synthesis / Action
        """
        rules_text = "\n".join([f"- [{r['id']}] {r['title']}: {r['content']}" for r in retrieved_guidelines])
        
        prompt = self.prompts["review_prompt_template"].format(
            repo_name=pr_context["repo_name"],
            pr_title=pr_context["pr_title"],
            pr_size=pr_context["pr_size"],
            retrieved_context=rules_text
        )
        
        # Simulated LLM generation (e.g. Gemini / GPT-4)
        has_critical_issue = any("concurrency" in r["category"].lower() or "memory" in r["category"].lower() for r in retrieved_guidelines)
        
        if has_critical_issue:
            verdict = "REQUEST_CHANGES"
            confidence = 94.5
            actionable_feedback = (
                f"**Reviewer Verdict: {verdict}**\n"
                f"Found potential issue aligning with guideline `{retrieved_guidelines[0]['id']}`.\n"
                f"Recommendation: Ensure that async worker dispatch implements timeout handling to avoid thread starvation."
            )
        else:
            verdict = "APPROVE"
            confidence = 96.0
            actionable_feedback = (
                f"**Reviewer Verdict: {verdict}**\n"
                f"Changes adhere to project standards. Code size ({pr_context['pr_size']} lines) is well-bounded."
            )
            
        return {
            "verdict": verdict,
            "confidence_score": confidence,
            "feedback": actionable_feedback,
            "prompt_used": prompt
        }

    def run_agentic_pipeline(self, user_query, sample_pr):
        print(f"\n=======================================================")
        print(f" AGENTIC RAG PIPELINE: CODE REVIEW TRIAGE")
        print(f"=======================================================")
        print(f"[Input Query]: {user_query}")
        
        # Step 1: Decomposition
        decomp = self.step1_decompose_query(user_query)
        print("\n--- STEP 1: Query Decomposition ---")
        for sq in decomp["sub_questions"]:
            print(f"  [{sq['step']}] ({sq['type']}): {sq['question']}")
            
        # Step 2: Data Retrieval
        context = self.step2_execute_data_retrieval(sample_pr)
        print("\n--- STEP 2: PR Data Retrieval ---")
        print(f"  Target PR: {context['pr_id']} ({context['repo_name']})")
        print(f"  Title: {context['pr_title']}")
        print(f"  Diff Size: {context['pr_size']} lines, Commits: {context['no_commits']}")
        
        # Step 3: Vector Search
        retrieved_rules = self.step3_execute_vector_rag(context, top_k=2)
        print("\n--- STEP 3: Oracle 23ai AI Vector Search Retrieval ---")
        for r in retrieved_rules:
            print(f"  Retrieved Rule: {r['id']} - {r['title']}")
            
        # Step 4: LLM Synthesis & Decision
        review_result = self.step4_synthesize_review(context, retrieved_rules)
        print("\n--- STEP 4: Evaluative Synthesis & Decision ---")
        print(f"  Confidence: {review_result['confidence_score']}%")
        print(f"  Output:\n{review_result['feedback']}")
        
        return {
            "decomposition": decomp,
            "context": context,
            "retrieved_rules": retrieved_rules,
            "review_result": review_result
        }

if __name__ == "__main__":
    system = AgenticRAGReviewSystem()
    sample_pr = {
        "pr_id": "PR-10696",
        "repo_name": "pytorch/pytorch",
        "pr_title": "Refactor async pipeline handler with GPT suggestions (#1696)",
        "pr_body": "Optimized caching mechanism and error handling. Suggested by ChatGPT to avoid thread contention.",
        "pr_size": 22,
        "no_commits": 2,
        "no_changed_files": 1
    }
    system.run_agentic_pipeline(
        user_query="Please review this async PR for potential thread deadlock and adherence to concurrency standards.",
        sample_pr=sample_pr
    )
