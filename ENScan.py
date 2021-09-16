#!env python3
# Keac
# admin@wgpsec.org
# WgpSec Team
import argparse
import datetime
import json
import logging
import os
from time import sleep

import pandas as pd
import redis
import requests
import random
import re
import _thread

from colorama import Fore
from tqdm import tqdm

requests.packages.urllib3.disable_warnings()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# 是否开启Redis模式
isRedis = False
if isRedis:
    pool = redis.ConnectionPool(host='localhost', port=6379, password='')
    r = redis.StrictRedis(connection_pool=pool)


class EIScan(object):
    def __init__(self):
        # 文件配置项
        self.user_proxy = []  # 是否添加常用代理
        self.cookie = ""  # 是否添加Cookie信息（打开浏览器，打开爱企查，复制cookie）
        # 是否开启代理 (速度变慢，但提高稳定性)
        self.is_proxy = False
        # 是否拿到分支机构详细信息，为了获取邮箱和人名信息等
        self.is_branch = False
        # 是否选出不清楚投资比例的（出现误报较高）
        self.invest_is_rd = False
        # 筛选投资比例需要大于多少
        self.invest_num = 90
        # ==== 初始化数据 ====
        self.isCmd = False
        self.resData = {}
        self.c_data = {}
        self.c_data['branch_list']={}
        self.p_bar = None
        self.pid = None
        self.c_name = None
        self.rKey = None
        self.is_rp = True
        self.enInfo = {}
        self.clear()

        self.version = "v1.0.0"
        self.proxy = "http://proxy.ts.wgpsec.org/get_all/"

    def clear(self):
        self.c_data = {}
        self.p_bar = None
        self.pid = None
        self.c_name = None
        self.rKey = None
        self.enInfo = {
            "basicInfo": {},
            "icpList": [],
            "emailInfo": [],
            "appInfo": [],
            "socialInfo": [],
            "legalPersonInfo": []
        }

    def get_show_banner(self):
        print("""\033[32m
              ______ _   _  _____                 
             |  ____| \ | |/ ____|                
             | |__  |  \| | (___   ___ __ _ _ __  
             |  __| | . ` |\___ \ / __/ _` | '_ \ 
             | |____| |\  |____) | (_| (_| | | | |
             |______|_| \_|_____/ \___\__,_|_| |_|
                                            
                ENScan 企业资产快速收集工具 {}
                  WgpSec Team @Keac
                www.wgpsec.org
                \033[0m
                """.format(self.version))

    def set_redis(self):
        if isRedis:
            self.c_data['enInfo'] = self.enInfo
            r.set(self.rKey, json.dumps(self.c_data), ex=(3600 * 24 * 7))
        pass

    def build_headers(self, referer):
        if not referer:
            referer = 'https://aiqicha.baidu.com/'
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
            'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/68.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:61.0) '
            'Gecko/20100101 Firefox/68.0',
            'Mozilla/5.0 (X11; Linux i586; rv:31.0) Gecko/20100101 Firefox/68.0'
        ]
        ua = random.choice(user_agents)
        headers = {
            'Accept': 'text/html, application/xhtml+xml, image/jxr, */*',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-Hans-CN, zh-Hans; q=0.5',
            'Connection': 'Keep-Alive',
            'Cookie': self.cookie,
            'Referer': referer,
            'User-Agent': ua
        }
        return headers

    # 获取代理信息
    def get_proxy(self, is_add=False):
        if not is_add:
            self.user_proxy = []
        logger.info("Get Proxy")
        test_p = requests.get('http://proxy.ts.wgpsec.org/get_all/', timeout=3)
        pr_ip = json.loads(test_p.text)
        if len(pr_ip) < 1:
            test_p = requests.get('http://proxy.ts.wgpsec.org/get_all/', timeout=3)
            pr_ip = json.loads(test_p.text)
        logger.info("Get Proxy Pool {}".format(len(pr_ip)))
        proxy_bar = tqdm(total=len(pr_ip), desc="【Proxy】",
                         bar_format='{l_bar}%s{bar}%s{r_bar}' % (Fore.BLUE, Fore.RESET))
        for p_ip in pr_ip:
            pt_s = {
                "https": "http://" + p_ip['proxy'],
            }
            try:
                proxy_bar.update(1)
                # self.user_proxy.append(pt_s)
                # 判断代理存活性
                p = requests.get('http://myip.ipip.net', verify=False, proxies=pt_s, timeout=3)
                if p.status_code == 200:
                    if p.text.find(p_ip['proxy']):
                        logger.info(p_ip['proxy'] + " 【ok】")
                        if pt_s not in self.user_proxy:
                            self.user_proxy.append(pt_s)
            except Exception as e:
                a = e
                # 删除错误代理
                requests.get("http://proxy.ts.wgpsec.org/delete/?proxy={}".format(p_ip['proxy']))
        if len(self.user_proxy) < 1:
            self.get_proxy()
        if len(self.user_proxy) < 3:
            _thread.start_new_thread(self.get_proxy, (True,))
        if isRedis:
            r.set("c:im:proxy", json.dumps(self.user_proxy))
        proxy_bar.close()
        logger.info("====HAVE {} PROXY===".format(len(self.user_proxy)))
        return self.user_proxy

    # 统一代理请求
    def get_req(self, url, referer, redirect, is_json=False, t=0):
        # 判断尝试次数
        if t > 20:
            logger.error("【失败】请求超过20次 {}".format(url))
            raise Exception(print("请求错误尝试超过20次，自动退出"))

        # 随机获取一个代理
        proxy = None
        if self.is_proxy and len(self.user_proxy) > 0:
            proxy = random.choice(self.user_proxy)

        try:
            if proxy is not None and self.is_proxy:
                resp = requests.get(url, headers=self.build_headers(referer), verify=False, timeout=10,
                                    allow_redirects=redirect,
                                    proxies=proxy)
            else:
                resp = requests.get(url, headers=self.build_headers(referer), verify=False, timeout=10,
                                    allow_redirects=redirect,
                                    )

            if resp.status_code == 200:
                # 判断返回为 200 成功
                res = resp.text
                # 判断是否需要进行 json 校验（部分请求可能出现验证码，非预期效果）
                if is_json:
                    # 判断status json格式成功返回一般都带这个
                    if resp.json()['status'] != 0:
                        logger.warning("【JSON校验错误重试】返回内容： {} ".format(res))
                        # 递归请求，这里错误可能是网络原因什么的导致错误
                        return self.get_req(url, referer, redirect, is_json, t + 1)
                return res
            elif resp.status_code == 302:
                # 如果是302一般是跳到百度的安全校验那边去了，需要设置下Cookie信息或者用代理
                logger.error("【风险校验】需要更新Cookie {}".format(url))
                return None
            else:
                # 如果返回不是302和200 那就继续请求看看是不是能解决
                return self.get_req(url, referer, redirect, is_json, t + 1)
        except requests.exceptions.Timeout:
            logger.info("【连接超时自动重连】 {} ".format(proxy))
            sleep(1)
            return self.get_req(url, referer, redirect, is_json, t + 1)
        except requests.exceptions.ProxyError:
            logger.info("【代理连接错误】 {} ".format(proxy))
            if self.is_proxy:
                logger.info("【自动删除代理】 {} ".format(proxy))
                requests.get("http://proxy.ts.wgpsec.org/delete/?proxy={}".format(proxy['https']))
                self.user_proxy.remove(proxy)
                # 看看代理还够不够，不够得新增
                if t > len(self.user_proxy) / 2 or len(self.user_proxy) < 3:
                    _thread.start_new_thread(self.get_proxy, ())
            sleep(1)
            return self.get_req(url, referer, redirect, is_json, t + 1)
        except Exception as e:
            # 如果不是上面几种错误，估计出问题了，就不要请求了
            logger.warning("【请求错误】 {} ".format(e))
            return None

    def parse_index(self, content, flag=True):
        tag_2 = '/* eslint-enable */</script><script data-app'
        tag_1 = 'window.pageData ='
        idx_1 = content.find(tag_1)
        idx_2 = content.find(tag_2)
        # 判断关键词区间中的JSON数据来进行匹配
        if idx_2 > idx_1:
            # 关键词提取判断，去除多余字符
            mystr = content[idx_1 + len(tag_1): idx_2].strip()
            mystr = mystr.replace("\n", "")
            mystr = mystr.replace("window.isSpider = null;", "")
            mystr = mystr.replace("window.updateTime = null;", "")
            mystr = mystr.replace(" ", "")
            mystr = mystr.replace("if(window.pageData.result.isDidiwei){window.location.href=`/login?u=${encodeURIComponent(window.location.href)}`}", "")
            mystr = mystr.replace(" ", "")
            len_str = len(mystr)
            if mystr[len_str - 1] == ';':
                mystr = mystr[0:len_str - 1]
            # 数据JSON转化
            j = json.loads(mystr)
            # 判断数据
            if flag:
                return j["result"]

            if len(j["result"]["resultList"]) > 0:
                item = j["result"]["resultList"][0]
                return item
            else:
                # 返回可能没查到企业信息
                return None

        else:
            logger.error("【关键词数据提取失败】 {}".format(idx_1))
            return None

    def get_item_name(self, item):
        entName = item['entName']
        pattern = re.compile(r'<[^>]+>', re.S)
        result = pattern.sub('', entName)
        return item['pid'], result

    def access_pid(self, pid, url_prefix, t=0):
        # url = "https://aiqicha.baidu.com/detail/compinfo?pid=" + pid
        url = "https://aiqicha.baidu.com/company_detail_" + pid
        content = self.get_req(url, url_prefix, True)
        res = self.parse_detail(content)
        if res:
            return res
        else:
            if t > 20:
                logger.error("Error to access pid".format(t))
                return None
            logger.info("access pid ERROR try{}".format(t))
            return self.access_pid(pid, url_prefix, t + 1)

    def access_des(self, pid, url_prefix, t=0):
        url = "https://aiqicha.baidu.com/compdata/navigationListAjax?pid=" + pid
        res = self.get_req(url, url_prefix, True, is_json=True)
        if pid == 51881537729212:
            return None
        if res:
            res = json.loads(res)['data']
            return res
        else:
            if t > 20:
                logger.error("Error to access pid".format(t))
                return None
            logger.info("access pid ERROR try{}".format(t))
            return self.access_pid(pid, url_prefix, t + 1)

    def parse_detail(self, content):
        tag_2 = '/* eslint-enable */</script><script data-app'
        tag_1 = 'window.pageData ='
        idx_1 = content.find(tag_1)
        idx_2 = content.find(tag_2)
        if idx_2 > idx_1:
            mystr = content[idx_1 + len(tag_1): idx_2].strip()
            mystr = mystr.replace("\n", "")
            mystr = mystr.replace("window.isSpider = null;", "")
            mystr = mystr.replace("window.updateTime = null;", "")
            mystr = mystr.replace(" ", "")
            mystr = mystr.replace("if(window.pageData.result.isDidiwei){window.location.href=`/login?u=${encodeURIComponent(window.location.href)}`}", "")
            mystr = mystr.replace(" ", "")
            # mystr = content[idx_1 + len(tag_1): idx_2].strip()
            len_str = len(mystr)
            if mystr[len_str - 1] == ';':
                mystr = mystr[0:len_str - 1]
            j = json.loads(mystr)
            return j["result"]
        else:
            return None

    def get_company_info_user(self, pid):
        item_detail = self.access_pid(pid, "")
        item_detail['newTabs'] = self.access_des(pid, "")
        info = {}
        if item_detail:
            # 基本信息获取
            info["email"] = item_detail["email"]
            info["addr"] = item_detail["addr"]
            info["website"] = item_detail["website"]
            info["legalPerson"] = item_detail["legalPerson"]
            info["entName"] = item_detail["entName"]
            info["openStatus"] = item_detail["openStatus"]
            info["telephone"] = item_detail["telephone"]
            if item_detail['newTabs'][1]['name'] == '上市信息':
                l = 1
            else:
                l = 0
            print(l)
            # 根据信息顺序数字判断
            info["invest"] = item_detail['newTabs'][0]['children'][7]['total']
            info["hold"] = item_detail['newTabs'][0]['children'][8]['total']
            info["branch"] = item_detail['newTabs'][0]['children'][12]['total']
            info["icpNum"] = item_detail['newTabs'][2 + l]['children'][0]['total']
            info["copyrightNum"] = item_detail['newTabs'][2 + l]['children'][3]['total']
            info["microblog"] = item_detail['newTabs'][4 + l]['children'][10]['total']
            info["wechatoa"] = item_detail['newTabs'][4 + l]['children'][11]['total']
            info["appinfo"] = item_detail['newTabs'][4 + l]['children'][12]['total']
            info["supplier"] = item_detail['newTabs'][4 + l]['children'][22]['total']
            email_info = {
                # "entName": info["entName"],
                "email": info["email"],
                "legalPerson": info["legalPerson"],
                "telephone": info["telephone"],
            }
            if info["email"] not in self.enInfo['emailInfo'] and info["email"] != "-":
                self.enInfo['emailInfo'].append(info["email"])
            if email_info not in self.enInfo['legalPersonInfo']:
                self.enInfo['legalPersonInfo'].append(email_info)

        return info

    def get_info_list(self, pid, types):
        logger.info("查询API {} ".format(types))
        url_prefix = 'https://www.baidu.com/'
        url = "https://aiqicha.baidu.com/"
        url += types
        url += "?size=100&pid=" + pid
        content = self.get_req(url, url_prefix, True, True)
        res_data = json.loads(content)
        list_data = []
        if res_data['status'] == 0:
            data = res_data['data']
            if types == "relations/relationalMapAjax":
                data = data['investRecordData']
            page_count = data['pageCount']
            if page_count > 1:
                proxy_bar = tqdm(total=page_count, desc="【INFO_LIST】",
                                 bar_format='{l_bar}%s{bar}%s{r_bar}' % (Fore.BLUE, Fore.RESET))
                for t in range(1, page_count + 1):
                    proxy_bar.update(1)
                    req_url = url + "&p=" + str(t) + "&page=" + str(t)
                    content = self.get_req(req_url, url_prefix, True, True)
                    res_s_data = json.loads(content)['data']
                    list_data.extend(res_s_data['list'])
                proxy_bar.close()
            else:
                list_data = data['list']
        return list_data

    def get_company_c(self, pid, flag=False):
        s_info = self.get_company_info_user(pid)
        c_info = {}
        print("----基本信息----")
        if s_info['openStatus'] == '注销' or s_info['openStatus'] == '吊销':
            print(s_info['legalPerson'])
            return None
        else:
            c_info['basic_info'] = s_info
            if flag:
                self.c_data['info'] = c_info
                self.set_redis()
            for t in s_info:
                print(t + ":" + str(s_info[t]))
            if s_info['icpNum'] != "" and s_info['icpNum'] > 0:
                print("-ICP备案-")
                icp_info = self.get_info_list(pid, "detail/icpinfoAjax")
                c_info['icp_info'] = icp_info
                for icp_item in icp_info:
                    for domain_item in icp_item['domain']:
                        icp_t = {
                            "entName": s_info['entName'],
                            "siteName": icp_item['siteName'],
                            "homeSite": icp_item['homeSite'][0],
                            "icpNo": icp_item['icpNo'],
                            "domain": domain_item,
                        }
                        self.enInfo["icpList"].append(icp_t)
                    print(icp_item)
            if flag:
                self.c_data['info'] = c_info
                self.set_redis()
            if s_info['appinfo'] != "" and s_info['appinfo'] > 0:
                print("-APP信息-")
                info_res = self.get_info_list(pid, "c/appinfoAjax")
                c_info['app_info'] = info_res
                for info_item in info_res:
                    info_item['entName'] = s_info['entName']
                    self.enInfo["appInfo"].append(info_item)
                    print(info_item)
            if flag:
                self.c_data['info'] = c_info
                self.set_redis()
            if s_info['microblog'] != "" and int(s_info['microblog']) > 0:
                print("-微博信息-")
                info_res = self.get_info_list(pid, "c/microblogAjax")
                c_info['micro_blog'] = info_res
                for info_item in info_res:
                    print(info_item)
            if flag:
                self.c_data['info'] = c_info
                self.set_redis()
            if s_info['wechatoa'] != "" and s_info['wechatoa'] > 0:
                print("-微信公众号信息-")
                info_res = self.get_info_list(pid, "c/wechatoaAjax")
                c_info['wechat_mp'] = info_res
                for info_item in info_res:
                    print(info_item)
            if flag:
                self.c_data['info'] = c_info
                self.set_redis()
            if s_info['copyrightNum'] != "" and s_info['copyrightNum'] > 0:
                print("-软件著作-")
                copyright_info = self.get_info_list(pid, "detail/copyrightAjax")
                for copy_item in copyright_info:
                    print(copy_item['softwareName'])
                    print(copy_item['detail'])
            c_info['supplier_info'] = None
            if s_info['supplier'] != "" and s_info['supplier'] > 0:
                print("-供应商信息-")
                copyright_info = self.get_info_list(pid, "c/supplierAjax")
                for copy_item in copyright_info:
                    print(copy_item['supplier'])
                c_info['supplier_info'] = copyright_info
            if flag:
                self.c_data['info'] = c_info
                self.set_redis()
            print("-XX-基本信息END-XX-")
        return c_info

    # 查询关键词信息
    def get_cm_if(self, name, t=0):
        company = name
        item = None
        url_prefix = 'https://www.baidu.com/'
        url_a = 'https://aiqicha.baidu.com/s?q=' + company + '&t=0'
        content = self.get_req(url_a, url_prefix, False)
        if content:
            item = self.parse_index(content, False)
        if t > 3:
            return None
        if item:
            return item
        else:
            logger.warning("【关键词查询重试】{}  {}".format(name, t))
            return self.get_cm_if(name, t + 1)

    def get_company_info(self, pid):
        print(pid)
        # 根据pid去查询公司信息
        self.c_data['info'] = self.get_company_c(pid, True)
        if self.c_data['info'] is None:
            return None
        print(self.c_data)
        self.set_redis()
        self.p_bar.update(10)
        print(self.c_data['info'])
        en_name = self.c_data['info']['basic_info']['entName']
        logger.info("【查分支机构】{}".format(en_name))
        relations_info = self.get_info_list(pid, "detail/branchajax")
        self.c_data['branch'] = relations_info
        self.set_redis()
        for s in relations_info:
            print(s['entName'] + " " + s['openStatus'])
            # 是否拿到分支机构的详细信息
            if self.is_branch:
                self.get_company_c(s['pid'])
                # self.c_data['branch_list'][s['pid']] = self.get_company_c(s['pid'])
        self.p_bar.update(10)
        # print("===控股公司===")
        # holds_info_data = []
        # holds_info = self.get_info_list(pid, "detail/holdsAjax")
        # for s in holds_info:
        #     print(s['entName'])
        #     holds_info_data.append(self.get_company_c(s['pid']))
        # self.c_data['holds'] = holds_info_data
        self.p_bar.update(10)
        logger.info("【对外投资信息】{}".format(en_name))
        invest_data = []
        holds_info = self.get_info_list(pid, "detail/investajax")
        self.p_bar.update(10)
        for s in holds_info:
            holds_info_data = {}
            print(s['entName'] + " 状态：" + s['openStatus'] + " 投资比例：" + s['regRate'])
            if s['regRate'] == '-':
                s['regRate'] = "-1"
            if float(s['regRate'].replace("%", "")) > self.invest_num or (s['regRate'] == "-1" and self.invest_is_rd):
                holds_info_data = self.get_company_c(s['pid'])
                print(holds_info_data)
                invest_data.append({
                    "entName": s['entName'],
                    "openStatus": s['openStatus'],
                    "regRate": s['regRate'].replace("%", ""),
                    "data": holds_info_data,
                })
        self.c_data['invest'] = invest_data
        self.set_redis()
        self.p_bar.update(10)

    def check_name(self, name):
        self.check_proxy()
        logger.info("【开始查询关键词】 {}".format(name))
        item = self.get_cm_if(name)
        if item:
            my = self.get_item_name(item)
            print("【根据关键词查询到公司】 " + my[1])
            if self.c_name is None:
                self.c_name = my[1]
            return my
        else:
            logger.error("【未查询到关键词】 {}".format(name))
            return None

    def check_proxy(self):
        # 判断代理情况，是否开启检查代理
        if self.is_proxy:
            logger.info("Check and update Proxy Info")
            if isRedis:
                if r.get("c:im:proxy") is not None:
                    self.user_proxy = json.loads(r.get("c:im:proxy"))
            if len(self.user_proxy) < 1:
                self.get_proxy()
            # _thread.start_new_thread(self.get_proxy, (True,))

    def export(self):
        logger.info("导出 {} 信息".format(self.c_name))
        if not os.path.exists("res"):
            os.mkdir("res")
        xlsx = pd.ExcelWriter(r"res/{}-{}.xlsx".format(datetime.date.today(), self.c_name))
        res = []
        # ICP备案信息
        icp_names = ['域名', '站点名称', '首页', '公司名称', 'ICP备案号']
        for item in self.c_data['enInfo']['icpList']:
            csv_res = {
                '域名': item['domain'],
                '站点名称': item['siteName'],
                '首页': item['homeSite'],
                '公司名称': item['entName'],
                'ICP备案号': item['icpNo'],
            }
            with open("test.txt", "a") as f:
                f.write(item['domain']+"\n")
            res.append(csv_res)
        df1 = pd.DataFrame(res, columns=icp_names)
        df1.to_excel(xlsx, sheet_name="ICP备案信息", index=False)
        # 投资工资与比例信息
        if self.c_data['invest']:
            res = []
            inv_names = ['公司名称', '状态', '投资比例', '数据信息']
            for item in self.c_data['invest']:
                csv_res = {
                    '公司名称': item['entName'],
                    '状态': item['openStatus'],
                    '投资比例': item['regRate'],
                    '数据信息': item['data']
                }
                res.append(csv_res)
            df2 = pd.DataFrame(res, columns=inv_names)
            df2.to_excel(xlsx, sheet_name="对外投资信息", index=False)
        # 导出APP信息
        res = []
        app_names = ["名称", "分类", "logo文字", "logo地址", "应用描述", "应用所属公司"]
        for item in self.c_data['enInfo']['appInfo']:
            csv_res = {
                '名称': item['name'],
                '分类': item['classify'],
                'logo文字': item['logoWord'],
                'logo地址': item['logo'],
                '应用描述': item['logoBrief'],
                '应用所属公司': item['entName'],
            }
            res.append(csv_res)
        df_app = pd.DataFrame(res, columns=app_names)
        df_app.to_excel(xlsx, sheet_name="APP信息", index=False)

        # 导出供应商信息
        if self.c_data['info']['supplier_info']:
            res = []
            supplier_names = ["供应商", "来源", "所属公司", "日期"]
            for item in self.c_data['info']['supplier_info']:
                csv_res = {
                    '供应商': item['supplier'],
                    '来源': item['source'],
                    '所属公司': item['principalNameClient'],
                    '日期': item['cooperationDate']
                }
                res.append(csv_res)
            df_supplier = pd.DataFrame(res, columns=supplier_names)
            df_supplier.to_excel(xlsx, sheet_name="供应商", index=False)

        xlsx.close()
        logger.info("导出 {} 信息完成".format(self.c_name))

    def main(self, pid=None, search_keyword=None):
        self.get_show_banner()
        logger.info("ENScan JOB Start")
        self.clear()
        # 获取关键词，判断是否命令模式
        self.pid = None
        if self.isCmd:
            print("==== 【命令行模式】 请输入关键词 ====")
            if search_keyword is None:
                search_keyword = input("")
            else:
                print("当前查询：{}".format(search_keyword))
        elif pid is not None:
            self.pid = pid

        # 设置进度条
        self.p_bar = tqdm(total=100)

        # 判断代理情况
        self.check_proxy()
        self.p_bar.update(10)
        # 判断结束代理

        # 判断命令模式，对关键词进行处理
        if self.isCmd:
            res = self.check_name(search_keyword)
            if res is not None:
                self.pid = res[0]

        if self.pid is not None:
            self.rKey = "c:im:info:" + self.pid
            if isRedis:
                if r.get(self.rKey) is None:
                    self.get_company_info(self.pid)
                else:
                    self.c_data = json.loads(r.get(self.rKey))
            else:
                self.get_company_info(self.pid)
                self.c_data['enInfo'] = self.enInfo

        self.p_bar.close()

        # 命令模式输出
        if not self.isCmd:
            return self.c_data
        else:
            # print(self.enInfo)
            print("!!!!!!!!!!!!Email!!!!!!!!!!!!!!!1")
            if self.c_data:
                # email_info = self.c_data['enInfo']['emailInfo']
                # for item in email_info:
                #     print(item)
                p_info = self.c_data['enInfo']['legalPersonInfo']
                for i in p_info:
                    print(i)
                if self.c_data['info']:
                    self.export()
            # print(self.c_data)
            if self.is_rp:
                self.main()


if __name__ == '__main__':
    Scan = EIScan()
    Scan.isCmd = True
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', dest='paths', help='指定批量查询关键词文本')
    parser.add_argument('-s', dest='key', help='指定查询关键词文本')
    args = parser.parse_args()
    if args.paths:
        Scan.is_rp = False
        paths = args.paths
        with open(paths, "r", encoding='UTF-8') as files:
            file_data = files.readlines()  # 读取文件
            for fi_s in file_data:
                fi_s = fi_s.strip('\n')
                Scan.main(None, fi_s)
                sleep(5)
    elif  args.key:
        Scan.main(None, args.key)
    else:
        Scan.main()
