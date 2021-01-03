<h1 align="center">ENScan 🛠</h1>

<p>
  <img src="https://img.shields.io/badge/Language-Python3-blue" />
  <img src="https://img.shields.io/badge/Version-1.0-blue" />
</p>


## 背景

本项目为 [狼组信息化平台](https://plat.wgpsec.org) 功能项目，内部开源

程序主要对[百度爱企查](aiqicha.baidu.com) API和接口进行封装可获取

- 企业基本信息（法人、电话、公司地址等等）
  - 企业ICP备案号以及网站
  - 企业APP信息
  - 企业微信公众号信息
  - 企业微博信息
  - 子公司的基本信息
- 该企业投资大于51%的企业基本信息（参考上面）

有更多需求可以联系@Keac 师傅提

## 快速使用

1. 安装依赖 (部分依赖有点问题，需要手动安装下)

   `pip install -r requirements.txt`

2. 命令使用

   `python ENScan.py`

   输入关键词即可查询

## API部署

本项目需要运行在Linux/MAC环境下，不支持Windows，使用了任务队列RQ

需要安装配置Redis

`python api.py` (启动 web API)

`python scan_worker.py` (启动扫描端)

