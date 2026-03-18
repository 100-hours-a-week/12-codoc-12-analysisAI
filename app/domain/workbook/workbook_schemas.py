from pydantic import BaseModel, HttpUrl, ConfigDict, field_validator
from pydantic.alias_generators import to_camel

class Images(BaseModel):
    order : int
    url: HttpUrl      

class ImageSubmitReq(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    images: list[Images]
    
    @field_validator("images")
    def validate_images(cls, v):
        orders = [img.order for img in v]
        if len(orders) != len(set(orders)):
            raise ValueError("order 값이 중복됩니다.")
        
        return sorted(v, key=lambda x: x.order)
    
class ImageSubmitRes(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    recognized_text: str
    
    