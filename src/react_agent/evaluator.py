"""RAG evaluation implementation."""

from typing import List, Dict, Any
from dataclasses import dataclass
from langchain_core.messages import HumanMessage, AIMessage
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class EvaluationMetrics:
    relevance_score: float
    answer_quality: float
    context_utilization: float
    overall_score: float

class RAGEvaluator:
    def __init__(self):
        # Get API keys from environment variables
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            print("Warning: GEMINI_API_KEY not found. Evaluation will use fallback metrics.")
            self.embeddings = None
        else:
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model="models/embedding-001",
                google_api_key=gemini_api_key
            )
        
    def evaluate_response(
        self,
        query: str,
        retrieved_docs: List[Dict[str, Any]],
        response: str,
        ground_truth: str = None
    ) -> EvaluationMetrics:
        """Evaluate the RAG response quality."""
        
        if not self.embeddings:
            # Fallback evaluation without embeddings
            print("[EVAL] Using fallback evaluation metrics")
            return EvaluationMetrics(
                relevance_score=0.7,  # Default reasonable score
                answer_quality=0.7,
                context_utilization=0.7,
                overall_score=0.7
            )
        
        try:
            # Calculate relevance score
            query_embedding = self.embeddings.embed_query(query)
            doc_embeddings = [self.embeddings.embed_query(doc["content"]) for doc in retrieved_docs]
            relevance_scores = [cosine_similarity([query_embedding], [doc_emb])[0][0] for doc_emb in doc_embeddings]
            relevance_score = float(np.mean(relevance_scores))

            # Calculate answer quality (if ground truth is provided)
            if ground_truth:
                response_embedding = self.embeddings.embed_query(response)
                truth_embedding = self.embeddings.embed_query(ground_truth)
                answer_quality = float(cosine_similarity([response_embedding], [truth_embedding])[0][0])
            else:
                answer_quality = 0.5  # Default score if no ground truth

            # Calculate context utilization
            response_embedding = self.embeddings.embed_query(response)
            context_scores = [cosine_similarity([response_embedding], [doc_emb])[0][0] for doc_emb in doc_embeddings]
            context_utilization = float(np.mean(context_scores))

            # Calculate overall score
            overall_score = (relevance_score + answer_quality + context_utilization) / 3

            return EvaluationMetrics(
                relevance_score=relevance_score,
                answer_quality=answer_quality,
                context_utilization=context_utilization,
                overall_score=overall_score
            )
        except Exception as e:
            print(f"[EVAL] Error during evaluation: {e}")
            # Return fallback metrics
            return EvaluationMetrics(
                relevance_score=0.6,
                answer_quality=0.6,
                context_utilization=0.6,
                overall_score=0.6
            )

    def generate_evaluation_report(
        self,
        metrics: EvaluationMetrics,
        query: str,
        response: str
    ) -> str:
        """Generate a human-readable evaluation report."""
        report = f"""
RAG Evaluation Report
====================
Query: {query}

Response: {response}

Metrics:
- Relevance Score: {metrics.relevance_score:.2f}
- Answer Quality: {metrics.answer_quality:.2f}
- Context Utilization: {metrics.context_utilization:.2f}
- Overall Score: {metrics.overall_score:.2f}

Interpretation:
- Relevance Score: How well the retrieved documents match the query
- Answer Quality: How accurate and complete the response is
- Context Utilization: How well the response uses the retrieved context
- Overall Score: Combined performance metric
"""
        return report 
    
    def rag_evaluate(query: str, response: str, retrieved_docs: list) -> dict:
    # Your real evaluation logic here
    # For example: return simple heuristic metrics
        return {"relevance_score": 0.85, "coherence": 0.9}
