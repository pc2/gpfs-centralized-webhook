#!/usr/bin/env python3

from flask import Flask, request
import socket
import re
import subprocess
import requests
import json
import logging
import time

SERVERHOST="0.0.0.0"
SERVERPORT=8001
#### CLI Wrapper
def _exec(bashCommand,getstderr=False):
        """
        Exec command and return output
        """
        process = subprocess.Popen(bashCommand, stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=True)
        output, error = process.communicate()
        if getstderr:
                return [output.decode(),error.decode(),process.returncode]
        else:
                return output.decode()

#### Hostname resolution
        """ 
        Gets hostname for a given IP from /etc/hosts and returns    hostname or none
        """
def get_hostname_from_ip(ip_address: str) -> str:
        try:
                result = subprocess.run(
                        ["getent", "hosts", ip_address],
                        capture_output=True,
                        text=True,
                        check=True
                )

                output = result.stdout.strip()
                parts = output.split()

                if len(parts) >= 2:
                        return parts[1]  # Zweites Element ist der primäre Hostname

                return None

        except subprocess.CalledProcessError:
                # IP not found
                return None
        except FileNotFoundError:
                # No getent -> Bigger problems ahead
                return None

def check_if_node_in_cluster(host: str) -> bool:
        """
                Checks if given node is member in the GPFS-Cluster
        """
        try:
                        result = subprocess.run(
                                ["/usr/lpp/mmfs/bin/mmlscluster"],
                                capture_output=True,
                                text=True,
                                check=True
                        )

                        if host in result.stdout:
                                return True

        except (subprocess.CalledProcessError, FileNotFoundError):
                        return False

def restoreconfig(host: str) -> bool:
        """
                Executes mmsdrrestore for given node
        """
        try:
                subprocess.run(
                        ["/usr/lpp/mmfs/bin/mmsdrrestore", "-N", host],
                        capture_output=True,
                        check=True
                )
                return True

        except (subprocess.CalledProcessError, FileNotFoundError):
                return False

#### HTTP Server
app = Flask(__name__)
@app.route('/restoreconfig', methods=['GET'])
def handle_restoreconfig():
        """
        Handles checks and executing mmsdrrestore 
        """
        client_ip = request.remote_addr
        logging.info(f"Request from {client_ip}")
        hostname = get_hostname_from_ip(str(client_ip))
        logging.debug(f"{client_ip} resolved to {hostname}")
        
        if check_if_node_in_cluster(hostname):
                logging.debug(f"{hostname} is part of the GPFS-Cluster. Starting mmsdrrestore.")
                if restoreconfig(hostname):
                    logging.debug(f"mmsdrrestore for {hostname} suceeded")
                    return "Done", 200
                else:
                    logging.error(f"mmsdrrestore for {hostname} failed!! Trying again in 5 seconds.")
                    time.sleep(5)
                    if restoreconfig(hostname):
                        logging.error(f"mmsdrrestore for {hostname} failed!! Check node.")
                        return "Failure restoring", 503
        else:
                logging.error(f"{hostname} is not part of the GPFS-Cluster. Either the node is new or something is wrong")
                return "Node not in cluster", 424


logger = logging.getLogger()
gunicorn_logger = logging.getLogger("gunicorn.error")
logger.handlers = gunicorn_logger.handlers
logger.setLevel(logging.DEBUG)

if __name__ == '__main__':
    app.run(host=SERVERHOST, port=SERVERPORT)


