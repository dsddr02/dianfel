import logging
import logging.config
import os
import sys
import time
import json
from datetime import datetime, timedelta
from const import *
from data_fetcher import DataFetcher

# 全局配置变量
CONFIG = {}
RETRY_TIMES_LIMIT = 5
LOGGER_INITIALIZED = False  # 添加标志位，确保日志只初始化一次

def load_config():
    """加载配置文件"""
    global CONFIG, RETRY_TIMES_LIMIT
    
    try:
        CONFIG = {
            "PHONE_NUMBER": os.getenv("PHONE_NUMBER"),
            "PASSWORD": os.getenv("PASSWORD"),
            "HASS_URL": os.getenv("HASS_URL"),
            "JOB_START_TIME": os.getenv("JOB_START_TIME", "07:00"),
            "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
            "VERSION": os.getenv("VERSION"),
            "HASS_TOKEN": os.getenv("HASS_TOKEN", ""),
            "ENABLE_DATABASE_STORAGE": os.getenv("ENABLE_DATABASE_STORAGE", "false").lower(),
            "IGNORE_USER_ID": os.getenv("IGNORE_USER_ID", "xxxxx,xxxxx"),
            "DB_NAME": os.getenv("DB_NAME", "homeassistant.db"),
            "DRIVER_IMPLICITY_WAIT_TIME": os.getenv("DRIVER_IMPLICITY_WAIT_TIME", "60"),
            "LOGIN_EXPECTED_TIME": os.getenv("LOGIN_EXPECTED_TIME", "10"),
            "RETRY_WAIT_TIME_OFFSET_UNIT": os.getenv("RETRY_WAIT_TIME_OFFSET_UNIT", "10"),
            "DATA_RETENTION_DAYS": os.getenv("DATA_RETENTION_DAYS", "7"),
            "RECHARGE_NOTIFY": os.getenv("RECHARGE_NOTIFY", "false").lower(),
            "BALANCE": os.getenv("BALANCE", "5.0"),
            "PUSHPLUS_TOKEN": os.getenv("PUSHPLUS_TOKEN", "")
        }
        RETRY_TIMES_LIMIT = int(os.getenv("RETRY_TIMES_LIMIT", 5))
        logging.info("配置加载成功")
        return True
    except Exception as e:
        logging.error(f"配置加载失败: {e}")
        return False

def should_run_now():
    """检查当前是否应该运行任务"""
    if not CONFIG:
        return False
    
    # 获取当前时间
    now = datetime.now()
    
    # 解析配置中的执行时间
    try:
        job_time = datetime.strptime(CONFIG["JOB_START_TIME"], "%H:%M").time()
    except ValueError:
        logging.error("JOB_START_TIME 格式错误，应为 HH:MM")
        return False
    
    # 计算今天的执行时间
    scheduled_time = datetime.combine(now.date(), job_time)
    
    # 检查当前时间是否在计划时间的5分钟内
    time_diff = abs((now - scheduled_time).total_seconds())
    return time_diff < 300  # 5分钟窗口期

def run_task():
    """执行数据获取任务"""
    driver = None
    try:
        fetcher = DataFetcher(CONFIG["PHONE_NUMBER"], CONFIG["PASSWORD"])
        driver = fetcher._get_webdriver()
        fetcher.driver = driver
        
        for retry_times in range(1, RETRY_TIMES_LIMIT + 1):
            try:
                fetcher.fetch()
                return True
            except Exception as e:
                logging.error(f"任务执行失败: {e}, 剩余重试次数: {RETRY_TIMES_LIMIT - retry_times}")
                time.sleep(60)  # 重试前等待1分钟
    except Exception as e:
        logging.error(f"任务初始化失败: {e}")
        return False
    finally:
        if driver:
            driver.quit()
    return False

def logger_init(level: str):
    """初始化日志配置"""
    global LOGGER_INITIALIZED
    
    # 确保日志只初始化一次
    if LOGGER_INITIALIZED:
        # 只更新日志级别
        logging.getLogger().setLevel(level)
        return
        
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # 清除所有现有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)
    format = logging.Formatter("%(asctime)s  [%(levelname)-8s] ---- %(message)s", "%Y-%m-%d %H:%M:%S")
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setFormatter(format)
    logger.addHandler(sh)
    
    LOGGER_INITIALIZED = True

def main():
    """主函数"""
    # 初始化日志
    logger_init("INFO")
    
    # 加载配置
    if not load_config():
        logging.error("程序启动失败，无法加载配置")
        return 1  # 非 0 表示失败
    
    # 设置日志级别
    logging.getLogger().setLevel(CONFIG.get("LOG_LEVEL", "INFO"))
    
    # 记录版本信息
    version = CONFIG.get("VERSION", "未知")
    logging.info(f"当前版本: {version}")
    logging.info("开始执行任务")
    
    success = run_task()
    if success:
        logging.info("任务执行完成")
        return 0
    else:
        logging.error("任务执行失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
