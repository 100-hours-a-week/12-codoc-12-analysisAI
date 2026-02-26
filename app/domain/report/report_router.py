from fastapi import APIRouter

from app.common.api_response import CommonResponse
from app.domain.report.report_schemas import ReportRequest, ReportResponseData
from app.domain.report.report_service import report_service

router = APIRouter()

@router.post("", response_model=CommonResponse[ReportResponseData])
async def genearte_report(request: ReportRequest):
    data = await report_service.generate_report(request)
    return CommonResponse.success_response(message="OK", data=data)

