import logging
import logging.config
import os
import sys
import time
import json
import random
from datetime import datetime, timedelta
from const import *
from data_fetcher import DataFetcher

# 全局配置变量
CONFIG = {}
RETRY_TIMES_LIMIT = 5

def load_config():
    """加载配置文件"""
    global CONFIG, RETRY_TIMES_LIMIT
    
    if 'PYTHON_IN_DOCKER' not in os.environ: 
        # 读取 .env 文件
        import dotenv
        dotenv.load_dotenv(verbose=True)
    
    if os.path.isfile('/data/options.json'):
        with open('/data/options.json') as f:
            options = json.load(f)
        try:
            CONFIG = {
                "PHONE_NUMBER": options.get("PHONE_NUMBER"),
                "PASSWORD": options.get("PASSWORD"),
                "HASS_URL": options.get("HASS_URL"),
                "JOB_START_TIME": options.get("JOB_START_TIME", "07:00"),
                "LOG_LEVEL": options.get("LOG_LEVEL", "INFO"),
                "VERSION": os.getenv("VERSION"),
                "HASS_TOKEN": options.get("HASS_TOKEN", ""),
                "ENABLE_DATABASE_STORAGE": str(options.get("ENABLE_DATABASE_STORAGE", "false")).lower(),
                "IGNORE_USER_ID": options.get("IGNORE_USER_ID", "xxxxx,xxxxx"),
                "DB_NAME": options.get("DB_NAME", "homeassistant.db"),
                "DRIVER_IMPLICITY_WAIT_TIME": str(options.get("DRIVER_IMPLICITY_WAIT_TIME", 60)),
                "LOGIN_EXPECTED_TIME": str(options.get("LOGIN_EXPECTED_TIME", 10)),
                "RETRY_WAIT_TIME_OFFSET_UNIT": str(options.get("RETRY_WAIT_TIME_OFFSET_UNIT", 10)),
                "DATA_RETENTION_DAYS": str(options.get("DATA_RETENTION_DAYS", 7)),
                "RECHARGE_NOTIFY": str(options.get("RECHARGE_NOTIFY", "false")).lower(),
                "BALANCE": str(options.get("BALANCE", 5.0)),
                "PUSHPLUS_TOKEN": options.get("PUSHPLUS_TOKEN", "")
            }
            RETRY_TIMES_LIMIT = int(options.get("RETRY_TIMES_LIMIT", 5))
            logging.info("当前以Homeassistant Add-on 形式运行.")
        except Exception as e:
            logging.error(f"读取 options.json 文件失败: {e}")
            return False
    else:
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
            logging.info("当前以 Docker 镜像形式运行.")
        except Exception as e:
            logging.error(f"读取环境变量失败: {e}")
            return False
    
    # 设置环境变量
    for key, value in CONFIG.items():
        if key not in ["PHONE_NUMBER", "PASSWORD", "JOB_START_TIME", "LOG_LEVEL", "VERSION"]:
            os.environ[key] = value
    
    os.environ["RETRY_TIMES_LIMIT"] = str(RETRY_TIMES_LIMIT)
    
    return True

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
    
    # 添加随机延迟（-10分钟到+10分钟）
    random_delay_minutes = random.randint(-10, 10)
    scheduled_time = (datetime.combine(now.date(), job_time) + 
                     timedelta(minutes=random_delay_minutes))
    
    # 如果计划时间已经过去，则推迟到第二天
    if scheduled_time < now:
        scheduled_time += timedelta(days=1)
    
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
    logger = logging.getLogger()
    logger.setLevel(level)
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)
    format = logging.Formatter("%(asctime)s  [%(levelname)-8s] ---- %(message)s", "%Y-%m-%d %H:%M:%S")
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setFormatter(format)
    logger.addHandler(sh)

def main():
    """主函数"""
    # 初始化日志（使用默认级别，稍后可能会被配置覆盖）
    logger_init("INFO")
    
    logging.info("程序启动，等待执行时间...")
    
    while True:
        try:
            # 检查是否到达执行时间
            if should_run_now():
                logging.info("检测到执行时间，开始加载配置...")
                
                # 加载配置
                if not load_config():
                    logging.error("配置加载失败，等待下一次执行时间")
                    time.sleep(300)  # 等待5分钟后重试
                    continue
                
                # 重新配置日志级别
                logger_init(CONFIG.get("LOG_LEVEL", "INFO"))
                
                # 记录版本信息
                version = CONFIG.get("VERSION", "未知")
                logging.info(f"当前版本: {version}, 仓库地址: https://github.com/ARC-MX/sgcc_electricity_new.git")
                logging.info(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logging.info(f"用户名: {CONFIG['PHONE_NUMBER']}, 执行时间: {CONFIG['JOB_START_TIME']}")
                
                # 执行任务
                run_task()
                
                logging.info("任务执行完成，等待下一次执行时间")
                
                # 任务完成后等待23小时，避免频繁检查
                time.sleep(23 * 3600)
            else:
                # 未到执行时间，等待5分钟后再检查
                time.sleep(300)
        except KeyboardInterrupt:
            logging.info("程序被用户中断")
            break
        except Exception as e:
            logging.error(f"程序执行异常: {e}")
            time.sleep(300)  # 发生异常后等待5分钟再继续

if __name__ == "__main__":
    main()