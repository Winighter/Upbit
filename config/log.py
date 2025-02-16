import logging

class Log:
    def __init__(self, msg:str):

        # 로거 세팅
        logger = logging.getLogger("postprocessor")
        logger.setLevel(logging.DEBUG)

        # 일반 핸들러, 포매터 세팅
        formatter = logging.Formatter("%(asctime)s %(levelname)s:%(message)s")
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)

        # # 크리티컬 이벤트에 대한 핸들러, 포매터 세팅
        formatter_critical = logging.Formatter("%(asctime)s %(levelname)s:%(message)s")
        handler_critical = logging.FileHandler("config/logs/log_event.log")
        handler_critical.setLevel(logging.CRITICAL)
        handler_critical.setFormatter(formatter_critical)

        # 각 핸들러를 로거에 추가
        logger.addHandler(handler)
        logger.addHandler(handler_critical)

        logger.critical(msg)