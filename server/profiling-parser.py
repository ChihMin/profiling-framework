#!/usr/bin/env python

import redis
import os, sys
import argparse

parser = argparse.ArgumentParser(description='Profiling database system')
parser.add_argument('--file', help="profiling file path")
parser.add_argument('--port', help="redis DB port number")
args = parser.parse_args()


if args.file is None:
    print("Please input filename!")
    exit(-1)

portnumber = 6379
if args.port is not None:
    portnumber = int(args.port)

print("Current port number is %s, reading date from redis DB..." % portnumber)

r = redis.Redis(port=portnumber)
filename = args.file

file = open(filename, 'r')
while True:
    str = file.readline()
    if len(str) == 0:
        break

    status = str.split()
    nodename = status[6]
    execname = status[7]
    eventname = status[4]
    
    counts = int(status[3])
    origincounts = r.hget(nodename, eventname)
    if origincounts is not None:
        counts = counts + int(origincounts)

    r.hset(nodename, 'execname', execname)
    r.hset(nodename, eventname, counts)

r.save()
file.close()
