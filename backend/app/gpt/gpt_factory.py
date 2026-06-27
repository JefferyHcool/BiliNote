from openai import OpenAI

from app.gpt.base import GPT
from app.gpt.provider.OpenAI_compatible_provider import OpenAICompatibleProvider
from app.gpt.universal_gpt import UniversalGPT
from app.models.model_config import ModelConfig


class GPTFactory:
    @staticmethod
    def from_config(config: ModelConfig) -> GPT:
        # TwelveLabs Pegasus 视频理解后端：直接「看」视频生成笔记（可选）。
        # 仅当供应商 type == 'twelvelabs' 时路由到这里；其余供应商行为不变。
        if (config.provider or "").lower() == "twelvelabs":
            from app.gpt.twelvelabs_gpt import TwelveLabsGPT
            return TwelveLabsGPT(api_key=config.api_key, model=config.model_name or "pegasus1.5")

        client = OpenAICompatibleProvider(api_key=config.api_key, base_url=config.base_url).get_client
        return UniversalGPT(client=client, model=config.model_name)