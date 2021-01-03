import json

import redis
from flask import Flask, request, Response
from rq import Queue
from rq.job import Job

import ENScan

conn = redis.Redis(host='127.0.0.1', password='', port=6379, db=10)  # 指定redis数据库
if __name__ == '__main__':
    app = Flask(__name__)
    Scan = ENScan.EIScan()


    @app.route('/')
    def index():
        d_info = {
            "code": 4003,
            "msg": "No",
            "data": None
        }
        Scan.check_proxy()
        return Response(json.dumps(d_info), mimetype='application/json'), 403


    @app.route('/check')
    def check_info():
        arg = request.args.get("name")
        res_ag = Scan.check_name(arg)
        res_info = {
            "name": res_ag[1],
            "pid": res_ag[0]
        }
        d_info = {
            "code": 2000,
            "msg": "No",
            "data": res_info
        }
        return Response(json.dumps(d_info), mimetype='application/json')


    q = Queue("high", connection=conn)


    @app.route('/add')
    def add_work():
        arg = request.args.get("name")
        s = q.enqueue_call(Scan.main, args=(arg,))
        print(s.id)
        d_info = {
            "code": 2000,
            "msg": "add ok",
            "data": s.id
        }
        return Response(json.dumps(d_info), mimetype='application/json')


    @app.route('/get')
    def get_work():
        job_id = request.args.get("id")
        job = q.fetch_job(job_id)
        d_info = {
            "code": 2000,
            "msg": "No",
            "data": None
        }
        if job is None:
            d_info['code'] = 5000
            d_info['msg'] = "No Task"
            return Response(json.dumps(d_info), mimetype='application/json'), 500

        if job.get_status() == 'failed':
            d_info['code'] = 5000
            d_info['msg'] = "Failed"
            return Response(json.dumps(d_info), mimetype='application/json'), 500
            pass
        if not job.is_finished:
            d_info['code'] = 2002
            d_info['msg'] = "Not OK"
            return Response(json.dumps(d_info), mimetype='application/json'), 202
        else:
            d_info["data"] = job.result
            return Response(json.dumps(d_info), mimetype='application/json')
        pass


    app.run(port=5000)
    app.run()
