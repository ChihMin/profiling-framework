#!/usr/bin/env python

import os, sys
import redis
import argparse

def main():
    parser = argparse.ArgumentParser(description='Dump profiling data from redis DB')
    parser.add_argument('--o', help="output filename")
    parser.add_argument('--port', help="redis db port number")
    args = parser.parse_args()
    file = None

    portnumber = 6379
    if args.port is not None:
        portnumber = int(args.port)
    
    if args.o is not None:
        file = open(args.o, "w")    

    r = redis.Redis(port=portnumber)
    for key in r.keys():
        outputstr = "{%s: %s}" % (key, r.hgetall(key))
        if file is None:
            print(outputstr)
        else:
            file.write(outputstr)
            file.write("\n")

if __name__ == "__main__":
    main()
