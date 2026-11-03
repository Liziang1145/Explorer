import json,subprocess,ipaddress
from pathlib import Path
if Path('/sys/class/net/eno1/carrier').read_text().strip()!='1':raise SystemExit()
links=json.loads(subprocess.check_output(['ip','-j','-4','addr','show','dev','eno1']))
if any(ipaddress.IPv4Address(a['local']) in ipaddress.IPv4Network('192.168.137.0/24') for l in links for a in l.get('addr_info',[])):raise SystemExit()
state=subprocess.check_output(['nmcli','-g','GENERAL.STATE','device','show','eno1'],text=True).split()[0]
if state in ('40','50','60','70','80','90'):raise SystemExit()
print('No 137 subnet IPv4; retrying DHCP, refusing bridge management DHCP',flush=True)
subprocess.run(['nmcli','--wait','35','connection','up','uuid','10838d80-caeb-349e-ba73-08ed16d4d666','ifname','eno1'],timeout=40)
