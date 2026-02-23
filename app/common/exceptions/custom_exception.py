from app.common.exceptions.base_exception import BusinessException


# 401: 인증 실패 (토큰 없음, 만료 등)
class CredentialException(BusinessException):
    def __init__(self, message: str = "자격 증명을 검증할 수 없습니다."):
        super().__init__(errorCode="AUTH_401", message=message)


# 403: 권한 없음 (관리자만 접근 가능 등)
class UnauthorizedException(BusinessException):
    def __init__(self, message: str = "해당 권한을 가진 사용자가 아닙니다."):
        super().__init__(errorCode="AUTH_403", message=message)


class InvalidStarterConditionException(BusinessException):
    def __init__(
        self, message: str = "NEW 시나리오는 solved < 5 조건에서만 사용 가능"
    ):
        super().__init__(errorCode="RECOMMEND_400", message=message)


class RecommendationNotFoundException(BusinessException):
    def __init__(self, message: str = "추천 결과가 없습니다."):
        super().__init__(errorCode="RECOMMEND_404", message=message)
