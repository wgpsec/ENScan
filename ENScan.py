#!env python3
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
pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True)
r = redis.StrictRedis(host='127.0.0.1', port=6379, db=0, decode_responses=True)


class EIScan(object):
    def __init__(self):
        self.user_proxy = []
        self.icp_list = []
        self.data = []
        self.c_data = {}
        self.p_bar = None
        self.pid = None
        self.rKey = None

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
            'Cookie': 'BIDUPSID={};'.format("959BD58239197A4C8C27D9AA6CE6802A"),
            'Referer': referer,
            'User-Agent': ua
        }
        return headers

    # 获取代理信息
    def get_proxy(self):
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
                p = requests.get('https://icanhazip.com', verify=False, proxies=pt_s, timeout=3)
                if p.status_code == 200:
                    if p.text.find(p_ip['proxy']):
                        logger.info(p_ip['proxy'] + " 【ok】")
                        self.user_proxy.append(pt_s)
            except:
                requests.get("http://proxy.ts.wgpsec.org/delete/?proxy={}".format(p_ip['proxy']))
        if len(self.user_proxy) < 1:
            self.get_proxy()
        if len(self.user_proxy) < 3:
            _thread.start_new_thread(self.get_proxy, ())
        r.set("c:im:proxy", json.dumps(self.user_proxy))
        proxy_bar.close()
        logger.info("====HAVE {} PROXY===".format(len(self.user_proxy)))
        return self.user_proxy

    # 统一代理请求
    def get_req(self, url, referer, redirect, is_json=False, t=0):
        # 随机获取一个代理
        proxy = random.choice(self.user_proxy)
        # 判断尝试次数
        if t > 20:
            logger.error("【失败】请求超过20次 {}".format(url))
            raise Exception(print("！！！尝试超过！！！ NO NO!!!"))
        try:
            if proxy:
                resp = requests.get(url, headers=self.build_headers(referer), verify=False, timeout=10,
                                    allow_redirects=redirect,
                                    proxies=proxy)
            else:
                logger.error("【未检测到任何代理请求】")
                raise Exception(print("没有获取到代理"))
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
            if len(self.user_proxy) > 3:
                logger.info("【自动删除代理】 {} ".format(proxy))
                self.user_proxy.remove(proxy)
            if t > len(self.user_proxy) / 2 or len(self.user_proxy) < 3:
                _thread.start_new_thread(self.get_proxy, ())
            return self.get_req(url, referer, redirect, is_json, t + 1)
        except Exception as e:
            logger.warning("【请求错误】 {} ".format(e))
            if t > 20:
                print("ERROR")
                raise Exception(print("！！！尝试超过！！！" + str(e)))
            return self.get_req(url, referer, redirect, is_json, t + 1)
        finally:
            pass

    def parse_index(self, content):
        tag_2 = '/* eslint-enable */</script> <script type="text/javascript"'
        tag_1 = 'window.pageData ='
        idx_1 = content.find(tag_1)
        idx_2 = content.find(tag_2)

        if idx_2 > idx_1:

            mystr = content[idx_1 + len(tag_1): idx_2].strip()
            len_str = len(mystr)
            if mystr[len_str - 1] == ';':
                mystr = mystr[0:len_str - 1]
            j = json.loads(mystr)

            if len(j["result"]["resultList"]) > 0:
                item = j["result"]["resultList"][0]
                return item
            else:
                return None

        else:
            return None

    def get_item_name(self, item):
        entName = item['entName']
        pattern = re.compile(r'<[^>]+>', re.S)
        result = pattern.sub('', entName)
        return item['pid'], result

    def access_pid(self, pid, url_prefix):
        url = "https://aiqicha.baidu.com/detail/compinfo?pid=" + pid
        content = self.get_req(url, url_prefix, True)
        res = self.parse_detail(content)
        # print(res)
        if res:
            return res
        else:
            return self.access_pid(pid, url_prefix)

    def parse_detail(self, content):
        tag_2 = '/* eslint-enable */</script> <script type="text/javascript"'
        tag_1 = 'window.pageData ='
        idx_1 = content.find(tag_1)
        idx_2 = content.find(tag_2)
        if idx_2 > idx_1:
            mystr = content[idx_1 + len(tag_1): idx_2].strip()
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
                r.set(self.rKey, json.dumps(self.c_data))
            for t in s_info:
                print(t + ":" + str(s_info[t]))
            if s_info['icpNum'] > 0:
                print("-ICP备案-")
                icp_info = self.get_info_list(pid, "detail/icpinfoAjax")
                c_info['icp_info'] = icp_info
                for icp_item in icp_info:
                    print(icp_item)
            if flag:
                self.c_data['info'] = c_info
                r.set(self.rKey, json.dumps(self.c_data))
            if s_info['appinfo'] > 0:
                print("-APP信息-")
                info_res = self.get_info_list(pid, "c/appinfoAjax")
                c_info['app_info'] = info_res
                for info_item in info_res:
                    print(info_item)
            if flag:
                self.c_data['info'] = c_info
                r.set(self.rKey, json.dumps(self.c_data))
            if s_info['microblog'] > 0:
                print("-微博信息-")
                info_res = self.get_info_list(pid, "c/microblogAjax")
                c_info['micro_blog'] = info_res
                for info_item in info_res:
                    print(info_item)
            if flag:
                self.c_data['info'] = c_info
                r.set(self.rKey, json.dumps(self.c_data))
            if s_info['wechatoa'] > 0:
                print("-微信公众号信息-")
                info_res = self.get_info_list(pid, "c/wechatoaAjax")
                c_info['wechat_mp'] = info_res
                for info_item in info_res:
                    print(info_item)
            if flag:
                self.c_data['info'] = c_info
                r.set(self.rKey, json.dumps(self.c_data))
            # if s_info['copyrightNum'] > 0:
            #     print("-软件著作-")
            #     copyright_info = self.get_info_list(pid, "detail/copyrightAjax")
            #     for copy_item in copyright_info:
            #         print(copy_item['softwareName'])
            #         print(copy_item['detail'])
            print("-XX-基本信息END-XX-")
        return c_info

    # 查询关键词信息
    def get_cm_if(self, name, t=0):
        company = name
        url_prefix = 'https://www.baidu.com/'
        url_a = 'https://aiqicha.baidu.com/s?q=' + company + '&t=0'
        content = self.get_req(url_a, url_prefix, False)
        item = self.parse_index(content)
        if t > 3:
            return None
        if item:
            return item
        else:
            logger.info("【关键词】{} 【失败重试】{}".format(name, t))
            return self.get_cm_if(name, t + 1)

    def get_company_info(self, pid):
        # 根据pid去查询公司信息
        self.c_data['info'] = self.get_company_c(pid, True)
        r.set(self.rKey, json.dumps(self.c_data))
        self.p_bar.update(10)
        print(self.c_data['info'])
        en_name = self.c_data['info']['basic_info']['entName']
        logger.info("【查分支机构】{}".format(en_name))
        relations_info = self.get_info_list(pid, "detail/branchajax")
        self.c_data['branch'] = relations_info
        r.set(self.rKey, json.dumps(self.c_data))
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
                if float(s['regRate'].replace("%", "")) > 50:
                    holds_info_data = self.get_company_c(s['pid'])
                    print(holds_info_data)
            invest_data.append({
                "entName": s['entName'],
                "openStatus": s['openStatus'],
                "regRate": s['regRate'],
                "data": holds_info_data,
            })
        self.c_data['invest'] = invest_data
        r.set(self.rKey, json.dumps(self.c_data))
        self.p_bar.update(10)

    def check_name(self, name):
        self.check_proxy()
        logger.info("【开始查询关键词】 {}".format(name))
        item = self.get_cm_if(name)
        if item:
            my = self.get_item_name(item)
            print("【根据关键词查询到公司】 " + my[1])
            return my
        else:
            logger.warning("【未查询到关键词】 {}".format(name))
            return None

    def check_proxy(self):
        # 判断代理情况
        if r.get("c:im:proxy") is not None:
            self.user_proxy = json.loads(r.get("c:im:proxy"))
        if len(self.user_proxy) < 1:
            self.get_proxy()
        if len(self.user_proxy) < 1:
            self.get_proxy()

    def main(self, name=None):
        logger.info("Start print log")
        if name is not None:
            company = name
        else:
            print("==== 【命令行模式】 Need Keyword ====")
            company = input("")
        # 设置进度条
        self.p_bar = tqdm(total=100)
        # 判断代理情况
        self.check_proxy()
        # 判断结束代理

        self.p_bar.update(10)
        pid = self.check_name(company)[0]
        if pid is not None:
            self.pid = pid
            self.rKey = "c:im:info:" + self.pid
            if r.get(self.rKey) is None:
                self.get_company_info(pid)
            else:
                self.c_data = r.get(self.rKey)

        self.p_bar.close()
        # 命令模式输出
        if name is not None:
            return self.c_data
        else:
            print(self.c_data)
            self.main()


if __name__ == '__main__':
    Scan = EIScan()
    Scan.main()
