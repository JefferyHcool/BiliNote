import os

from app.transcriber.whisper import WhisperTranscriber
from app.transcriber.bcut import BcutTranscriber
from app.transcriber.kuaishou import KuaishouTranscriber
from app.utils.logger import get_logger
logger = get_logger(__name__)

logger.info('初始化转录服务提供器')

# 维护各种转录器的单例实例
_transcribers = {
    'whisper': None,
    'bcut': None,
    'kuaishou': None
}

def get_whisper_transcriber(model_size="base", device="cuda"):
    """获取 Whisper 转录器实例"""
    if _transcribers['whisper'] is None:
        logger.info(f'创建 Whisper 转录器实例，参数：{model_size}, {device}')
        try:
            _transcribers['whisper'] = WhisperTranscriber(model_size=model_size, device=device)
            logger.info('Whisper 转录器创建成功')
        except Exception as e:
            logger.error(f"Whisper 转录器创建失败: {e}")
            raise
    return _transcribers['whisper']

def get_bcut_transcriber():
    """获取 Bcut 转录器实例"""
    if _transcribers['bcut'] is None:
        logger.info('创建 Bcut 转录器实例')
        try:
            _transcribers['bcut'] = BcutTranscriber()
            logger.info('Bcut 转录器创建成功')
        except Exception as e:
            logger.error(f"Bcut 转录器创建失败: {e}")
            raise
    return _transcribers['bcut']

def get_kuaishou_transcriber():
    """获取快手转录器实例"""
    if _transcribers['kuaishou'] is None:
        logger.info('创建快手转录器实例')
        try:
            _transcribers['kuaishou'] = KuaishouTranscriber()
            logger.info('快手转录器创建成功')
        except Exception as e:
            logger.error(f"快手转录器创建失败: {e}")
            raise
    return _transcribers['kuaishou']

def get_transcriber(transcriber_type="fast-whisper", model_size="base", device="cuda"):
    """
    获取指定类型的转录器实例
    
    参数:
        transcriber_type: 转录器类型，支持 "fast-whisper", "bcut", "kuaishou"
        model_size: 模型大小，whisper 特有参数
        device: 设备类型，whisper 特有参数
    
    返回:
        对应类型的转录器实例
    """
    logger.info(f'获取转录器，类型: {transcriber_type}')
    if transcriber_type == "fast-whisper":
        whisper_model_size = os.environ.get("WHISPER_MODEL_SIZE",model_size)
        return get_whisper_transcriber(whisper_model_size, device=device)
    elif transcriber_type == "bcut":
        return get_bcut_transcriber()
    elif transcriber_type == "kuaishou":
        return get_kuaishou_transcriber()
    else:
        logger.warning(f'未知转录器类型 "{transcriber_type}"，使用默认 whisper')
        whisper_model_size = os.environ.get("WHISPER_MODEL_SIZE",model_size)
        return get_whisper_transcriber(whisper_model_size, device)