# coding=utf-8

from logging.handlers import TimedRotatingFileHandler

import inspect

import sys

from pprint import pprint,pp

import requests

import socket

import time

import re

import os

import logging

import tkinter

from lxml import etree

import traceback

from selenium import webdriver

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import ElementNotInteractableException

from selenium.webdriver.support.ui import Select

import pandas as pd

from datetime import datetime,timedelta

import random

import json

class Config:

  def __init__(self):

    self.total_max_retry = 5

    self.total_max_exception = 5

    self.device = socket.gethostname()
    
    self.datetime_now = datetime.now()

    self.day_now = self.datetime_now.strftime("%d")


    self.name = ""

    self.at = ""



    self.lark_base_ID = ""

    self.lark_config_table_ID = ""

    self.lark_history_table_ID = ""

    self.lark_hit_table_ID = ""



    self.config_head_site_no = "网站编号"

    self.config_head_site_name = "网站名称"

    self.config_head_site_link = "网站链接"

    self.config_head_positive_words = "组合触发词"

    self.config_head_negative_words = "通用拦截词"

    self.config_head_open_date = "生效日期"

    self.config_head_close_date = "失效日期"

    self.config_head_language_type = "语言分类"


    self.history_head_site_no = "网站编号"

    self.history_head_site_name = "网站名称"

    self.history_head_news_title = "资讯标题"

    self.history_head_news_link = "资讯链接"

    self.history_head_news_date = "发布时间"

    self.history_head_log_stamp = "创建时间"

    self.history_head_push_device = "推送设备"


    self.hit_head_site_no = "网站编号"

    self.hit_head_site_name = "网站名称"

    self.hit_head_positive_words = "命中关键词"

    self.hit_head_news_title = "资讯标题"

    self.hit_head_news_link = "资讯链接"

    self.hit_head_news_content = "资讯正文"

    self.hit_head_news_date = "发布时间"

    self.hit_head_push_device = "推送设备"

    self.hit_head_log_stamp = "创建时间"



    # Simplified for testing - always use console logging
    self.log_path = None
    self.logger = self._init_logger(self.log_path)
    
    # Try to initialize browser with default paths
    try:
      # Try common Chrome paths
      chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",   # Windows
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",  # Windows 32-bit
        "/usr/bin/google-chrome",  # Linux
        "/usr/bin/chromium-browser"  # Linux Chromium
      ]
      
      driver_paths = [
        "/usr/local/bin/chromedriver",  # macOS with Homebrew
        "C:\\chromedriver\\chromedriver.exe",  # Windows
        "/usr/bin/chromedriver"  # Linux
      ]
      
      chrome_path = None
      driver_path = None
      
      for path in chrome_paths:
        if os.path.exists(path):
          chrome_path = path
          break
          
      for path in driver_paths:
        if os.path.exists(path):
          driver_path = path
          break
      
      if chrome_path and driver_path:
        self.browser_buffer_path = "/tmp"  # Use temp directory
        self.browser = self._init_browser(driver_path, chrome_path, self.browser_buffer_path)
        self.logger.debug(f"Browser initialized successfully")
      else:
        self.logger.warning(f"Chrome or ChromeDriver not found. Chrome paths checked: {chrome_paths}")
        self.logger.warning(f"Driver paths checked: {driver_paths}")
        self.browser = None
        
    except Exception as e:
      self.logger.error(f"Failed to initialize browser: {e}")
      self.browser = None



    # self._init_lark_token()

    # self._init_lark_config()
    
    # Hardcoded configuration for testing
    self.lark_config_list = [
      {
        self.config_head_site_no: 0,
        self.config_head_site_name: "Quamnet Test",
        self.config_head_site_link: "https://www.quamnet.com/channel/news/042928e4-dde9-478f-9ffb-7d58e5582b06",
        self.config_head_positive_words: ["test+news", "financial+market"],
        self.config_head_negative_words: ["spam", "advertisement"]
      }
    ]

    
  def _init_browser(self,driver_path,chrome_path,browser_buffer_path):

    service = Service(
      executable_path=driver_path
    )

    options = Options()

    options.binary_location = chrome_path

    prefs = {
        'download.default_directory': browser_buffer_path, 
        'download.prompt_for_download': False,
        'safebrowsing.enabled': False,
        'safebrowsing.disable_download_protection': True
    }

    options.add_experimental_option('prefs', prefs)
    options.add_experimental_option("detach", True)
    options.add_experimental_option('excludeSwitches', ['enable-automation','enable-logging'])

    options.add_argument('--disable-blink-features=AutomationControlled') 

    options.add_argument("--start-maximized")  
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-download-bar")

    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument("--disable-gpu")   

    options.add_argument('--headless')

    browser = webdriver.Chrome(options = options,service=service)

    return browser

  def show_message(self,text="Text on the screen",duration=1):

    duration = duration*1000

    label = tkinter.Label(text=text, font=("Times New Roman","80"), fg="brown", bg="white")
    label.master.overrideredirect(True)
    label.master.geometry("-250-250")
    label.master.lift()
    label.master.wm_attributes("-topmost", True)
    label.master.wm_attributes("-disabled", True)
    label.master.wm_attributes("-transparentcolor", "white")
    label.after(duration, label.master.destroy)
    label.pack()
    label.mainloop()

  def post_lark_log(
    self
    ,name=""
    ,at="donghegeng"
    ,anonymous_1=""
    ,anonymous_2=""
    ,anonymous_3=""
    ,anonymous_4=""
    ,anonymous_5=""
    ,anonymous_6=""
    ,anonymous_7=""
    ,anonymous_8=""
    ,anonymous_9=""
    ,anonymous_10=""
  ):
    # Simple testing version - just log
    logger = self.logger
    logger.debug(f"Lark log: {name} - {anonymous_1}")
    return

  def post_lark_notice(
    self
    ,name=""
    ,at=""
    ,message=""
  ):
    # Simple testing version - just log
    logger = self.logger
    logger.debug(f"Lark notice: {name} - {message}")
    return

  def _init_logger(self,log_file_path=None):

    dir_path,py_file_name = os.path.split(os.path.abspath(__file__))

    # log_file_name = py_file_name.replace(".py",".log")

    # log_file_path = os.path.join(dir_path,log_file_name)

    logger = logging.getLogger(py_file_name)

    logger.setLevel(logging.DEBUG)

    if not logger.handlers:

      formatter = logging.Formatter('%(levelname)s - %(asctime)s - %(filename)s - %(funcName)s - %(lineno)d - %(message)s')

      if log_file_path :

        # fileHandler = logging.FileHandler(log_file_path,encoding="utf-8",mode="a")

        fileHandler = TimedRotatingFileHandler(
            filename=log_file_path
            ,when='W0'
            ,interval=1
            ,backupCount=50
            ,encoding='utf-8'
            ,delay=False
            ,utc=False
            ,atTime=None
        )
    
        fileHandler.setLevel(logging.DEBUG)
        fileHandler.setFormatter(formatter)

        logger.addHandler(fileHandler)
      
      else :

        consoleHeader = logging.StreamHandler()
        consoleHeader.setFormatter(formatter)
        consoleHeader.setLevel(logging.DEBUG)

        logger.addHandler(consoleHeader)

    return logger

  def _init_lark_token(self):

    url = ""

    payload = {
      "app_id": "",
      "app_secret": ""
    }

    headers = {
      'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, json=payload,timeout=10)

    _lark_bearer_token_json = response.json()
    
    _lark_bearer_token = _lark_bearer_token_json['tenant_access_token']
    
    self.lark_bearer_token = _lark_bearer_token


  def _init_lark_config(self):

    lark_config_table_url = "https://open.feishu.cn/open-apis/bitable/v1/apps/{}/tables/{}/records/search?page_size=500".format(
      self.lark_base_ID
      ,self.lark_config_table_ID
    )

    post_json = {
      "automatic_fields": False,
      "field_names": [
        self.config_head_site_no
        ,self.config_head_site_name
        ,self.config_head_positive_words
        ,self.config_head_negative_words
      ],
      "filter": {
        "conditions": [
          {
            "field_name": self.config_head_open_date,
            "operator": "isLess",
            "value": ["Tomorrow"]
          },
          {
            "field_name": self.config_head_close_date,
            "operator": "isGreater",
            "value": ["Yesterday"]
          }
        ],
        "conjunction": "and"
      },
      "sort": [
        {
          "desc": False,
          "field_name": self.config_head_site_no
        }
      ] 
    }

    headers = {
      'Authorization': 'Bearer ' + self.lark_bearer_token,
      'Content-Type': 'application/json'
    }

    response = requests.request("POST", lark_config_table_url, headers=headers, json=post_json)

    response_json = response.json()

    lark_config_list = response_json['data']['items']

    lark_config_list = [item['fields'] for item in lark_config_list]

    self.lark_config_list = lark_config_list
  


class Meta_0():

  def __init__(self,config:Config):
    
    self.config = config

    self.meta_id = self.__class__.__name__.split("_")[1]

    self.meta_name = ""

  def _fetch_html(
      self
      ,url:str
    ) -> str:
      
      if self.config.browser is not None:
        # Use Selenium if browser is available
        self.config.browser.get(url)

        WebDriverWait(self.config.browser, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        time.sleep(2)
        
        total_height = self.config.browser.execute_script("return document.body.scrollHeight")
        half_height = total_height // 2
        self.config.browser.execute_script(f"window.scrollTo(0, {half_height});")

        time.sleep(1)
        
        self.config.browser.execute_script("window.scrollTo(0, 0);")

        time.sleep(1)
        
        page_html = self.config.browser.page_source
        
        return page_html
      else:
        # Fallback to requests for testing
        self.config.logger.debug("Using requests fallback since browser not available")
        headers = {
          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text

  def _parse_page(self):
    
    response_text = ""

    url = "https://www.quamnet.com/channel/news/042928e4-dde9-478f-9ffb-7d58e5582b06"

    href = None

    response_text = self._fetch_html(url=url)

    html = etree.HTML(response_text)

    raw_title_list = html.xpath('//div[@class="post-list"]/div/h1/text()')

    raw_link_list = html.xpath('//div[@class="post-list"]/div/div/div/div/div/a[@class="permalink"]/@href')

    raw_date_list = html.xpath('//div[@class="post-list"]/div/div/div/div/div/a[@class="permalink"]/text()')

    self.config.logger.debug(
      "raw_text_list:{} raw_link_list{} raw_date_list:{}".format(
        len(raw_title_list),len(raw_link_list),len(raw_date_list)
      )
    )

    assert len(raw_title_list)==len(raw_link_list)==len(raw_date_list)

    date_list = []

    title_list = []

    link_list = []

    for title,link,date in zip(
      raw_title_list,raw_link_list,raw_date_list
    ):

      date = date.strip()

      date = datetime.strptime(date, "%Y-%m-%d %H:%M")

      if self.config.day_now == date.strftime("%d"):

        date = time.strftime("%Y-%m-%d %H:%M:%S")

        title_list.append(
          title
        )

        link_list.append(
          link
        )

        date_list.append(
          date
        )

      else:

        continue
    
    return title_list,link_list,date_list

  def _build_table(
      self
      ,title_list
      ,link_list
      ,date_list
    ):

    history_table_row_count = len(link_list)

    meta_id_list = [self.meta_id] * history_table_row_count

    meta_name_list = [self.meta_name] * history_table_row_count

    log_stamp_list = [
      datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ] * history_table_row_count

    push_device_list = [
      self.config.device
    ] * history_table_row_count

    return pd.DataFrame(
      {
        self.config.history_head_site_no:meta_id_list
        ,self.config.history_head_site_name:meta_name_list
        ,self.config.history_head_news_title:title_list
        ,self.config.history_head_news_link:link_list
        ,self.config.history_head_news_date:date_list
        ,self.config.history_head_log_stamp:log_stamp_list
        ,self.config.history_head_push_device:push_device_list
      }
    )
  

  
  def _init_history_set(self):
    # Simple testing version - just return empty set
    self.config.logger.debug("init history set - testing mode")
    return set()

  def _distinct_spider(self,spider_df:pd.DataFrame,history_set:set):

    distinct_df = spider_df[
      ~spider_df[
        self.config.history_head_news_link
      ].isin(history_set)
    ]

    return distinct_df

  def _push_lark_history(self,distinct_df:pd.DataFrame):
    # Simple testing version - just log
    self.config.logger.debug(f"Would push {len(distinct_df)} records to Lark history")
    return

  def _push_apx_history(self,distinct_df:pd.DataFrame):
    # APX history push method - implement as needed
    self.config.logger.debug(f"Would push {len(distinct_df)} records to APX history table")
    self.config.logger.debug(f"Sample data: {distinct_df.head().to_dict()}")
    return

  


  def _detect_words(
    self
    ,word_group_list:list
    ,title:str
  ):
    
    hit_words_list = []

    for positive_word_group in word_group_list:

      positive_word_split_list = positive_word_group.split("+")

      for positive_word_split in positive_word_split_list:

        positive_word_pattern = positive_word_split.replace("/","|")

        search_hit = re.search(
          pattern=positive_word_pattern
          ,string=title
          ,flags=re.I
          )
        
        if search_hit :

          hit_words_list.append(
            search_hit.group()
          )
        
        else:

          hit_words_list = []

          break
      
      else:

        break
    
    if hit_words_list:

      return "、".join(hit_words_list)

    else :

      return None

  def detect_words(
    self
    ,word_group_list:list
    ,title:str
  ):
    
    hit_words_list = []

    for positive_word_group in word_group_list:

      positive_word_split_list = positive_word_group.split("+")

      for positive_word_split in positive_word_split_list:

        positive_word_pattern = positive_word_split.replace("/","|")

        search_hit = re.search(
          pattern=positive_word_pattern
          ,string=title
          ,flags=re.I
          )
        
        if search_hit :

          hit_words_list.append(
            search_hit.group()
          )
        
        else:

          hit_words_list = []

          break
      
      else:

        break
    
    if hit_words_list:

      return "、".join(hit_words_list)

    else :

      return None

  def _filter_distinct(self,distinct_table:pd.DataFrame):

    self.config.logger.debug(
      "_filter_distinct"
    )

    # Check if DataFrame is empty
    if len(distinct_table) == 0:
      self.config.logger.debug("No data to filter - returning empty DataFrame")
      return distinct_table

    distinct_table[
      self.config.config_head_negative_words
    ] = distinct_table.apply(
      lambda row:self._detect_words(
          row[self.config.config_head_negative_words]
          ,row[self.config.history_head_news_title]
        )
      ,axis=1
    )
    
    distinct_table = distinct_table[
      distinct_table[
        self.config.config_head_negative_words
      ].isna()
    ]

    distinct_table = distinct_table.drop(
      [
        self.config.config_head_negative_words
      ]
      , axis=1
    )

    distinct_table[
      self.config.hit_head_positive_words
    ] = distinct_table.apply(
      lambda row:self.detect_words(
          row[self.config.config_head_positive_words]
          ,row[self.config.history_head_news_title]
        )
      ,axis=1
    )
    
    distinct_table = distinct_table[
      distinct_table[
        self.config.hit_head_positive_words
      ].notna()
    ]

    return distinct_table

  def _push_lark_filter(self,filter_table:pd.DataFrame):
    # Simple testing version - just log
    self.config.logger.debug(f"Would push {len(filter_table)} records to Lark filter")
    return


  def run(self):

    lark_history_set = self._init_history_set()

    title_list,link_list,date_list = self._parse_page()

    spider_df = self._build_table(title_list,link_list,date_list)

    distinct_df = self._distinct_spider(spider_df,lark_history_set)

    self._push_lark_history(distinct_df)

    self._push_apx_history(distinct_df)

    filter_df = self._filter_distinct(distinct_df)

    self._push_lark_filter(filter_df)





class Flow():

  def _init_meta_class(self) -> dict:

    current_module = sys.modules[__name__]

    class_dict = {

      int(name.split("_")[1]):obj

      for name, obj in inspect.getmembers(current_module)

      if inspect.isclass(obj) 

        and obj.__module__ == current_module.__name__ 

        and name.startswith("Meta")
    }

    return class_dict
  
  def run(self):

    class_dict = self._init_meta_class()

    config = Config()

    for lark_config_row_dict in config.lark_config_list:

      website_no = lark_config_row_dict[
        config.config_head_site_no
      ]

      website_name = lark_config_row_dict[
        config.config_head_site_name
      ]

      try:

        config.logger.debug(
          "handle {} {}".format(
            website_no,website_name
          )
        )

        Meta = class_dict.get(
          website_no
          ,None
        )

        meta:Meta_0 = Meta(config)

        meta.meta_name = website_name

        meta.run()

        config.logger.debug(
          "finsish".format(
            
          )
        )
      
      except Exception as e:

        config.logger.debug(e)

        config.post_lark_notice(
          name = config.name,
          at= config.at,
          message = "skip {} {} \n {}".format(
            website_no,website_name,traceback.format_exc()
          )
        )
      
        config.total_max_exception -= 1

        if config.total_max_exception == 0:

          exit()



if __name__ == "__main__":

  flow = Flow()

  flow.run()

# C:\CTG_RPA\News_Energy\Python\python.exe "C:\CTG_RPA\News_Energy\Code\alpha.py"

# Get-Content .\Distributed_Handle_Record.log -Tail 10 -Wait -Encoding UTF8