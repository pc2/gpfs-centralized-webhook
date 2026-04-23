#!/usr/bin/env python3

from flask import Flask, request
import socket
import re
import subprocess
import requests
import json
import logging
import time

SERVERHOST = "0.0.0.0"
SERVERPORT = 8001


def get_hostname_from_ip(ip_address: str) -> str:
    """
    Gets hostname for a given IP from /etc/hosts and returns hostname or none
    """
    try:
        result = subprocess.run(
            ["getent", "hosts", ip_address], capture_output=True, text=True, check=True
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
            check=True,
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
            check=True,
        )
        return True

    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


#### HTTP Server
app = Flask(__name__)


@app.route("/restoreconfig", methods=["GET"])
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
            # Restore can fail on the first try, try again in a few seconds
            logging.error(
                f"mmsdrrestore for {hostname} failed!! Trying again in 5 seconds."
            )
            time.sleep(5)
            # Restore again
            if not restoreconfig(hostname):
                # Restore failed the second time, call quits.
                logging.critical(f"mmsdrrestore for {hostname} failed!! Calling quits. Check node and GPFS.")
                return "Failure restoring", 503
    else:
        logging.error(
            f"{hostname} is not part of the GPFS-Cluster. Either the node is new or something is wrong"
        )
        return "Node not in cluster", 424


if __name__ == "__main__":
    logger = logging.getLogger()
    logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%d.%m.%Y %H:%M:%S", level=logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    logging.info("App running with development Server, using console logger and logging everything .")
    app.run(host=SERVERHOST, port=SERVERPORT)
elif __name__ == "gpfs-webhook":
    logger = logging.getLogger()
    gunicorn_logger = logging.getLogger("gunicorn.error")
    logger.handlers = gunicorn_logger.handlers
    logger.setLevel(logging.INFO)
    logging.info("App running with Gunicorn, using Gunicorn Logger.")