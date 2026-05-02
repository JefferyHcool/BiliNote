from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.exceptions.provider import ProviderError
from app.models.model_config import ModelConfig
from app.services.model import ModelService
from app.utils.response import ResponseWrapper as R
from app.services.provider import ProviderService

router = APIRouter()

#  新增 type 字段
class ProviderRequest(BaseModel):
    name: str
    api_key: str
    base_url: str
    logo: Optional[str] = None
    type: str

class TestRequest(BaseModel):
    id: str
class ProviderUpdateRequest(BaseModel):
    id: str
    name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    logo: Optional[str] = None
    type: Optional[str] = None
    enabled:Optional[int] = None

@router.post("/add_provider")
def add_provider(data: ProviderRequest):
    try:
        res = ProviderService.add_provider(
            name=data.name,
            api_key=data.api_key,
            base_url=data.base_url,
            logo=data.logo,
            type_=data.type
        )
        return R.success(msg='添加模型供应商成功',data=res)
    except Exception as e:
        return R.error(msg=e)

@router.get("/get_all_providers")
def get_all_providers():
    try:
        res = ProviderService.get_all_providers_safe()
        return R.success(data=res)
    except Exception as e:
        return R.error(msg=e)

@router.get("/get_provider_by_id/{id}")
def get_provider_by_id(id: str):
    try:
        res = ProviderService.get_provider_by_id_safe(id)
        return R.success(data=res)
    except Exception as e:
        return R.error(msg=e)
#
# @router.get("/get_provider_by_name/{name}")
# def get_provider_by_name(name: str):
#     try:
#         res = ProviderService.get_provider_by_name(name)
#         return R.success(data=res)
#     except Exception as e:
#         return R.error(msg=e)


@router.post("/update_provider")
def update_provider(data: ProviderUpdateRequest):
    try:
        if all(
            field is None
            for field in [data.name, data.api_key, data.base_url, data.logo, data.type,data.enabled]
        ):
            return R.error(msg='请至少填写一个参数')

        updated_provider =ProviderService.update_provider(
            id=data.id,
            data=dict(data)
        )
        if updated_provider:
            return R.success(msg='更新模型供应商成功', data=updated_provider)
        else:
            return R.error(msg='更新模型供应商失败')
    except Exception as e:
        print(e)
        return R.error(msg=str(e))

@router.post('/connect_test')
def gpt_connect_test(data: TestRequest):
    ModelService().connect_test(data.id)
    return R.success(msg='连接成功')
