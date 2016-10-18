#!/usr/bin/env python

import os, sys
import redis
import argparse

parser = argparse.ArgumentParser(description='Dump profiling data from redis DB')
parser.add_argument('-o', help="output filename")
parser.add_argument('--port', help="redis db port number")
args = parser.parse_args()

portnumber = 6379
if args.port is not None:
    portnumber = int(args.port)

r = redis.Redis(port=portnumber)
for key in r.keys():
    print("{%s: %s}" % (key, r.hgetall(key)))
