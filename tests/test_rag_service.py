import pytest
from unittest.mock import MagicMock, patch
from services.rag_service import rag_service

def test_search_documents_empty_results():
    with patch.object(rag_service.index, "query") as mock_query:
        mock_results = MagicMock()
        mock_results.matches = []
        mock_query.return_value = mock_results

        context = rag_service.search_documents([0.1, 0.2])
        assert context == ""

def test_generate_answer_fallback_on_api_error():
    with patch.object(rag_service, "get_query_embedding", side_effect=Exception("API Connection Timeout")):
        answer = rag_service.generate_answer("who is rama", "+919876543210")
        assert "unable to process your request" in answer
