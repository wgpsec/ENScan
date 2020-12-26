#!env python3
import json
import time
import requests
import random
import re

requests.packages.urllib3.disable_warnings()


class EIScan(object):
    def __init__(self):
        self.user_proxy = [{}]
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
            'Mozilla/5.0 (X11; Linux i586; rv:31.0) Gecko/20100101 Firefox/68.0']
        ua = random.choice(user_agents)
        headers = {'Accept': 'text/html, application/xhtml+xml, image/jxr, */*',
                   'Accept-Encoding': 'gzip, deflate',
                   'Accept-Language': 'zh-Hans-CN, zh-Hans; q=0.5',
                   'Connection': 'Keep-Alive',
                   'Cookie': 'BIDUPSID=EA760A851A8300E10B0E70D41C1833F2; PSTM=1521186511;' + "pm=" + str(
                       random.random()),
                   'Referer': referer,
                   'User-Agent': ua
                   }
        return headers

    def get_proxy(self):
        self.user_proxy = [{}]
        print("====GET PROXY===")
        test_p = requests.get('http://proxy.ts.wgpsec.org/get_all/',
                              timeout=3)
        pr_ip = json.loads(test_p.text)
        print(len(pr_ip))
        for p_ip in pr_ip:
            pt_s = {
                "https": "http://" + p_ip['proxy'],
            }
            try:
                p = requests.get('https://icanhazip.com', verify=False,
                                 proxies=pt_s, timeout=3)
                if p.status_code == 200:
                    print(p_ip['proxy'] + " 【ok】")
                    self.user_proxy.append(pt_s)
            except:
                requests.get("http://proxy.ts.wgpsec.org/delete/?proxy={}".format(p_ip['proxy']))
        print("====HAVE {} PROXY===".format(len(self.user_proxy)))
        return self.user_proxy

    def get_req(self, fn, url, referer, redirect, t=0):
        proxy = random.choice(self.user_proxy)
        try:
            if proxy:
                resp = requests.get(url, headers=self.build_headers(referer), verify=False, timeout=10,
                                    allow_redirects=redirect,
                                    proxies=proxy)
            else:
                resp = requests.get(url, headers=self.build_headers(referer), verify=False, timeout=8,
                                    allow_redirects=redirect)
            res = resp.text
        except Exception as e:
            print("【失败】自动重连")
            if t > len(self.user_proxy):
                self.get_proxy()
            res = self.get_req("", url, referer, redirect, t + 1)
        return res

    def parse_index(self, content):
        tag_2 = '/* eslint-enable */</script> <script type="text/javascript"'
        tag_1 = 'window.pageData ='
        idx_1 = content.find(tag_1)
        idx_2 = content.find(tag_2)

        if (idx_2 > idx_1):

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
        content = self.get_req('./company_tmp/' + pid + 'aiqi_detail.html', url, url_prefix, True)
        res = self.parse_detail(content)
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
        print("==ITEM==")
        print(item_detail)
        print("===ITEM END==")
        info = {}
        if item_detail:
            # 基本信息获取
            info["email"] = item_detail["email"]
            info["addr"] = item_detail["addr"]
            info["website"] = item_detail["website"]
            info["legalPerson"] = item_detail["legalPerson"]
            info["entName"] = item_detail["entName"]
            info["openStatus"] = item_detail["openStatus"]
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
        content = self.get_req('./company_tmp/' + pid + 'aiqi_detail.html', url, url_prefix, True)
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
                    url += "&p=" + str(t) + "&page=" + str(t)
                    content = self.get_req('./company_tmp/' + pid + 'aiqi_detail.html', url, url_prefix, True)
                    res_s_data = json.loads(content)['data']
                    list_data.extend(res_s_data['list'])
            else:
                list_data = data['list']
        return list_data

    def get_company_c(self, pid):
        s_info = self.get_company_info_user(pid)
        print("----基本信息----")
        print(s_info)
        if s_info['openStatus'] == '注销':
            print(s_info['legalPerson'])
        else:
            for t in s_info:
                print(t + ":" + str(s_info[t]))
            if s_info['icpNum'] > 0:
                print("-ICP备案-")
                icp_info = self.get_info_list(pid, "detail/icpinfoAjax")
                for icp_item in icp_info:
                    print(icp_item)
            if s_info['appinfo'] > 0:
                print("-APP信息-")
                info_res = self.get_info_list(pid, "c/appinfoAjax")
                for info_item in info_res:
                    print(info_item)
            if s_info['microblog'] > 0:
                print("-微博信息-")
                info_res = self.get_info_list(pid, "c/microblogAjax")
                for info_item in info_res:
                    print(info_item)
            if s_info['wechatoa'] > 0:
                print("-微信公众号信息-")
                info_res = self.get_info_list(pid, "c/wechatoaAjax")
                for info_item in info_res:
                    print(info_item)
            if s_info['copyrightNum'] > 0:
                print("-软件著作-")
                copyright_info = self.get_info_list(pid, "detail/copyrightAjax")
                for copy_item in copyright_info:
                    print(copy_item['softwareName'])
                    print(copy_item['detail'])
            print("-XX-基本信息END-XX-")
        return s_info

    def get_cm_if(self, name, t=0):
        company = name
        url_prefix = 'https://www.baidu.com/'
        url_a = 'https://aiqicha.baidu.com/s?q=' + company + '&t=0'
        content = self.get_req('./aiqi.html', url_a, url_prefix, False)
        item = self.parse_index(content)
        print(t)
        if t > 3:
            return None
        if item:
            return item
        else:
            return self.get_cm_if(name, t + 1)

    def get_company_info(self, name):
        print("Start")
        item = self.get_cm_if(name)
        if item:
            my = self.get_item_name(item)
            print("查询到公司：" + my[1] + " pid:" + my[0])
            pid = my[0]
            self.get_company_c(pid)
            print("===查分支机构===")
            relations_info = self.get_info_list(pid, "detail/branchajax")
            # print(relations_info)
            for s in relations_info:
                print(s['entName'] + " " + s['openStatus'])
                # self.get_company_c(s['pid'])
            print("===控股公司===")
            holds_info = self.get_info_list(pid, "detail/holdsAjax")
            for s in holds_info:
                print(s['entName'])
                self.get_company_c(s['pid'])
            print("===对外投资===")
            holds_info = self.get_info_list(pid, "detail/investajax")
            for s in holds_info:
                print(s['entName'] + " 状态：" + s['openStatus'] + " 投资比例：" + s['regRate'])
                if s['regRate'] != '-':
                    if float(s['regRate'].replace("%", "")) > 50:
                        self.get_company_c(s['pid'])
        else:
            print("NO_INDEX_ERROR")
            return "NO_INDEX"

    def main(self):
        print("name")
        company = input("")
        info = self.get_company_info(company)
        self.main()


if __name__ == '__main__':
    Scan = EIScan()
    Scan.get_proxy()
    Scan.main()
