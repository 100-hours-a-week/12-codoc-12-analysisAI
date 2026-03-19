from app.common.exceptions.base_exception import BusinessException


# 401: 인증 실패 (토큰 없음, 만료 등)
class CredentialException(BusinessException):
    def __init__(self, message: str = "자격 증명을 검증할 수 없습니다."):
        super().__init__(errorCode="AUTH_401", message=message)


# 403: 권한 없음 (관리자만 접근 가능 등)
class UnauthorizedException(BusinessException):
    def __init__(self, message: str = "해당 권한을 가진 사용자가 아닙니다."):
        super().__init__(errorCode="AUTH_403", message=message)

# 400
class InvalidStarterConditionException(BusinessException):
    def __init__(
        self, message: str = "NEW 시나리오는 solved < 5 조건에서만 사용 가능"
    ):
        super().__init__(errorCode="RECOMMEND_400", message=message)

# 404
class RecommendationNotFoundException(BusinessException):
    def __init__(self, message: str = "추천 결과가 없습니다."):
        super().__init__(errorCode="RECOMMEND_404", message=message)

# 424 : 근거 데이터 부족
class DependencyNotReadyException(BusinessException):
    def __init__(self, message:str = "VectorDB/근거 데이터가 아직 준비되지 않았습니다."):
        super().__init__(errorCode="DEPENDENCY_NOT_READY", message=message)

# 400 : OCR 처리 실패
class OcrProcessingException(BusinessException):
    def __init__(self, message: str = "OCR 처리에 실패했습니다."):
        super().__init__(errorCode="OCR_400", message=message)

# 422 : 코딩테스트 이미지가 아님
class InvalidImageException(BusinessException):
    def __init__(self, message: str = "코딩테스트 문제 이미지가 아닙니다."):
        super().__init__(errorCode="OCR_422", message=message)

# 422 : 문제 텍스트 자체가 논리적으로 유효하지 않음 (Stage 0)
class InvalidProblemContentException(BusinessException):
    def __init__(self, message: str = "문제 내용이 논리적으로 유효하지 않거나 충분하지 않습니다."):
        super().__init__(errorCode="WORKBOOK_INVALID_CONTENT", message=message)

# 500 : 요약카드/퀴즈 생성 실패 (Stage 1 - API 호출, 파싱, 구조 검증)
class SummaryGenerationException(BusinessException):
    def __init__(self, message: str = "요약카드 및 퀴즈 생성에 실패했습니다."):
        super().__init__(errorCode="WORKBOOK_GENERATION_FAILED", message=message)

# 422 : 생성된 콘텐츠가 검수를 통과하지 못함 (Stage 2)
class ContentVerificationException(BusinessException):
    def __init__(self, message: str = "생성된 요약카드 및 퀴즈가 기술 검수를 통과하지 못했습니다."):
        super().__init__(errorCode="WORKBOOK_VERIFICATION_FAILED", message=message)
