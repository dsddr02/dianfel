import logging
import os
import re
import subprocess
import time

import random
import base64
import sqlite3
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import WebDriverException
from sensor_updator import SensorUpdator

from const import *

import platform
from io import BytesIO
from PIL import Image
from onnx import ONNX


def base64_to_PLI(base64_str: str):
    base64_data = re.sub('^data:image/.+;base64,', '', base64_str)
    byte_data = base64.b64decode(base64_data)
    image_data = BytesIO(byte_data)
    img = Image.open(image_data)
    return img

class DataFetcher:

    def __init__(self, username: str, password: str):
        if 'PYTHON_IN_DOCKER' not in os.environ: 
            import dotenv
            dotenv.load_dotenv(verbose=True)
        self._username = username
        self._password = password
        self.onnx = ONNX("./captcha.onnx")
        if platform.system() == 'Windows':
            pass
        else:
            self._chromium_version = self._get_chromium_version()

        # 获取 ENABLE_DATABASE_STORAGE 的值，默认为 False
        self.enable_database_storage = os.getenv("ENABLE_DATABASE_STORAGE", "false").lower() == "true"
        self.DRIVER_IMPLICITY_WAIT_TIME = int(os.getenv("DRIVER_IMPLICITY_WAIT_TIME", 60))
        self.RETRY_TIMES_LIMIT = int(os.getenv("RETRY_TIMES_LIMIT", 5))
        self.LOGIN_EXPECTED_TIME = int(os.getenv("LOGIN_EXPECTED_TIME", 10))
        self.RETRY_WAIT_TIME_OFFSET_UNIT = int(os.getenv("RETRY_WAIT_TIME_OFFSET_UNIT", 10))
        self.IGNORE_USER_ID = os.getenv("IGNORE_USER_ID", "xxxxx,xxxxx").split(",")

    # @staticmethod
    def _click_button(self, driver, button_search_type, button_search_key):
        '''wrapped click function, click only when the element is clickable'''
        click_element = driver.find_element(button_search_type, button_search_key)
        # logging.info(f"click_element:{button_search_key}.is_displayed() = {click_element.is_displayed()}\r")
        # logging.info(f"click_element:{button_search_key}.is_enabled() = {click_element.is_enabled()}\r")
        WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.element_to_be_clickable(click_element))
        driver.execute_script("arguments[0].click();", click_element)

    # @staticmethod
    def _is_captcha_legal(self, captcha):
        ''' check the ddddocr result, justify whether it's legal'''
        if (len(captcha) != 4):
            return False
        for s in captcha:
            if (not s.isalpha() and not s.isdigit()):
                return False
        return True

    # @staticmethod
    def _get_chromium_version(self):
        result = str(subprocess.check_output(["chromium", "--product-version"]))
        version = re.findall(r"(\d*)\.", result)[0]
        logging.info(f"chromium-driver version is {version}")
        return int(version)

    # @staticmethod 
    def _sliding_track(self, driver, distance):# 机器模拟人工滑动轨迹
        # 获取按钮
        slider = driver.find_element(By.CLASS_NAME, "slide-verify-slider-mask-item")
        ActionChains(driver).click_and_hold(slider).perform()
        # 获取轨迹
        # tracks = _get_tracks(distance)
        # for t in tracks:
        yoffset_random = random.uniform(-2, 4)
        ActionChains(driver).move_by_offset(xoffset=distance, yoffset=yoffset_random).perform()
            # time.sleep(0.2)
        ActionChains(driver).release().perform()

    def connect_user_db(self, user_id):
        """创建数据库集合，db_name = electricity_daily_usage_{user_id}
        :param user_id: 用户ID"""
        try:
            # 创建数据库
            DB_NAME = os.getenv("DB_NAME", "homeassistant.db")
            if 'PYTHON_IN_DOCKER' in os.environ: 
                DB_NAME = "/data/" + DB_NAME
            self.connect = sqlite3.connect(DB_NAME)
            self.connect.cursor()
            logging.info(f"Database of {DB_NAME} created successfully.")
			
			# 创建data表名
            self.table_expand_name = f"data{user_id}"
            sql = f'''CREATE TABLE IF NOT EXISTS {self.table_expand_name} (
                    name TEXT PRIMARY KEY NOT NULL,
                    value TEXT NOT NULL)'''
            self.connect.execute(sql)
            logging.info(f"Table {self.table_expand_name} created successfully")
			
        # 如果表已存在，则不会创建
        except sqlite3.Error as e:
            logging.debug(f"Create db or Table error:{e}")
            return False
        return True

    def insert_expand_data(self, data:dict):
        if self.connect is None:
            logging.error("Database connection is not established.")
            return
        # 创建索引
        try:
            sql = f"INSERT OR REPLACE INTO {self.table_expand_name} VALUES('{data['name']}','{data['value']}');"
            self.connect.execute(sql)
            self.connect.commit()
        except BaseException as e:
            logging.debug(f"Data update failed: {e}")

                
    def _get_webdriver(self):
        chrome_options = Options()
        chrome_options.add_argument('--incognito')
        chrome_options.add_argument('--window-size=4000,1600')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-dev-shm-usage')
        driver = uc.Chrome(driver_executable_path="/usr/bin/chromedriver", options=chrome_options, version_main=self._chromium_version)
        driver.implicitly_wait(self.DRIVER_IMPLICITY_WAIT_TIME)
        return driver

    def _login(self, driver, phone_code = False):

        driver.get(LOGIN_URL)
        logging.info(f"Open LOGIN_URL:{LOGIN_URL}.\r")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        # swtich to username-password login page
        driver.find_element(By.CLASS_NAME, "user").click()
        logging.info("find_element 'user'.\r")
        self._click_button(driver, By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[2]/span')
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        # click agree button
        self._click_button(driver, By.XPATH, '//*[@id="login_box"]/div[2]/div[1]/form/div[1]/div[3]/div/span[2]')
        logging.info("Click the Agree option.\r")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        if phone_code:
            self._click_button(driver, By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[3]/span')
            input_elements = driver.find_elements(By.CLASS_NAME, "el-input__inner")
            input_elements[2].send_keys(self._username)
            logging.info(f"input_elements username \r")
            self._click_button(driver, By.XPATH, '//*[@id="login_box"]/div[2]/div[2]/form/div[1]/div[2]/div[2]/div/a')
            code = input("Input your phone verification code: ")
            input_elements[3].send_keys(code)
            logging.info(f"input_elements verification code: {code}.\r")
            # click login button
            self._click_button(driver, By.XPATH, '//*[@id="login_box"]/div[2]/div[2]/form/div[2]/div/button/span')
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT*2)
            logging.info("Click login button.\r")

            return True
        else :
            # input username and password
            input_elements = driver.find_elements(By.CLASS_NAME, "el-input__inner")
            input_elements[0].send_keys(self._username)
            logging.info(f"input_elements username\r")
            input_elements[1].send_keys(self._password)
            logging.info(f"input_elements password\r")

            # click login button
            self._click_button(driver, By.CLASS_NAME, "el-button.el-button--primary")
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT*2)
            logging.info("Click login button.\r")
            # sometimes ddddOCR may fail, so add retry logic)
            for retry_times in range(1, self.RETRY_TIMES_LIMIT + 1):
                
                self._click_button(driver, By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[2]/span')
                #get canvas image
                background_JS = 'return document.getElementById("slideVerify").childNodes[0].toDataURL("image/png");'
                # targe_JS = 'return document.getElementsByClassName("slide-verify-block")[0].toDataURL("image/png");'
                # get base64 image data
                im_info = driver.execute_script(background_JS) 
                background = im_info.split(',')[1]  
                background_image = base64_to_PLI(background)
                logging.info(f"Get electricity canvas image successfully.\r")
                distance = self.onnx.get_distance(background_image)
                logging.info(f"Image CaptCHA distance is {distance}.\r")

                self._sliding_track(driver, round(distance*1.06)) #1.06是补偿
                time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
                if (driver.current_url == LOGIN_URL): # if login not success
                    try:
                        logging.info(f"Sliding CAPTCHA recognition failed and reloaded.\r")
                        self._click_button(driver, By.CLASS_NAME, "el-button.el-button--primary")
                        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT*2)
                        continue
                    except:
                        logging.debug(
                            f"Login failed, maybe caused by invalid captcha, {self.RETRY_TIMES_LIMIT - retry_times} retry times left.")
                else:
                    return True
            logging.error(f"Login failed, maybe caused by Sliding CAPTCHA recognition failed")
        return False

        raise Exception(
            "Login failed, maybe caused by 1.incorrect phone_number and password, please double check. or 2. network, please mnodify LOGIN_EXPECTED_TIME in .env and run docker compose up --build.")
        
    def fetch(self):
        """Main logic for fetching data."""
        driver = None
        try:
            # Initialize WebDriver
            if platform.system() == 'Windows':
                driverfile_path = r'C:\Users\mxwang\Project\msedgedriver.exe'
                driver = webdriver.Edge(executable_path=driverfile_path)
            else:
                driver = self._get_webdriver()
            
            driver.maximize_window()
            logging.info("WebDriver initialized.")
            updator = SensorUpdator()

            # Try logging in
            try:
                debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
                if self._login(driver, phone_code=debug_mode):
                    logging.info("Login succeeded!")
                else:
                    logging.error("Login failed!")
                    raise Exception("Login failed")
            except Exception as e:
                logging.error(f"Login error: {e}. WebDriver will quit.")
                return

            logging.info(f"Login successful on {LOGIN_URL}")
            user_id_list = self._get_user_ids(driver)
            logging.info(f"Fetched {len(user_id_list)} user IDs, ignoring {self.IGNORE_USER_ID}.")
            
            # Iterate through users
            for userid_index, user_id in enumerate(user_id_list):
                try:
                    driver.get(BALANCE_URL)
                    time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
                    
                    self._choose_current_userid(driver, userid_index)
                    time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
                    
                    current_userid = self._get_current_userid(driver)
                    if current_userid in self.IGNORE_USER_ID:
                        logging.info(f"Skipping ignored user {current_userid}.")
                        continue
                    
                    # Fetch data
                    balance = self._get_balance(driver)
                    updator.update_one_userid(user_id, balance)
                    
                    logging.info(f"Data fetched successfully for user.")
                    time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
                 
                except Exception as e:
                    logging.warning(f"Failed to fetch data for user: {e}")
                    continue  # Continue to next user

            logging.info("Data fetching completed successfully.")

        except Exception as e:
            logging.error(f"Unexpected error in fetch process: {e}")

        finally:
            if driver:
                try:
                    driver.quit()
                    logging.info("WebDriver successfully quit.")
                except WebDriverException as e:
                    logging.error(f"Error while quitting WebDriver: {e}")

    def _get_current_userid(self, driver):
        current_userid = driver.find_element(By.XPATH, '//*[@id="app"]/div/div/article/div/div/div[2]/div/div/div[1]/div[2]/div/div/div/div[2]/div/div[1]/div/ul/div/li[1]/span[2]').text
        return current_userid
    
    def _choose_current_userid(self, driver, userid_index):
        elements = driver.find_elements(By.CLASS_NAME, "button_confirm")
        if elements:
            self._click_button(driver, By.XPATH, f'''//*[@id="app"]/div/div[2]/div/div/div/div[2]/div[2]/div/button''')
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        self._click_button(driver, By.CLASS_NAME, "el-input__suffix")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        self._click_button(driver, By.XPATH, f"/html/body/div[2]/div[1]/div[{userid_index+1}]/ul/li/span")

    def _get_balance(self, driver):
        try:
            driver.get(BALANCE_URL)
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            balance = self._get_electric_balance(driver)
            if (balance is None):
                logging.info(f"Get electricity charge balance for user failed, Pass.")
            else:
                logging.info(
                    f"Get electricity charge balance for user successfully, balance is {balance} CNY.")
            return balance
        except Exception as e:
            logging.error(f"Failed to get balance: {e}")
            return None

    def _get_user_ids(self, driver):
        try:
            # 刷新网页
            driver.refresh()
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT*2)
            element = WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.presence_of_element_located((By.CLASS_NAME, 'el-dropdown')))
            # click roll down button for user id
            self._click_button(driver, By.XPATH, "//div[@class='el-dropdown']/span")
            logging.debug(f'''self._click_button(driver, By.XPATH, "//div[@class='el-dropdown']/span")''')
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            # wait for roll down menu displayed
            target = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_element(By.TAG_NAME, "li")
            logging.debug(f'''target = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_element(By.TAG_NAME, "li")''')
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            logging.debug(f'''WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))''')
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.text_to_be_present_in_element((By.XPATH, "//ul[@class='el-dropdown-menu el-popper']/li"), ":"))
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

            # get user id one by one
            userid_elements = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_elements(By.TAG_NAME, "li")
            userid_list = []
            for element in userid_elements:
                userid_list.append(re.findall("[0-9]+", element.text)[-1])
            return userid_list
        except Exception as e:
            logging.error(
                f"Webdriver quit abnormly, reason: {e}. get user_id list failed.")
            driver.quit()

    def _get_electric_balance(self, driver):
        try:
            balance = driver.find_element(By.CLASS_NAME, "num").text
            balance_text = driver.find_element(By.CLASS_NAME, "amttxt").text
            if "欠费" in balance_text :
                return -float(balance)
            else:
                return float(balance)
        except:
            return None

    def _save_balance_to_db(self, user_id, balance):
        """Saves the balance to the database."""
        if self.connect_user_db(user_id):
            try:
                # 写入当前户号
                dic = {'name': 'user', 'value': f"{user_id}"}
                self.insert_expand_data(dic)
                # 写入剩余金额
                dic = {'name': 'balance', 'value': f"{balance}"}
                self.insert_expand_data(dic)
                self.connect.close()
                logging.info(f"Balance for user {user_id} saved to database.")
            except Exception as e:
                logging.error(f"Failed to save balance to database: {e}")
            finally:
                if hasattr(self, 'connect') and self.connect:
                    self.connect.close()
        else:
            logging.error("Database connection failed, balance not saved.")

if __name__ == "__main__":
    with open("bg.jpg", "rb") as f:
        test1 = f.read()
        print(type(test1))
        print(test1)
