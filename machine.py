import websocket, re
from time import sleep
from ssl import CERT_NONE
from threading import Thread
from urllib.parse import quote
from requests import post, get

class QemuMachine:
    def __init__(self, prox_node, vm_id):
        self.vm = prox_node.qemu(vm_id)
        self.vm_power = False
        self.vm_agent = False
        self._status_power()
        self._status_agent()

    def _status_power(self):
        vm_status = self.vm.status("current").get()
        if vm_status["status"] == "running":
            self.vm_power = True
        else:
            self.vm_power = False
        return self.vm_power

    def _status_agent(self):
        try:
            self.vm.agent("ping").post()
            self.vm_agent = True
        except:
            self.vm_agent = False
        return self.vm_agent

    def run_command(self, cmd):
        if not self._status_power():
            return "-- error: vm power off --"
        if not self._status_agent():
            return "-- error: vm agent not reachable --"
        try:
            cmd_pid = self.vm.agent("exec").post(command=["bash", "-c", f"LANG=C.UTF-8 {cmd}"])["pid"]
        except:
            return "-- error: cant execute program (no pid)"
        while 1:
            sleep(1)
            out = self.vm.agent("exec-status").get(pid=cmd_pid)
            if out["exited"] == 1:
                if "out-data" in out:
                    return out["out-data"]
                if "err-data" in out:
                    return out["err-data"]
                return "-- error: no output --"

class EcoRouter:
    """
    Caution! Console working only with login/password Proxmoxer auth (not api token), internal flaw in termproxy sources.
    Get PVEAuthTicket:
        PVEAuthTicket, CSRFPreventionToken = prox.get_tokens()
    """
    def __init__(self, PVE_DOMAIN, PVE_PORT, PVEAuthTicket, CSRFPreventionToken, node, vm_id, prepare = False):
        router_status = get(f"https://{PVE_DOMAIN}:{PVE_PORT}/api2/json/nodes/{node}/qemu/{vm_id}/status/current", 
                          cookies={"PVEAuthCookie":PVEAuthTicket}, 
                          headers={"CSRFPreventionToken":CSRFPreventionToken}, 
                          verify=False)
        assert router_status.status_code == 200, "Cant get VM status"
        if router_status.json()["data"]["status"] != "running":
            self.router_power = False
            return
        self.router_power = True
        termproxy = post(f"https://{PVE_DOMAIN}:{PVE_PORT}/api2/json/nodes/{node}/qemu/{vm_id}/termproxy", 
                          cookies={"PVEAuthCookie":PVEAuthTicket}, 
                          headers={"CSRFPreventionToken":CSRFPreventionToken}, 
                          verify=False)
        assert termproxy.status_code == 200, "Cant start termproxy websocket"
        termproxy_data = termproxy.json()
        assert "ticket" in termproxy_data["data"], "No ticket in termproxy"
        self.user = termproxy_data["data"]["user"]
        self.port = termproxy_data["data"]["port"]
        self.ticket = termproxy_data["data"]["ticket"]
        self.ws = websocket.WebSocket(sslopt={"cert_reqs":CERT_NONE})
        self.ws.connect(f'wss://{PVE_DOMAIN}:{PVE_PORT}/api2/json/nodes/{node}/qemu/{vm_id}/vncwebsocket?port={self.port}&vncticket={quote(self.ticket)}', 
                        cookie=f"PVEAuthCookie={PVEAuthTicket}", 
                        timeout=5)
        Thread(target=self._ping, name='keep_alive', daemon=True).start()
        self._auth()
        if prepare:
            self.device_prepare()
        

    def _ping(self):
        while 1:
            self.ws.ping("2")
            sleep(15)

    def _auth(self):
        print(f"Auth on console")
        self.ws.send(f"{self.user}:{self.ticket}\n")
        assert "OK" in self._msg_compile(), "Auth not working"

    def device_prepare(self, login="admin", password="admin"):
        """
        Enter device to enable mode, prepare device to SHOW commands.
        You can be pass custom login and password, enable with no password.
        """
        if not self.router_power:
            print("Device is power off")
            return False
        self._send_z()
        self._msg_send("")
        while 1:
            buffer = self._msg_compile()
            if re.search(r"login: $", buffer):
                print(f"Enter login ({login})")
                self._msg_send(login)
            if re.search(r"Password:$", buffer):
                print(f"Enter password ({password})")
                self._msg_send(password)
            if re.search(r"\S>$", buffer):
                print("Try enable")
                self._msg_send("enable")
            if re.search(r"\(.*\)#$", buffer):
                print("Exit to #")
                self._msg_send("end")
            if re.search(r"#$", buffer):
                print("Device is ready")
                return True

    def run_command(self, cmd):
        if not self.router_power:
            print("Device is power off")
            return "--device is power off--"
        self._send_z()
        self._msg_send(cmd)
        return self._msg_compile()

    def _msg_send(self, msg):
        self.ws.send(f"0:{len(msg)+1}:{msg}\n")

    def _msg_compile(self):
        buffer = b""
        while 1:
            try:
                buffer += self.ws.recv()
            except websocket.WebSocketTimeoutException:
                break
        return buffer.decode("utf-8")
    
    def _send_z(self):
        self.ws.send("0:1:\x1A")

    def __exit__(self):
        self.ws.close()