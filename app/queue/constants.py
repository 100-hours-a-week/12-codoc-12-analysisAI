RECOMMEND_REQUEST_QUEUE = "recommend.request.q"
RECOMMEND_RESPONSE_QUEUE = "recommend.response.q"
REPORT_REQUEST_QUEUE = "report.request.q"
REPORT_RESPONSE_QUEUE = "report.response.q"

OCR_REQUEST_QUEUE = "custom.problem.request"
OCR_EXCHANGE = "custom.problem.exchange"
OCR_RESPONSE_ROUTING_KEY = "custom.problem.response"

ALL_QUEUE_NAMES = [
    RECOMMEND_REQUEST_QUEUE,
    RECOMMEND_RESPONSE_QUEUE,
    REPORT_REQUEST_QUEUE,
    REPORT_RESPONSE_QUEUE,
    OCR_REQUEST_QUEUE
]