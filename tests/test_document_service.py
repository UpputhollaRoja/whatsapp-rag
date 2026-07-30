import pytest
from unittest.mock import MagicMock, patch
from services.document_service import document_service

def test_extract_text_from_empty_pdf_or_corrupt():
    with pytest.raises(ValueError, match="Failed to extract text from PDF"):
        document_service.extract_text_from_pdf(b"invalid pdf bytes content")

def test_process_and_ingest_empty_text_raises_error():
    doc_id = "test_doc_123"
    filename = "empty.txt"
    file_content = b"   \n   \n"
    mimetype = "text/plain"

    with patch("services.document_service.supabase") as mock_supabase:
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with pytest.raises(ValueError, match="No readable text found in document"):
            document_service.process_and_ingest_document(doc_id, filename, file_content, mimetype)

        mock_supabase.table.assert_called_with("documents")
        mock_table.update.assert_called_with({"status": "failed"})

def test_get_embeddings_batching():
    texts = [f"sample chunk {i}" for i in range(45)]
    mock_embedding = [0.1] * 1024

    with patch.object(document_service.openai_client.embeddings, "create") as mock_create:
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=mock_embedding) for _ in range(20)]
        mock_create.return_value = mock_response

        embeddings = document_service.get_embeddings(texts, batch_size=20)
        assert mock_create.call_count == 3  # 20 + 20 + 5
