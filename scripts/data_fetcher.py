import logging
import os
import re
import subprocess
import time

import random
import base64
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import WebDriverException, TimeoutException
from sensor_updator import SensorUpdator

from const import *

import platform
from io import BytesIO
from PIL import Image
from onnx import ONNX


def base64_to_PIL(base64_str: str):
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

        # 删除数据库相关配置
        # self.enable_database_storage 已移除
        self.DRIVER_IMPLICITY_WAIT_TIME = int(os.getenv("DRIVER_IMPLICITY_WAIT_TIME", 60))
        self.RETRY_TIMES_LIMIT = int(os.getenv("RETRY_TIMES_LIMIT", 5))
        self.LOGIN_EXPECTED_TIME = int(os.getenv("LOGIN_EXPECTED_TIME", 10))
        self.RETRY_WAIT_TIME_OFFSET_UNIT = int(os.getenv("RETRY_WAIT_TIME_OFFSET_UNIT", 10))
        self.IGNORE_USER_ID = os.getenv("IGNORE_USER_ID", "xxxxx,xxxxx").split(",")

    def _click_button(self, driver, button_search_type, button_search_key):
        '''wrapped click function, click only when the element is clickable'''
        click_element = driver.find_element(button_search_type, button_search_key)
        WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.element_to_be_clickable(click_element))
        driver.execute_script("arguments[0].click();", click_element)

    def _is_captcha_legal(self, captcha):
        ''' check the ddddocr result, justify whether it's legal'''
        if len(captcha) != 4:
            return False
        for s in captcha:
            if not s.isalpha() and not s.isdigit():
                return False
        return True

    def _get_chromium_version(self):
        result = str(subprocess.check_output(["chromium", "--product-version"]))
        version = re.findall(r"(\d*)\.", result)[0]
        logging.info(f"chromium-driver version is {version}")
        return int(version)

    def _sliding_track(self, driver, distance):
        """机器模拟人工滑动轨迹"""
        slider = driver.find_element(By.CLASS_NAME, "slide-verify-slider-mask-item")
        ActionChains(driver).click_and_hold(slider).perform()
        yoffset_random = random.uniform(-2, 4)
        ActionChains(driver).move_by_offset(xoffset=distance, yoffset=yoffset_random).perform()
        ActionChains(driver).release().perform()

    def _get_webdriver(self):
        """Initialize a robust Chrome WebDriver for Docker environment."""
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--incognito")

        try:
            driver = uc.Chrome(
                driver_executable_path="/usr/bin/chromedriver",
                options=chrome_options,
                version_main=self._chromium_version
            )
        except Exception as e:
            logging.warning(f"Failed to start uc.Chrome with version {self._chromium_version}, fallback to default: {e}")
            driver = uc.Chrome(
                driver_executable_path="/usr/bin/chromedriver",
                options=chrome_options
            )

        driver.set_page_load_timeout(120)
        driver.set_script_timeout(120)
        driver.implicitly_wait(self.DRIVER_IMPLICITY_WAIT_TIME)
        logging.info("Chrome WebDriver initialized successfully (Docker-safe mode).")
        return driver

    def _login(self, driver, phone_code=False):
        driver.get(LOGIN_URL)
        logging.info(f"Open LOGIN_URL:{LOGIN_URL}.\r")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

        driver.find_element(By.CLASS_NAME, "user").click()
        logging.info("find_element 'user'.\r")
        self._click_button(driver, By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[2]/span')
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

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
            self._click_button(driver, By.XPATH, '//*[@id="login_box"]/div[2]/div[2]/form/div[2]/div/button/span')
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT * 2)
            logging.info("Click login button.\r")
            return True
        else:
            input_elements = driver.find_elements(By.CLASS_NAME, "el-input__inner")
            input_elements[0].send_keys(self._username)
            logging.info(f"input_elements username\r")
            input_elements[1].send_keys(self._password)
            logging.info(f"input_elements password\r")

            self._click_button(driver, By.CLASS_NAME, "el-button.el-button--primary")
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT * 2)
            logging.info("Click login button.\r")

            for retry_times in range(1, self.RETRY_TIMES_LIMIT + 1):
                self._click_button(driver, By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[2]/span')

                background_JS = 'return document.getElementById("slideVerify").childNodes[0].toDataURL("image/png");'
                im_info = driver.execute_script(background_JS)
                background = im_info.split(',')[1]
                background_image = base64_to_PIL(background)
                logging.info(f"Get electricity canvas image successfully.\r")

                distance = self.onnx.get_distance(background_image)
                logging.info(f"Image CaptCHA distance is {distance}.\r")

                self._sliding_track(driver, round(distance * 1.06))
                time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

                if driver.current_url == LOGIN_URL:
                    try:
                        logging.info(f"Sliding CAPTCHA recognition failed and reloaded.\r")
                        self._click_button(driver, By.CLASS_NAME, "el-button.el-button--primary")
                        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT * 2)
                        continue
                    except:
                        logging.debug(
                            f"Login failed, maybe caused by invalid captcha, {self.RETRY_TIMES_LIMIT - retry_times} retry times left.")
                else:
                    return True

            logging.error(f"Login failed, maybe caused by Sliding CAPTCHA recognition failed")
            raise Exception(
                "Login failed, maybe caused by 1.incorrect phone_number and password, please double check. or 2. network, please modify LOGIN_EXPECTED_TIME in .env and run docker compose up --build.")

    def fetch(self):
        """Main logic for fetching data, with fault tolerance for Docker."""
        driver = None
        try:
            if platform.system() == 'Windows':
                driverfile_path = r'C:\Users\mxwang\Project\msedgedriver.exe'
                driver = webdriver.Edge(executable_path=driverfile_path)
            else:
                driver = self._get_webdriver()

            driver.maximize_window()
            logging.info("WebDriver initialized.")
            updator = SensorUpdator()

            debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
            if not self._login(driver, phone_code=debug_mode):
                raise Exception("Login failed")

            logging.info(f"Login successful on {LOGIN_URL}")
            user_id_list = self._get_user_ids(driver)
            logging.info(f"Fetched {len(user_id_list)} user IDs, ignoring {self.IGNORE_USER_ID}.")

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

                    balance = self._get_balance(driver)
                    if balance is None:
                        logging.warning(f"Balance fetch failed for {user_id}, skipping.")
                        continue

                    # 仅通过 SensorUpdator 更新（如 Home Assistant），不再本地存储
                    updator.update_one_userid(user_id, balance)

                    logging.info(f"Data fetched and updated for user {user_id}.")
                    time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

                except WebDriverException as e:
                    logging.error(f"WebDriver error while processing user {user_id}: {e}")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    logging.info("Restarting Chrome WebDriver due to crash...")
                    driver = self._get_webdriver()
                    continue

                except Exception as e:
                    logging.warning(f"Failed to fetch data for user {user_id}: {e}")
                    continue

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
        current_userid = driver.find_element(
            By.XPATH,
            '//*[@id="app"]/div/div/article/div/div/div[2]/div/div/div[1]/div[2]/div/div/div/div[2]/div/div[1]/div/ul/div/li[1]/span[2]'
        ).text
        return current_userid

    def _choose_current_userid(self, driver, userid_index):
        elements = driver.find_elements(By.CLASS_NAME, "button_confirm")
        if elements:
            self._click_button(driver, By.XPATH,
                               '''//*[@id="app"]/div/div[2]/div/div/div/div[2]/div[2]/div/button''')
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        self._click_button(driver, By.CLASS_NAME, "el-input__suffix")
        time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
        self._click_button(driver, By.XPATH, f"/html/body/div[2]/div[1]/div[{userid_index + 1}]/ul/li/span")

    def _get_balance(self, driver):
        try:
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            for attempt in range(3):
                try:
                    balance = self._get_electric_balance(driver)
                    if balance is not None:
                        return balance
                    else:
                        logging.warning(f"Balance is None, retrying... {attempt + 1}/3")
                        time.sleep(2)
                except Exception as e:
                    logging.warning(f"Attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        time.sleep(2)
                        continue
                    else:
                        raise e
            return None

        except Exception as e:
            logging.error(f"Failed to get balance after all retries: {e}")
            return None

    def _get_electric_balance(self, driver):
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "num"))
            )
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "amttxt"))
            )

            balance_element = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CLASS_NAME, "num"))
            )
            balance_text_element = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CLASS_NAME, "amttxt"))
            )

            balance = balance_element.text.strip()
            balance_text = balance_text_element.text.strip()

            logging.info(f"Raw balance text: '{balance}', status text: '{balance_text}'")

            if not balance:
                logging.warning("Balance text is empty")
                return None

            balance_clean = re.sub(r'[^\d.]', '', balance)
            if not balance_clean:
                logging.warning(f"Could not extract numeric value from balance: '{balance}'")
                return None

            balance_value = float(balance_clean)

            if "欠费" in balance_text:
                return -balance_value
            else:
                return balance_value

        except TimeoutException:
            logging.error("Timeout while waiting for balance elements")
            return None
        except ValueError as e:
            logging.error(f"Value error parsing balance: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error in _get_electric_balance: {e}")
            return None

    def _get_user_ids(self, driver):
        try:
            driver.refresh()
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT * 2)
            element = WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'el-dropdown'))
            )
            self._click_button(driver, By.XPATH, "//div[@class='el-dropdown']/span")
            logging.debug(f'''self._click_button(driver, By.XPATH, "//div[@class='el-dropdown']/span")''')
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

            target = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_element(By.TAG_NAME, "li")
            logging.debug(f'''target = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_element(By.TAG_NAME, "li")''')
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)
            logging.debug(f'''WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))''')

            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.text_to_be_present_in_element((By.XPATH, "//ul[@class='el-dropdown-menu el-popper']/li"), ":")
            )
            time.sleep(self.RETRY_WAIT_TIME_OFFSET_UNIT)

            userid_elements = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_elements(By.TAG_NAME, "li")
            userid_list = []
            for element in userid_elements:
                userid_list.append(re.findall("[0-9]+", element.text)[-1])
            return userid_list

        except Exception as e:
            logging.error(
                f"Webdriver quit abnormally, reason: {e}. get user_id list failed.")
            try:
                driver.quit()
            except:
                pass
            return []


# 测试用，可删除
if __name__ == "__main__":
    with open("bg.jpg", "rb") as f:
        test1 = f.read()
        print(type(test1))
        print(test1)
