#!/usr/bin/env python

import redis
import os, sys


if len(sys.argv) < 2:
    print("Please input filename!")
    exit(-1)

r = redis.Redis()
filename = sys.argv[1]

file = open(sys.argv[1], 'r')
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
    if origincounts.__class__.__name__ != 'NoneType':
        counts = counts + int(origincounts)

    r.hset(nodename, 'execname', execname)
    r.hset(nodename, eventname, counts)

r.save()
file.close()
