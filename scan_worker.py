import redis
from flask import Flask, request
from rq import Worker, Queue, Connection

import Config
import ENScan
from multiprocessing import Pool
pool = Config.pool
conn = redis.Redis(connection_pool=pool, db=10)  # 指定redis数据库


def worker(listen):
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()


if __name__ == '__main__':
    listen = ['high', 'default', 'low']

    try:
        cpu_num = 4
        p = Pool(cpu_num)
        for i in range(cpu_num):
            p.apply_async(worker, args=(listen,))
        p.close()
        p.join()
    except Exception as e:
        print(e)

