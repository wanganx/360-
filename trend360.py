import re
import io
import os
import time
import json
import base64
import requests
import datetime
import numpy as np
from PIL import Image
from sklearn.externals import joblib
from settings import *
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException


BASE_DIR = os.path.join(os.path.dirname(__file__))
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)
cookie_path = os.path.join(BASE_DIR,'cookie','360_cookie.dat')


class LOGIN(object):
    def __init__(self):
        self.url = 'https://trends.so.com/'
        self.data_path = cookie_path
        cap = webdriver.DesiredCapabilities.PHANTOMJS
        cap["phantomjs.page.settings.resourceTimeout"] = 1000
        # self.driver = webdriver.PhantomJS(desired_capabilities=cap)
        self.driver = webdriver.Chrome(desired_capabilities=cap)
        self.driver.set_page_load_timeout(180)

    def __del__(self):
        self.driver.quit()

    def save_cookie_to_file(self):
        cookies = self.driver.get_cookies()
        with open(cookie_path, mode='w+', encoding='utf-8') as f:
            for cookie in cookies:
                line = json.dumps(cookie, ensure_ascii=False) + '\n'
                f.write(line)

    def retry_get(self, url):
        try:
            self.driver.get(url)
        except TimeoutException:
            pass


    def login_in(self):
        try:
            if not YOUR_PASSWORD or not YOUR_USERNAME:
                print("请在setting.py文件中填写用户名和密码！")

            self.retry_get(self.url)
            q_header_login = self.driver.find_element_by_xpath('//ul[@class="login"]/li[1]/a')
            q_header_login.click()
            time.sleep(0.3)
            uin_input = self.driver.find_element_by_xpath('//input[contains(@class,"quc-input-account")]')
            uin_input.clear()
            uin_input.send_keys(YOUR_USERNAME)
            pwd_input = self.driver.find_element_by_xpath('//input[contains(@class,"quc-input-password")]')
            pwd_input.clear()
            pwd_input.send_keys(YOUR_PASSWORD)
            print('如果有需要输验证码请在调试模式下 ')
            pwd_input.send_keys(Keys.ENTER)
            time.sleep(5)
            self.save_cookie_to_file()
        except Exception as e:
            print(e)

    def get_cookie(self):
        cookie_str = ""
        self.login_in()
        with open(cookie_path,'r',encoding='utf8') as f:
            for line in f.readlines():
                if line.strip():
                    cookie_line = json.loads(line)
                    cookie_str = cookie_str + cookie_line['name']+'='+cookie_line['value'] +"; "
        return cookie_str.strip('; ')


class Trend():
    def __init__(self):
        self.url = "https://index.so.com/index/csssprite"
        self.svm = joblib.load(os.path.join(BASE_DIR,'model','little_num.svm'))
        self.cookie = self.get_cookie()
        self.headers = {"Cookie":self.cookie}


    def get_num_from_img(self,img_list):
        X = [np.array(x).mean(axis=2).reshape(-1) for x in img_list]
        return "".join(self.svm.predict(X))

    @staticmethod
    def get_cookie(log=False):
        if not log and os.path.exists(cookie_path):
            cookie_str = ""
            with open(cookie_path, 'r', encoding='utf8') as f:
                for line in f.readlines():
                    if line.strip():
                        cookie_line = json.loads(line)
                        cookie_str = cookie_str + cookie_line['name'] + '=' + cookie_line['value'] + "; "
            return cookie_str.strip('; ')
        else:
            print('logging....')
            log = LOGIN()
            return log.get_cookie()

    def get_360_trend(self,search_words,start_date='',end_date=''):

        if isinstance(search_words,list):
            if len(search_words)>5:
                return {'error':1,'info':"最多同时查询五条关键字！"}
            search_word_str = ",".join(search_words)
        else:
            search_word_str = search_words
            search_words = [search_words]

        if not start_date and not end_date:
            e_date = datetime.datetime.today() - datetime.timedelta(1)
            s_date = e_date - datetime.timedelta(29)

        elif not end_date and start_date and re.match(r'\d+',str(start_date)):
            e_date = datetime.datetime.today() - datetime.timedelta(1)
            s_date = e_date - datetime.timedelta(int(start_date))

        elif re.match(r'\d{4}-\d{2}-\d{2}',str(start_date)):
            s_date = datetime.datetime.strptime(start_date,'%Y-%m-%d')
            e_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')

        elif re.match(r'\d{8}',str(start_date)):
            s_date = datetime.datetime.strptime(str(start_date), '%Y%m%d')
            e_date = datetime.datetime.strptime(str(end_date), '%Y%m%d')

        else:
            return {'error':1,'info':"时间格式不正确！"}

        if e_date >= datetime.datetime.today():
            return {'error':1,'info':"结束日期不能大于或等于当日！"}

        if (e_date - s_date).days > 360:
            return {'error':1,"info":"请选择360天以内时间区间"}
        result = {}

        for search_word in search_words:
            result[search_word] = []

        i = 1
        this_date = s_date
        while this_date <= e_date:
            data = {
                "q": search_word_str,
                "area": "全国",
                "from": int(this_date.strftime("%Y%m%d")),
                "to": int(e_date.strftime("%Y%m%d")),
                "click": 1,
                "t": "index",
            }
            res = requests.post(self.url, params=data, headers=self.headers)
            res_i = res.json()

            if res_i['msg'] != "success":
                self.cookie = self.get_cookie(log=True)
                self.headers = {"Cookie":self.cookie}
                continue

            for search_word in search_words:
                img_content = base64.b64decode(res_i['data'][search_word]['img'].split(',', 1)[-1])
                stream = io.BytesIO(img_content)
                img = Image.open(stream)
                num_po = res_i['data'][search_word]['css']
                num_v_ = re.findall(
                    r'<span class=\'imgval\' style=\'width:6.000000px;background-position:(.*?)px 6px\'></span>', num_po)
                num_v = [abs(int(float(x))) for x in num_v_]

                img_list = []
                for i, numi in enumerate(num_v):
                    num_img = img.crop((numi, 0, numi + 6, 12))
                    img_list.append(num_img)

                result[search_word].append((this_date.strftime("%Y-%m-%d"),self.get_num_from_img(img_list)))

            this_date = this_date + datetime.timedelta(days=1)
            i += 1

        return result


if __name__ == '__main__':
    trend = Trend()
    #                          剧名，最多5个    起始日期        结束日期
    print(trend.get_360_trend(['等到烟暖雨收'],'2018-12-01','2018-12-06'))
