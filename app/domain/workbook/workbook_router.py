from fastapi import APIRouter
from app.common.api_response import CommonResponse
from . import workbook_schemas
from app.domain.workbook.workbook_service import workbook_service

router = APIRouter()

@router.post("", response_model=CommonResponse[workbook_schemas.ImageSubmitReq])
async def image_recognition(post: workbook_schemas.ImageSubmitReq):
    data = await workbook_service.extract_text(post)
    
    return CommonResponse.success_response(message="이미지 인식이 완료되었습니다.", data=data)

