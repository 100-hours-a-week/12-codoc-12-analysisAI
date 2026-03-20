from pydantic import BaseModel, HttpUrl, field_validator


class Images(BaseModel):
    order: int
    url: HttpUrl


class WorkbookQueueRequest(BaseModel):
    customProblemId: int
    images: list[Images]

    @field_validator("images")
    def validate_images(cls, v):
        orders = [img.order for img in v]
        if len(orders) != len(set(orders)):
            raise ValueError("order 값이 중복됩니다.")
        return sorted(v, key=lambda x: x.order)


class ProblemDetail(BaseModel):
    title: str
    content: str


class SummaryCard(BaseModel):
    paragraph_type: str
    paragraph_order: int
    answer_index: int
    choices: list[str]


class Quiz(BaseModel):
    quiz_type: str
    question: str
    choices: list[str]
    answer_index: int
    explanation: str
    sequence: int


class WorkbookResponseData(BaseModel):
    problem_detail: ProblemDetail
    summary_card: list[SummaryCard]
    quiz: list[Quiz]
