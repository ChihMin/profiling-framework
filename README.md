## Introduction

This framework is used to conveniently collect  profiling and benchmark data from other machine. Sometimes we need to build many versions of executable binary to find the best solution of optimization, but we don't have an easy way to run application benchmark and monitor performance. 

Below contents are information inspected by profiling tools:

- branch-misses
- cache-misses
- cpu-cycles
- instructions
- cpu-clock
- L1-dcache-load-misses
- L1-dcache-loads
- L1-dcache-prefetch-misses 
- L1-dcache-prefetches 
- L1-dcache-store-misses
- L1-dcache-stores
- L1-icache-load-misses
- L1-icache-loads
- iTLB-load-misses
- iTLB-loads

To achieve easier way to run profiling, we propose an **extensible**,**distributed**, **concurrency**, and **high performance**  profiling framework.

## Profiling Framework

![img](https://docs.google.com/drawings/d/1vqONSoFKMXsF33nb0cj8460I_2vFxdbs_Bnzj-WLBYk/pub?w=960&h=720)
- Host Computer 
  - Parse profiling result sent from target computer.
  - Redis key-value database for real-time data streaming. 
  - Store benchmark result
- Target Computer
  - Collect profiling and profiling result and send back to host computer.


## Data Schema

### Profiling 

Below is profiling format and screenshot:

![](https://i.imgur.com/6xumAQ4.png)
Support scalable profiling event, and some node has cache-misses but no branch-misses
- Node Name: string
  - execname: string
  - Cache-misses: integer
  - L1-icache-misses: integer
  - iTLB-load-misses: integer
  - cycles: integer
  - ...
  - ...
### Benchmark
![](https://i.imgur.com/DSnu06D.png)

- JOBID: integer
    - Benchmark: integer $\rightarrow$ current benchmark times
    - number: integer $\rightarrow$ json string
        - Exectime: String
        - cache-misses
        - cycles
        - branch-misses
        - ...

## How to build?

### Environment

Install **redis** on ***server side*** as database to store profiling and benchmark data  

```bash
sudo apt-get install redis
```

### Server 

First, you should prepare a server environment, and run `profiling-server` command to run server. We recommend use `screen` or `tmux` to hang the program on server.

```bash
mkdir ${PROF_SERVER_DIR}
cd ${PROD_SERVER_DIR}

# Default port number is 10000
${PROF_FRAMEWORK_REPO}/profiling-server --bind ${IP_ADDRESS} --port ${PORT_NUMBER}
```

Server screen shot

![](https://i.imgur.com/AKJGvG7.png)

### Client

Client side can be identified by user. Below is **CustomClient** template:
```python
class CustomClient(ProfClient):
    def __init__(self, bindaddr, port):
        super(CustomClient, self).__init__(bindaddr, port)
        
    """
    Implement run_on_job(self) method for idendified behavior.
    Use send_data(sock, cmdlist) to send data to server
    
    return value: command list
    cmdlist: A message list stores dict() type instance

    NOTICE: msg['command'] = XXX must be added to msg dict() object
            Farthermore, XXX must be idendified in server side
    """
    def run_on_job(self):
        """
        Here write your code ....
        """
```
#### Profiling Controller

- Create Job

  ```bash
  profiling-controller \
  	--bind ${HOST_IP_ADDR} \
  	--port ${HOST_PORT} \
  	--jobid ${JOBID} \
  	--cmd CREATE \
  	--info ${YOUR_JOB_DESCRIPTION}
  ```

  - --bind: Used to bind host(server) IP address
  - --port: Specify port number of **host**
  - --jobid: JobID is valid from 2001 to 9999, and cannot be duplicated
  - --cmd: Action desired to send

- Remove Job

  ```bash
  profiling-controller \
  	--bind ${HOST_IP_ADDR} \
  	--port ${HOST_PORT} \
  	--jobid ${JOBID} \
  	--cmd REMOVE
  ```

- Show all jobs in use

  ```bash
  profiling-controller \
  	--bind ${HOST_IP_ADDR} \
  	--port ${HOST_PORT}
  	--cmd LIST
  ```

- Dump benchmark data from server

  ```bash
  profiling-controller \
  	--bind ${HOST_IP_ADDR} \
  	--port ${HOST_PORT} \
  	--jobid ${JOBID} \
  	--cmd SHOW_JOB_BENCHMARK \
  	--file ${OUTPUT_FILE_NAME}
  ```

- Dump profiling data from server

  ```bash
  profiling-controller \
  	--bind ${HOST_IP_ADDR} \
  	--port ${HOST_PORT} \
  	--jobid ${JOBID} \
  	--cmd SHOW_JOB_PROFILING \
  	--file ${OUTPUT_FILE_NAME}
  ```

#### Profiling Client

**NOTICE:** You should **Create a Job** first before run profiling.  

Profiling client is used to collecting data of each function node, and profiling client currently can be identified by user. Below is parse profiling data example:

```cpp
 34     def run_on_job(self, sock):
 35         origindir = os.getcwd()
 36         eventlist = ['cache-misses:u', 'branch-misses:u', 'cpu-cycles:u']
 37         program = "/home/chihmin/llvm-develop/llvm/build/bin/clang++"
 38
 39         f = open("/home/chihmin/llvm-develop/llvm/build/test.log", "r")
 40         while True:
 41             str = f.readline()
 42             if not str:
 43                 break
 44
 45             cmd = str.split()
 46             targetdir = cmd[1]
 47             args = " ".join(['-O3'] + cmd[3:])
 48
 49             os.chdir(targetdir)
 50             self.run_profiling(sock, program, eventlist, args)
 51             os.chdir(origindir)
 52
 53         f.close()
 54
 55     def run_profiling(self, sock, program, eventlist, args):
 56         reportname = "profiling-result.log"
 57         events = ",".join(eventlist)
 58         recordcmd = ("perf record -e %s %s %s" % (events, program, args)).split()
 59         reportcmd = ("perf script").split()
 60         returncode = call(recordcmd, stdout=open(os.devnull, "w"), stderr=subprocess.STDOUT)
```

Sometimes we cannot actually know where the program location is and we don't have the same profiling tool, in this project we use [perf](http://wiki.csie.ncku.edu.tw/embedded/perf-tutorial) as example.  For example, we just put absolute path to executable binary in line 37 and 38. No matter what, just sending message back to server is enough.

Below is `profiling-client` execution method: 

```bash
profiling-client --bind ${PROF_SERVER_ADDRESS} \ 
                 --port ${PROF_SERVER_PORT} \
                 --jobid ${JOB_ID_CREATED_BY_CONTROLLER} 
```
- **Notice**
  Profiling tools will always run in supervisor mode, so please switch user to **root** or use **sudo** to run profiling and benchmark client. 

#### Benchmark Client

Benchmark is used to collect program status in runtime like **timing**, **cycles**, **branch-misses**, **cache-misses**, etc. Below is benchmark client execution method and screenshot. 

```bash
benchmark-client --bind ${PROF_SERVER_ADDRESS} \ 
                 --port ${PROF_SERVER_PORT} \
                 --jobid ${JOB_ID_CREATED_BY_CONTROLLER} 
```
Benchmark Screenshot:

![](https://i.imgur.com/CsSdAvk.png)

##  Current Features

- [x] Use **redis** DB as key-value for profiling data storage
      - [x] Real-time profiling data parsing and storage.
      - [x] Dump key-value data from **redis** storage.
      - [x] Support scalable column(e.g. other perf event) for database.
      - [x] Automatically add new counts of profiling event to old counts.
            	e.g. (old)cache-misses:10 + (new)cache-misses:7 = cache-misses:17

- [x] Server-client data streaming.
      - [x] Implement server side for profiling data receiving.
      - [x] Implement client side for profiling data sending.
      - [x] Automatically find correct data set.
            - [x] Implement hash table to search redis dumped data location
            - [x] Detect the source profiling data and target database

- [x] Support multiple client concurrency execution.

- [x] Support bencmark client.

- [x] Implement profiling-server controller
      - [x] Support identified client job

- [x] Support create/remove new task and new client for profiling

- [x] Support remote control profiling server

- [x] Support dump benchmark or profiling data to client from server.
