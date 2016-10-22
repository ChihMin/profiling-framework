#!/usr/bin/env python

import logging
import socket, os, sys
import argparse
import json

"""
parser = argparse.ArgumentParser(description='Profiling server')
parser.add_argument('--bind', help='Server IP address binder, default is localhost')
parser.add_argument('--port', help='Server port number, default is 10000') 
parser.add_argument('--jobid', help='Redis-DB port number')
args = parser.parse_args()
"""

class ProfClient(object):
    '''
    Below is command type
    '''
    SEND_PERF_DATA = 1
    SEND_BENCHMARK_DATA = 2
    
    def __init__(self, bindaddr, port):
        self.bindaddr = bindaddr
        self.port = port

    def send_data(self, sock, cmdlist):
        for msg in cmdlist:
            jsonstr = json.dumps(msg)
            sock.send(jsonstr)
            feedback = sock.recv(1024)
            if feedback != "ack":
                logging.error("%s" % feedback)
                sys.exit(-1) 

    def run_on_job(self, sock):
        raise NotImplementedError

    def run(self):
        logging.basicConfig(level=logging.INFO)
        logging.info("Link to HOST %s, port %s" % (self.bindaddr, self.port))
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error, msg:
            sys.stderr.write("[ERROR] %s\n" % msg[1])
            sys.exit(1)

        try:
            sock.connect((self.bindaddr, self.port))
        except socket.error, msg:
            sys.stderr.write("[ERROR] %s" % msg)
            exit(1)
        
        self.run_on_job(sock)
        sock.close()

def main():
    portnumber = 10000
    bindaddr = 'localhost'
    
    if args.bind is not None:
        bindaddr = args.bind

    if args.port is not None:
        portnumber = int(args.port)
    
    profclient = ProfClient(bindaddr, portnumber)
    profclient.run()    

if __name__ == "__main__":
    main()
