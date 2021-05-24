#!env python3
import csv
import datetime
import json
import time
import logging

import redis
import requests
import random
import re
import _thread

from colorama import Fore
from flask import Flask, request
from tqdm import tqdm

requests.packages.urllib3.disable_warnings()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

isRedis = False
if isRedis:
    pool = redis.ConnectionPool(host='localhost', port=6379, password='')
    r = redis.StrictRedis(connection_pool=pool)


class EIScan(object):
    def __init__(self):
        self.user_proxy = []
        self.isCmd = False
        # 初始化数据
        self.resData = {}
        self.icp_list = []
        self.data = []
        self.c_data = {}
        self.p_bar = None
        self.pid = None
        self.c_name = None
        self.rKey = None
        self.enInfo = {}
        self.clear()
        self.is_proxy = False
        self.version = "v1.0.0"
        self.proxy = "http://proxy.ts.wgpsec.org/get_all/"

    def clear(self):
        self.icp_list = []
        self.data = []
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
                  WgpSec Team
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
            referer = 'https://www.baidu.com'
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
            'Cookie': 'BAIDUID=B0EA5B5A26D48D912916667E2C032D6C:FG=1; BIDUPSID=B0EA5B5A12D48D91E92ED7191B603D2B; PSTM=1591879205; BAIDUID_BFESS=B1EA5B5A26D48D915316667E2C052D6C:FG=1;',
            'Referer': referer,
            'User-Agent': ua
        }
        return headers

    # 获取代理信息
    def get_proxy(self, is_add=False):
        if not is_add:
            self.user_proxy = []
        self.user_proxy = []
        return self.user_proxy
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
                p = requests.get('https://icanhazip.com', verify=False, proxies=pt_s, timeout=3)
                if p.status_code == 200:
                    if p.text.find(p_ip['proxy']):
                        logger.info(p_ip['proxy'] + " 【ok】")
                        if pt_s not in self.user_proxy:
                            self.user_proxy.append(pt_s)
            except:
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
        # 随机获取一个代理
        proxy = False
        if self.is_proxy:
            proxy = random.choice(self.user_proxy)
        # 判断尝试次数
        if t > 20:
            logger.error("【失败】请求超过20次 {}".format(url))
            raise Exception(print("请求错误尝试超过20次，自动退出"))
        try:
            if proxy & self.is_proxy:
                resp = requests.get(url, headers=self.build_headers(referer), verify=False, timeout=10,
                                    allow_redirects=redirect,
                                    proxies=proxy)
                # print(resp.text)
            else:
                resp = requests.get(url, headers=self.build_headers(referer), verify=False, timeout=10,
                                    allow_redirects=redirect,
                                    )
                # print(resp.text)
                # logger.error("【未检测到任何代理请求】")
            # 判断返回为 200 成功
            if resp.status_code == 200:
                res = resp.text
                # 判断是否需要进行 json 校验（部分请求可能出现验证码，非预期效果）
                if is_json:
                    # 判断status json格式成功返回一般都带这个
                    if resp.json()['status'] != 0:
                        logger.warning("【JSON校验错误】返回内容： {} ".format(res))
                        # 递归请求
                        return self.get_req(url, referer, redirect, is_json, t + 1)
                    return res
                else:
                    return res
            else:
                # 如果返回不是200 OK那就继续请求看看
                return self.get_req(url, referer, redirect, is_json, t + 1)
        except requests.exceptions.Timeout:
            logger.info("【代理超时自动重连】 {} ".format(proxy))
            if self.is_proxy:
                if len(self.user_proxy) > 3:
                    logger.info("【自动删除代理】 {} ".format(proxy))
                    self.user_proxy.remove(proxy)
                if t > len(self.user_proxy) / 2 or len(self.user_proxy) < 3:
                    _thread.start_new_thread(self.get_proxy, ())
            return self.get_req(url, referer, redirect, is_json, t + 1)
        except requests.exceptions.ProxyError:
            if self.is_proxy:
                logger.info("【代理错误】 {} ".format(proxy))
                requests.get("http://proxy.ts.wgpsec.org/delete/?proxy={}".format(proxy['https']))
                if len(self.user_proxy) > 3:
                    logger.info("【自动删除代理】 {} ".format(proxy))
                    self.user_proxy.remove(proxy)
                if t > len(self.user_proxy) / 2 or len(self.user_proxy) < 3:
                    _thread.start_new_thread(self.get_proxy, ())
            return self.get_req(url, referer, redirect, is_json, t + 1)

        except Exception as e:
            print(e)
            logger.warning("【请求错误】 {} ".format(e))
            if t > 20:
                print("ERROR")
                raise Exception(print("！！！尝试超过！！！" + str(e)))
            return self.get_req(url, referer, redirect, is_json, t + 1)
        finally:
            pass

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
            logger.info("access pid ERROR try{}".format(t))
            if t > 20:
                logger.error("Error to access pid".format(t))
                return None
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
            info["invest"] = item_detail['newTabs'][0 + l]['children'][7]['total']
            info["hold"] = item_detail['newTabs'][0 + l]['children'][8]['total']
            info["branch"] = item_detail['newTabs'][0 + l]['children'][12]['total']
            info["icpNum"] = item_detail['newTabs'][2 + l]['children'][0]['total']
            info["copyrightNum"] = item_detail['newTabs'][2 + l]['children'][3]['total']
            info["microblog"] = item_detail['newTabs'][4 + l]['children'][7]['total']
            info["wechatoa"] = item_detail['newTabs'][4 + l]['children'][8]['total']
            info["appinfo"] = item_detail['newTabs'][4 + l]['children'][9]['total']
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
        url_prefix = 'https://www.baidu.com/'
        url = "https://aiqicha.baidu.com/"
        url += types
        url += "?size=100&pid=" + pid
        content = self.get_req(url, url_prefix, True, True)
        res_data = json.loads(content)
        list_data = []
        print("开始查询 " + types)

        if res_data['status'] == 0:
            data = res_data['data']
            if types == "relations/relationalMapAjax":
                data = data['investRecordData']
            page_count = data['pageCount']
            if page_count > 1:
                for t in range(1, page_count + 1):
                    print(str(t) + "/" + str(page_count))
                    # !!!!!!!!!!!!修复参数叠加bug
                    req_url = url + "&p=" + str(t) + "&page=" + str(t)
                    content = self.get_req(req_url, url_prefix, True, True)
                    res_s_data = json.loads(content)['data']
                    list_data.extend(res_s_data['list'])
            else:
                list_data = data['list']
        return list_data

    def get_company_c(self, pid, flag=False):
        s_info = self.get_company_info_user(pid)
        c_info = {}
        print("----基本信息----")
        if s_info['openStatus'] == '注销' or s_info['openStatus'] == '吊销':
            print(s_info['legalPerson'])
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
            print("-XX-基本信息END-XX-")
        return c_info

    # 查询关键词信息
    def get_cm_if(self, name, t=0):
        company = name
        url_prefix = 'https://www.baidu.com/'
        url_a = 'https://aiqicha.baidu.com/s?q=' + company + '&t=0'
        content = self.get_req(url_a, url_prefix, False)
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
            # self.get_company_c(s['pid'])
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
            if s['regRate'] != '-':
                # 判断投资比例
                if float(s['regRate'].replace("%", "")) > 90:
                    holds_info_data = self.get_company_c(s['pid'])
                    print(holds_info_data)
            invest_data.append({
                "entName": s['entName'],
                "openStatus": s['openStatus'],
                "regRate": s['regRate'],
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
            _thread.start_new_thread(self.get_proxy, (True,))

    def export(self, res, eName):
        print("导出" + eName)
        with open('res/{}-{}.csv'.format(datetime.date.today(), eName), 'a', newline='',
                  encoding='utf-8-sig') as csvfile:
            fieldnames = ['域名', '站点名称', '首页', '公司名称', 'ICP备案号']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            # 注意header是个好东西
            writer.writeheader()
            try:
                for item in res:
                    writer.writerow(item)
            except Exception as e:
                print(f'写入csv出错\n错误原因:{e}')
                pass
            finally:
                pass
            pass

    def main(self, pid=None):
        self.get_show_banner()
        logger.info("=== JOB Start ===")
        self.clear()
        # 获取关键词，判断是否命令模式
        search_keyword = None
        self.pid = None
        if self.isCmd:
            print("==== 【命令行模式】 请输入关键词 ====")
            search_keyword = input("")
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
            email_info = self.c_data['enInfo']['emailInfo']
            for item in email_info:
                print(item)
            p_info = self.c_data['enInfo']['legalPersonInfo']
            for i in p_info:
                print(i)
            res = []
            for item in self.c_data['enInfo']['icpList']:
                print(item)
                csv_res = {
                    '域名': item['domain'],
                    '站点名称': item['siteName'],
                    '首页': item['homeSite'],
                    '公司名称': item['entName'],
                    'ICP备案号': item['icpNo'],
                }
                res.append(csv_res)
            self.export(res, self.c_name)
            # print(self.c_data)
            self.main()


if __name__ == '__main__':
    Scan = EIScan()
    Scan.isCmd = True
    Scan.main()
