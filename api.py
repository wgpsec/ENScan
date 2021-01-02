import redis
from flask import Flask, request
from rq import Queue
from rq.job import Job

import ENScan

conn = redis.Redis(host='127.0.0.1', password='', port=6379, db=10)  # 指定redis数据库
if __name__ == '__main__':
    app = Flask(__name__)
    Scan = ENScan.EIScan()


    @app.route('/check')
    def hello_world():
        arg = request.args.get("name")

        return str(Scan.check_name(arg))


    q = Queue("high", connection=conn)

    @app.route('/add')
    def add_work():
        arg = request.args.get("name")

        s = q.enqueue_call(Scan.main, args=(arg,))
        print(s.id)
        return str(s.id)


    @app.route('/get')
    def get_work():
        job_id = request.args.get("id")
        job = q.fetch_job(job_id)
        if not job.is_finished:
            return "Not yet", 202
        else:
            return str(job.result)
        pass


    app.run(port=5000)
    app.run()
