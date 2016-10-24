#!/usr/bin/env python

from multiprocessing import Process
from subprocess import call
import os, sys, signal
import subprocess
import argparse
import logging
import socket
import signal
import shutil
import redis
import time
import json

class ProfServer(object):
    MAIN_PORT = 2000

    '''
    Below constant value is command type
    '''
    SEND_PERF_DATA = 1
    SEND_BENCHMARK_DATA = 2
    CREATE_JOB = 3
    REMOVE_JOB = 4
    SHOW_ALL_JOB = 5
    SHOW_JOB_INFO = 6
    SHOW_JOB_BENCHMARK = 7
    SHOW_JOB_PROFILING = 8
    
    def __init__(self, bindaddr, portnumber):
        self.bindaddr = bindaddr
        self.portnumber = portnumber

    def create_redis_server(self, port):
        if not os.path.exists(port):
            os.mkdir(port)
        
        orgin_path = os.getcwd()
        os.chdir(port)
        cmds = ["redis-server", "--port", port]
        proc = subprocess.Popen(cmds, stdout=open(os.devnull, "w"), stderr=subprocess.STDOUT)
         
        logging.info("[PID %s] Redis server is created" % proc.pid)
        if int(port) != ProfServer.MAIN_PORT:
            r = redis.Redis(port=ProfServer.MAIN_PORT)
            r.hset(port, 'pid', proc.pid)
        
        proc.wait()
        logging.warning("[PID %s] is terminated, if this is first time to execute server, please killall redis-server" % proc.pid)
        sys.exit(0)

    def create_server(self, port):
        portnumber = str(port)
        p = Process(target=self.create_redis_server, args=(portnumber,))
        p.start() 
        
        r = redis.Redis(port=portnumber)
        while True:
            try:
                logging.info("[PID %s] Start connecting to port %s ..." % (p.pid, portnumber))
                time.sleep(1)
                r.ping()
            except redis.exceptions.ConnectionError:
                logging.error("[PID %s] Connected to port %s failed, restarting ..." % portnumber)
                pass
            else:
                logging.info("Connected successfully!")
                break  
        return p

    def redis_initialize(self, r):
        portlist = r.keys()
        for port in portlist:
            proc = self.create_server(port)

    def initialize(self):
        logging.info("Booting redis-DB manager ...")
        self.create_server(ProfServer.MAIN_PORT)    # Create redis-server manager
        
        redis_manager = redis.Redis(port=ProfServer.MAIN_PORT)
        self.redis_initialize(redis_manager)          # Initialized profiling DB
    
    def update_redis_manager(self, manager, msg):
        perf_data = msg['message']
        portnumber = msg['port']
        
        if manager.get('redis') is None:
            newredis = redis.Redis(port=portnumber)
            try:
                newredis.ping()
            except redis.exceptions.ConnectionError:
                logging.error("[PID %s] Unknown port %s" % (os.getpid(), portnumber))
                csock = manager['csock']
                csock.send("Unknown port %s" % (portnumber))
                sys.exit(-1)
            
            newredis.bgsave()
            manager['redis'] = newredis
    
    def ping_to_redis_db(self, csock, r, name):
        try:
            r.ping()
        except redis.exceptions.ConnectionError:
            logging.error("[PID %s] %s is dead ..." % (os.getpid(), name))
            csock = manager['csock']
            csock.send("%s IS DEAD!" % (name))
            sys.exit(-1)

    def parse_perf_data(self, manager, msg):
        self.update_redis_manager(manager, msg)
        
        perf_data = msg['message']
        portnumber = msg['port']
        r = manager['redis']  

        status = perf_data.split()
        nodename = status[6]
        execname = status[7]
        eventname = status[4]
        
        counts = int(status[3])
        origincounts = r.hget(nodename, eventname)
        if origincounts is not None:
            counts = counts + int(origincounts)

        r.hset(nodename, 'execname', execname)
        r.hset(nodename, eventname, counts)
        
    def parse_benchmark_data(self, manager, msg):
        benchmark_data = msg['message']
        portnumber = msg['port']
        
        csock = manager['csock']  
        mainredis = manager['mainredis']
        try:
            mainredis.ping()
        except redis.exceptions.ConnectionError:
            logging.error("[PID %s] MAIN port is dead ..." % (os.getpid()))
            csock = manager['csock']
            csock.send("MAIN PORT IS DEAD!")
            sys.exit(-1)
        
        if len(mainredis.hgetall(portnumber)) == 0:
            logging.error("[PID %s] Cannot find Job %s!" % (os.getpid(), portnumber))
            csock.send("Cannot find Job %s!" % (portnumber))
            sys.exit(-1)
        else:
            bench_counts = int(mainredis.hget(portnumber, 'benchmark'))
            mainredis.hset(portnumber, bench_counts, benchmark_data)
            mainredis.hset(portnumber, 'benchmark', bench_counts + 1)
    
    def sync_data_to_db(self, r):
        while True:
            try:
                r.save()
            except:
                time.sleep(1)
                pass
            else:
                break
        
         
    def remove_job(self, manager, msg):
        r = manager['mainredis']
        csock = manager['csock']
        self.ping_to_redis_db(csock, r, "MAIN PORT")

        jobID = msg['jobid']
        if r.exists(jobID):
            pid = int(r.hget(jobID, 'pid'))
            os.kill(pid, signal.SIGTERM)
            shutil.rmtree(jobID)
            r.delete(jobID)
            self.sync_data_to_db(r)
            logging.info("[DELETE] Process ID - %s" % pid)
            csock.send("[JOB %s] Remove successfully!" % jobID)
        else:
            csock.send("[JOB %s] is NOT in use" % jobID)
        ack = csock.recv(1024)
        csock.send("endofmsg")
            
    def create_job(self, manager, msg):
        r = manager['mainredis']
        csock = manager['csock']
        self.ping_to_redis_db(csock, r, "MAIN PORT")
        
        jobID = msg['jobid']
        if len(r.keys(jobID)) != 0:
            csock.send("[JOB %s] is in use ...\n" % jobID)
            logging.info("[JOB %s] is in use ..." % jobID)
        elif int(jobID) <= 2000 or int(jobID) >= 10000:
            errmsg = "Please choose form 2001 to 9999 as jobID"
            csock.send(errmsg)
        else:
            r.hset(jobID, 'info', msg['info'])
            r.hset(jobID, 'benchmark', 0)
            self.create_server(jobID)
            self.sync_data_to_db(r)
            returninfo = "[JOB %s] is created ..." % jobID
            logging.info(returninfo)
            csock.send(returninfo)
        ack = csock.recv(1024)
        csock.send("endofmsg")

    def show_all_job(self, manager, msg):
        csock = manager['csock']
        r = manager['mainredis']
        self.ping_to_redis_db(csock, r, "MAIN PORT")

        joblist = r.keys()
        for jobID in joblist:
            benchmark_data_number = r.hget(jobID, 'benchmark')
            information = r.hget(jobID, 'info')
            
            returnmsg = "JOBID: %s\t Info: %s\t Number of benchmark data: %s\n" % (
                jobID, information, benchmark_data_number
            )
            csock.send(returnmsg)
            ack = csock.recv(1024)
        csock.send("endofmsg")  
    
    def show_job_benchmark(self, manager, msg):
        csock = manager['csock']
        r = manager['mainredis']
        self.ping_to_redis_db(csock, r, "MAIN PORT")
        
        jobID = msg['jobid']
        benchID = 0
        while True:
            benchmark_data = r.hget(jobID, benchID)
            if not benchmark_data:
                break
            csock.send(benchmark_data + "\n")
            ack = csock.recv(1024)
            benchID = benchID + 1
        csock.send("endofmsg")
    
    def show_job_profiling(self, manager, msg):
        csock = manager['csock']
        jobID = msg['jobid']
        r = redis.Redis(port=int(jobID))
        self.ping_to_redis_db(csock, r, "JOB %s" % jobID)
        
        nodes = r.keys()
        for nodename in nodes:
            table = dict()
            returnmsg = json.dumps({nodename: r.hgetall(nodename)})
            csock.send(returnmsg + "\n")
            ack = csock.recv(1024)
        csock.send("endofmsg")

    def select_task(self, csock, manager, msg): 
        '''
        Initialize function selector in dictionay
        SEND_PERF_DATA --> parse_perf_data
        '''
        selector = dict()
        selector[ProfServer.SEND_PERF_DATA] = self.parse_perf_data
        selector[ProfServer.SEND_BENCHMARK_DATA] = self.parse_benchmark_data
        selector[ProfServer.REMOVE_JOB] = self.remove_job
        selector[ProfServer.CREATE_JOB] = self.create_job
        selector[ProfServer.SHOW_ALL_JOB] = self.show_all_job    
        selector[ProfServer.SHOW_JOB_BENCHMARK] = self.show_job_benchmark
        selector[ProfServer.SHOW_JOB_PROFILING] = self.show_job_profiling

        '''
        Just call selector for specific function
        '''
        idx = msg['command']
        selector[idx](manager, msg)
 
    def create_task(self, csock, adr):
        mainredis = redis.Redis(port=ProfServer.MAIN_PORT)
        mainredis.bgsave()
        
        manager = dict()
        manager['csock'] = csock
        manager['mainredis'] = mainredis

        while True:
            msg = csock.recv(1024)
            if not msg:
                logging.info("Done! Client %s is closed ..." % csock.getsockname()[0])
                break
            elif len(msg) != 0:
                csock.send("ack") # send ack back to client
                # print "Client send: " + msg
                msgdict = json.loads(msg)
                self.select_task(csock, manager, msgdict)

        csock.close()
        sys.exit(0) 

    def run(self):
        self.initialize()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error, msg:
            sys.stderr.write("[ERROR] %s\n" % msg[1])
            sys.exit(-1)
        
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.bindaddr, self.portnumber))
        sock.listen(100)
        
        while True:
            (csock, adr) = sock.accept()
            logging.info("Client Info: %s", csock.getsockname())
            p = Process(target=self.create_task, args=(csock, adr,)) 
            p.start()


def keyboard_int_handler(signal, frame):
    logging.info("[PID %s] Stop profiling server ..." % os.getpid())
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description='Profiling server')
    parser.add_argument('--bind', help='Server IP address binder, default is localhost')
    parser.add_argument('--port', help='Server port number, default is 10000') 
    args = parser.parse_args()

    portnumber = 10000
    bindaddr = 'localhost'
    
    if args.bind is not None:
        bindaddr = args.bind

    if args.port is not None:
        portnumber = int(args.port)
    
    logging.basicConfig(level=logging.INFO)
    logging.info("Bind addres is %s, port is %s" % (bindaddr, portnumber)) 
    signal.signal(signal.SIGINT, keyboard_int_handler)
    
    profserver = ProfServer(bindaddr, portnumber)
    profserver.run()   

if __name__ == "__main__":
    main()
