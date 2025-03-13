from proxmoxer import ProxmoxAPI
from machine import QemuMachine, EcoRouter
from time import sleep, time
import argparse
import sys
import json
import re

from urllib3 import disable_warnings, exceptions as urlexceptions
disable_warnings(urlexceptions.InsecureRequestWarning)

# Get args from cli
parser = argparse.ArgumentParser()
parser.add_argument('node', type=str)
parser.add_argument('user_num', type=int)
args = parser.parse_args()
node = args.node
user_num = args.user_num

ROOT_DIR = '/'.join(sys.argv[0].split('/')[0:-1])

TASKS = json.load(open(f"{ROOT_DIR}/m2-2025.json", encoding="utf-8"))
TOPO = TASKS["TOPO"]
TESTS = TASKS["TESTS"]

RESULT_FILE = f"{ROOT_DIR}/result{user_num}-{int(time())}.html"

api_user = "auto@pve"
api_password = ""
PVE_DOMAIN = ""
PVE_PORT = 443
place_vm_shift = 20000

def clear_output(text:str) -> str:
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace("[m", "")
    text = text.replace("[K", "")
    return text

def write_result(result):
	print(result, file=open(RESULT_FILE, "a", encoding="utf-8"))

prox = ProxmoxAPI(PVE_DOMAIN, port=PVE_PORT, user=api_user, password=api_password, verify_ssl=False)
PVEAuthTicket, CSRFPreventionToken = prox.get_tokens()
pve_node = prox.nodes(node)

# Validate tests
for point in TESTS:
    if "vms" in TESTS[point]:
        for vm in TESTS[point]["vms"]:
            assert vm in TOPO, f"Error: check VM name in tests {vm}"
# Prepare vm objects
for index, vm in enumerate(TOPO):
    vm_id = place_vm_shift + int(f"{user_num:02}{index:02}")
    TOPO[vm]["id"] = vm_id
    if TOPO[vm]["type"] == "qemu":
        TOPO[vm]["obj"] = QemuMachine(pve_node, vm_id)
    if TOPO[vm]["type"] == "eco":
        continue
        TOPO[vm]["obj"] = EcoRouter(PVE_DOMAIN, PVE_PORT, PVEAuthTicket, CSRFPreventionToken, node, vm_id, prepare=True)

write_result(f"""
<html>
    <title>User #{user_num}</title>
    <style>code {{ display: block; white-space: pre-wrap; border: 1px solid black; font-family: consolas; }}; </style>
    <style>.navbar {{ display:none; position: fixed; top: 0; right: 0; height: 100%; overflow-y: scroll; background-color: white; padding: 1rem; border: 1px solid black; }}; </style>
    <style>@media print {{ .hidden-print {{ display: none !important; }}}}</style>
    <body>
        <h1>Рабочее место №{user_num}</h1><br>
""")
nav_bar = ""

for point in TESTS:
    if len(point) > 15:
        print(point)
        href_id = int(time())
        write_result(f'<h2 id="{href_id}">{point}</h2>')
        nav_bar += f'<li><a href="#{href_id}">{point[:30]}</a></li>'
    if "comment" in TESTS[point]:
        write_result(TESTS[point]["comment"] + "<br>")
    if "vms" not in TESTS[point]:
        continue
    for vm in TESTS[point]["vms"]:
        write_result(f"<br><b>{vm} ({TOPO[vm]['id']})</b><br>")
        if "cmd" in TESTS[point]:
            for cmd in TESTS[point]["cmd"]:
                write_result(f"<i>{clear_output(cmd)}</i><br>")
                o = TOPO[vm]["obj"].run_command(cmd)
                write_result(f"<code>{clear_output(o)}</code><br>")

write_result(f"<div class=\"navbar hidden-print\"><ul>{nav_bar}</ul></div>")
write_result("</body></html>")