import json

import redis
from flask import Flask, request, Response
from rq import Queue
from rq.job import Job

import Config
import ENScan

pool = Config.pool
r = redis.StrictRedis(connection_pool=pool)
conn = redis.Redis(connection_pool=pool, db=10)  # 指定redis数据库
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
        if r.exists("c:im:keyword:" + arg):
            res_ag = json.loads(r.get("c:im:keyword:" + arg))
        else:
            res_ag = Scan.check_name(arg)
            r.set("c:im:keyword:" + arg, json.dumps(res_ag), ex=3600)
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


    @app.route('/getpid')
    def get_pid():
        pid = request.args.get("id")
        d_info = {
            "code": 2000,
            "msg": "No",
            "data": None
        }
        if r.get("c:im:info:" + pid) is not None:
            d_info["data"] = json.loads(r.get("c:im:info:" + pid))
            return Response(json.dumps(d_info), mimetype='application/json')
        else:
            d_info['code'] = 5000
            d_info['msg'] = "No Task"
            return Response(json.dumps(d_info), mimetype='application/json'), 500


    @app.route('/getName')
    def get_name():
        arg = request.args.get("name")
        delS = request.args.get("del")
        print(delS)
        d_info = {
            "code": 2000,
            "msg": "No",
            "data": None
        }
        isHas = False
        if r.exists("c:im:keyword:" + arg):
            isHas = True
            res_ag = json.loads(r.get("c:im:keyword:" + arg))
        else:
            res_ag = Scan.check_name(arg)
            r.set("c:im:keyword:" + arg, json.dumps(res_ag), ex=3600)

        if res_ag is not None:
            if (r.get("c:im:info:" + res_ag[0]) is not None) or isHas:
                if delS is None:
                    print(res_ag[0])
                    if r.exists("c:im:info:" + res_ag[0]):
                        d_info["data"] = json.loads(r.get("c:im:info:" + res_ag[0]))
                    return Response(json.dumps(d_info), mimetype='application/json')
                else:
                    r.delete("c:im:info:" + res_ag[0])
                    r.delete("c:im:keyword:" + arg)
                    return Response(json.dumps(d_info), mimetype='application/json')
            else:
                s = q.enqueue_call(Scan.main, args=(res_ag[0],))
                d_info['code'] = 5000
                d_info['msg'] = "TaskAdd Name:"
                d_info["data"] = {
                    "name": res_ag[1],
                    "pid": res_ag[0],
                    "taskId": s.id
                }
                return Response(json.dumps(d_info), mimetype='application/json')
        else:
            d_info['code'] = 5001
            d_info['msg'] = "No Task"
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
