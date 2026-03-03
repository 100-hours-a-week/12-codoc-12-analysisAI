import torch
from FlagEmbedding import BGEM3FlagModel


class EmbeddingService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model: BGEM3FlagModel | None = None

    def _load_model(self) -> BGEM3FlagModel:
        if self.model is None:
            self.model = BGEM3FlagModel(
                "BAAI/bge-m3",
                use_fp16=True if self.device == "cuda" else False,
                device=self.device
            )
            print(f"🚀 BGE-M3 모델 로드 완료 (Device: {self.device})")
        return self.model

    def get_embedding(self, text: str) -> list[float]:
        model = self._load_model()
        embeddings = model.encode([text], batch_size=1, max_length=8192)[
            "dense_vecs"
        ]

        return embeddings[0].tolist()


embedding_service = EmbeddingService()
