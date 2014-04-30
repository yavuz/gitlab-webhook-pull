#!/usr/bin/env python

import os
import json
import argparse
import BaseHTTPServer
import shlex
import subprocess
import shutil
import logging

logger = logging.getLogger('gitlab-webhook-pull')
logger.setLevel(logging.DEBUG)
logging_handler = logging.StreamHandler()
logging_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                      "%B %d %H:%M:%S"))
logger.addHandler(logging_handler)

repository = 'git@github.com:yavuz/gitlab-webhook-pull.git'

master_branch = "/var/www/master-domain"
test_branch = "/var/www/test-domain"

class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_POST(self):
        logger.info("Received POST request.")
        self.rfile._sock.settimeout(5)
        
        if not self.headers.has_key('Content-Length'):
            return self.error_response()
        
        json_data = self.rfile.read(
            int(self.headers['Content-Length'])).decode('utf-8')

        try:
            data = json.loads(json_data)
        except ValueError:
            logger.error("Unable to load JSON data '%s'" % json_data)
            return self.error_response()

        # merge request
        if data.has_key('object_kind'):
            if data['object_kind'] == 'merge_request':
                self.merge_branch(data['object_attributes']['target_branch'],data['object_attributes']['source_branch'])
        else:   # push request
            branch_to_update = data.get('ref', '').split('refs/heads/')[-1]
            branch_to_update = branch_to_update.replace('; ', '')
            if branch_to_update == '':
                logger.error("Unable to identify branch to update: '%s'" % data.get('ref', ''))
                return self.error_response()
            elif (branch_to_update.find("/") != -1 or branch_to_update in ['.', '..']):
                # Avoid feature branches, malicious branches and similar.
                logger.debug("Skipping update for branch '%s'." % branch_to_update)
            else:
                self.ok_response()
                logger.debug(branch_to_update)
                self.update_branch(branch_to_update)
                return

        self.ok_response()
        logger.info("Finished processing POST request.")


    def merge_branch(self,target_branch,source_branch):
        logger.info("target branch %s" % target_branch)
        logger.info("source branch %s" % source_branch)
        logger.info("merge request")
        self.update_branch(target_branch)
    
    def update_branch(self, branch):
        if branch == "test":
            branch_path = test_branch
        elif branch == "master":
            branch_path = master_branch
        else:
            branch_path = master_branch     #default branch
        os.chdir(branch_path)
        run_command("git pull origin -f %s" % branch)
        logger.info("Updated branch '%s'" % branch_path)
        
    def ok_response(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def error_response(self):
        self.log_error("Bad Request.")
        self.send_response(400)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_command(command):
    logger.debug("Running command: %s" % command)
    process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    process.wait()
    if process.returncode != 0:
        logger.error("Command '%s' exited with return code %s: %s" %
                     (command, process.returncode, process.stdout.read()))
        return ''
    return process.stdout.read()
        
def get_arguments():
    parser = argparse.ArgumentParser(description=(
            'Deploy Gitlab branches in repository to a directory.'))
    parser.add_argument('-p', '--port', default=8000, metavar='8000',
                        help='server address (host:port). host is optional.')
    return parser.parse_args()

def main():
    global repository
    global master_branch
    global test_branch
    
    args = get_arguments()
    address = str(args.port)
    
    if address.find(':') == -1:
        host = '0.0.0.0'
        port = int(address)
    else:
        host, port = address.split(":", 1)
        port = int(port)
    server = BaseHTTPServer.HTTPServer((host, port), RequestHandler)

    logger.info("Starting HTTP Server at %s:%s." % (host, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    logger.info("Stopping HTTP Server.")
    server.server_close()
    
if __name__ == '__main__':
    main()
