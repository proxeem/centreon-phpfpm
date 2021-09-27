#!/usr/bin/env python

#
# Copyright 2021 Proxeem (https://www.proxeem.fr/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Specials thanks to A. Razanajatovo for this great work
# mailto: arazanajatovo.dev@gmail.com
#


import os
import argparse
import subprocess
import shlex
import json
import hashlib
from time import time


#
# Cache manager
#
def getRequestPerSec(curlStats, url):

    fileName = 'phpfpm_pool_' + hashlib.md5(url.encode()).hexdigest()
    filePath = args.cachepath + '/' + fileName

    dataJson = '{\n'
    dataJson += '\t"request": ' + str(curlStats['stats']['accepted conn']) + ',\n'
    dataJson += '\t"timestamp": ' + str(curlStats['timestamp']) + '\n'
    dataJson += '}'

    if os.path.isfile(filePath):
        f = open(filePath, "r")
        lastValues = json.loads(f.read())
        f.close()

        f = open(filePath, "w")
        f.write(dataJson)
        f.close()

        if lastValues['request'] > curlStats['stats']['accepted conn']:
            lastValues['request'] = 0

        requestDiff = curlStats['stats']['accepted conn'] - lastValues['request']
        timestampDiff = curlStats['timestamp'] - lastValues['timestamp']
        result = float(requestDiff) / float(timestampDiff)

        return '{:.2f}'.format(result)

    else:
        f = open(filePath, "w")
        f.write(dataJson)
        f.close()
        return None


#
# HTTP request to get the pool list with an external CURL command
#
def getPoolList():

    curlURL = args.proto + '://' + args.hostname + '/' + args.urlpath
    curlCommand = subprocess.Popen(shlex.split(
        'curl -s -w "|%{http_code}" -m ' + args.timeout + ' ' + curlURL),
        stdout = subprocess.PIPE)
    curlOutput, curlError = curlCommand.communicate()
    curlOutput = curlOutput.decode("utf-8")

    curlValues = curlOutput.split('|')
    statusCode = int(curlValues[1])

    if 200 != statusCode:
        return {
            'pool_list': None,
            'status_code': statusCode
        }

    else:
        curlList = json.loads(curlValues[0])
        return {
            'pool_list': curlList,
            'status_code': int(curlValues[1])
        }


#
# HTTP request to get PHP FPM stats with an external CURL command
#
def getPhpFpmStats(curlURL):

    curlCommand = subprocess.Popen(shlex.split(
        'curl -s -w "|%{http_code}" -m ' + args.timeout + ' ' + curlURL + '?json'),
        stdout = subprocess.PIPE)
    curlOutput, curlError = curlCommand.communicate()
    curlOutput = curlOutput.decode("utf-8")

    curlValues = curlOutput.split('|')
    statusCode = int(curlValues[1])

    if 200 != statusCode:
        return {
            'stats': None,
            'timestamp': None,
            'status_code': statusCode
        }

    else:
        curlStats = json.loads(curlValues[0])
        return {
            'stats': curlStats,
            'timestamp': int(time()),
            'status_code': statusCode
        }


# Parse command line
parser = argparse.ArgumentParser(description = 'PHP FPM plugin for Centreon')
parser.add_argument('-d', '--debug', help = 'Output debug information (do not use with Centreon)', action = 'store_true')
parser.add_argument('--proto', help = 'Protocol', required=True)
parser.add_argument('--hostname', help = 'Hostname', required=True)
parser.add_argument('--urlpath', help = 'Relative URL', required=True)
parser.add_argument('--cachepath', help = 'Cache path', default='/var/lib/centreon/centplugins')
parser.add_argument('--timeout', help = 'Request timeout', default='30')
args = parser.parse_args()

# Retrive datas from pools list
curlPoolList = getPoolList()
if 200 == curlPoolList['status_code']:
    poolList = curlPoolList['pool_list']
    centreonStatusMessage = 'OK: '
    centreonStatusMessageDetails = ''
    centreonStatusMessagePiped = ' | '
    centreonStatusCode = 0

    for pool in poolList:
        curlStats = getPhpFpmStats(poolList[pool])
        if 200 == curlStats['status_code']:
            requestPerSec = getRequestPerSec(curlStats, poolList[pool])
            if requestPerSec != None:
                centreonStatusMessagePiped += "'" + pool + "'=" + str(requestPerSec) + "/s;;;0; "

    centreonStatusMessageDetails += 'All pools OK'
    centreonStatusMessage += centreonStatusMessageDetails + centreonStatusMessagePiped

else:
    centreonStatusMessage = 'UNKNOWN: [' + str(curlPoolList['status_code']).zfill(3) + '] Invalid response code'
    centreonStatusCode = 3

# Output Centreon datas
print(centreonStatusMessage)
exit(centreonStatusCode)
