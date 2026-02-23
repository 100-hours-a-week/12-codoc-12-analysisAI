import torch
from FlagEmbedding import BGEM3FlagModel


class EmbeddingService:
    def __init__(self):
        device = "cuda" if torch.cuda.is_available() else "cpu"

        self.model = BGEM3FlagModel(
            "BAAI/bge-m3", use_fp16=True if device == "cuda" else False, device=device
        )
        print(f"🚀 BGE-M3 모델 로드 완료 (Device: {device})")

    def get_embedding(self, text: str) -> list[float]:
        embeddings = self.model.encode([text], batch_size=1, max_length=8192)[
            "dense_vecs"
        ]

        return embeddings[0].tolist()


embedding_service = EmbeddingService()
