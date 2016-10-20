#!/usr/bin/env python

from multiprocessing import Process
from subprocess import call
import socket
import time
import os, sys
import subprocess
import redis
import signal
import argparse
import json
import logging

class ProfServer(object):
    MAIN_PORT = 2000

    '''
    Below constant value is command type
    '''
    SEND_PERF_DATA = 1
    
    def __init__(self, bindaddr, portnumber):
        self.bindaddr = bindaddr
        self.portnumber = portnumber

    def create_redis_server(self, port):
        if not os.path.exists(port):
            os.mkdir(port)
        
        orgin_path = os.getcwd()
        os.chdir(port)
        cmds = ["redis-server", "--port", port]
        ret = call(cmds, stdout=open(os.devnull, "w"), stderr=subprocess.STDOUT) 
        sys.exit(0)

    def create_server(self, port):
        portnumber = str(port)
        p = Process(target=self.create_redis_server, args=(portnumber,))
        p.start() 
        logging.info("[PID %s] Redis server is created" % p.pid)
        
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

    def parse_perf_data(self, manager, msg):
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
        

    def select_task(self, csock, manager, msg): 
        '''
        Initialize function selector in dictionay
        SEND_PERF_DATA --> parse_perf_data
        '''
        selector = dict()
        selector[ProfServer.SEND_PERF_DATA] = self.parse_perf_data     

        '''
        Just call selector for specific function
        '''
        selector[msg['command']](manager, msg)

    def create_task(self, csock, adr):
        manager = dict()
        manager['csock'] = csock

        while True:
            msg = csock.recv(1024)
            if not msg:
                logging.info("Done! Client %s is closed ..." % csock.getsockname()[0])
                break
            elif len(msg) != 0:
                # print "Client send: " + msg
                msgdict = json.loads(msg)
                self.select_task(csock, manager, msgdict)
                csock.send("ack") # send ack back to client

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
            logging.info("Client Info: %s" , csock.getsockname())
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
