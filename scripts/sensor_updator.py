import logging
import os
from datetime import datetime

import requests
from sympy import true

from const import *


class SensorUpdator:

    def __init__(self):
        HASS_URL = os.getenv("HASS_URL")
        HASS_TOKEN = os.getenv("HASS_TOKEN")
        self.base_url = HASS_URL[:-1] if HASS_URL.endswith("/") else HASS_URL
        self.token = HASS_TOKEN
        self.RECHARGE_NOTIFY = os.getenv("RECHARGE_NOTIFY", "false").lower() == "true"

    def update_one_userid(self, user_id: str, balance: float):
        postfix = f"_{user_id[-4:]}"
        if balance is not None:
            self.balance_notify(user_id, balance)

        logging.info(f"User state-refresh task run successfully!")


    def balance_notify(self, user_id, balance):

        if self.RECHARGE_NOTIFY :  # 这一行后面的代码块需要缩进
           BALANCE = float(os.getenv("BALANCE", 10.0))
           PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN").split(",")
           TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
           TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
           TELEGRAM_API_DOMAINS = os.getenv("TELEGRAM_API_DOMAINS", "").split(",")  # Use comma-separated list from env, empty string as default
           TELEGRAM_API_DOMAINS = [domain for domain in TELEGRAM_API_DOMAINS if domain] # Remove empty strings from list


           logging.info(f"Check the electricity bill balance. When the balance is less than {BALANCE} CNY, the notification will be sent = {self.RECHARGE_NOTIFY}")
           if balance < BALANCE : # 这一行后面的代码块需要缩进
               # Pushplus Notification
               if PUSHPLUS_TOKEN:  # Check if PUSHPLUS_TOKEN is defined
                   for token in PUSHPLUS_TOKEN: # 这一行后面的代码块需要缩进
                       title = "余额提醒"
                       content = (f"您的当前余额为：{balance}元，请及时充值。" )
                       url = ("http://www.pushplus.plus/send?token="+ token+ "&title="+ content+ "&content="+ content)
                       try:
                           requests.get(url)
                           logging.info(
                               f"The current balance of user is {balance} CNY less than {BALANCE} CNY, Pushplus notification has been sent, please pay attention to check and recharge."
                           )
                       except requests.exceptions.RequestException as e:
                           logging.error(f"Error sending Pushplus notification: {e}")

                # Telegram Notification
               if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID: # 这一行后面的代码块需要缩进
                   telegram_message = f"余额提醒：您的当前余额为：{balance}元，请及时充值。"
                   telegram_data = {
                       "chat_id": TELEGRAM_CHAT_ID,
                       "text": telegram_message
                   }
                   
                   for domain in TELEGRAM_API_DOMAINS:
                       telegram_api_url = f"https://{domain}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                       try:
                           response = requests.post(telegram_api_url, json=telegram_data, timeout=10) # Added timeout
                           response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                           logging.info(f"Telegram notification sent successfully via {domain}. Response: {response.text}")
                           break  # If successful, exit the loop
                       except requests.exceptions.RequestException as e:
                           logging.error(f"Error sending Telegram notification via {domain}: {e}")
                   else:
                       logging.error("Failed to send Telegram notification via all domains.")


           else: # 这一行后面的代码块需要缩进
               logging.info("Balance is sufficient, no notification sent.")
        else : # 这一行后面的代码块需要缩进
           logging.info(
           f"Check the electricity bill balance, the notification will be sent = {self.RECHARGE_NOTIFY}")
           return