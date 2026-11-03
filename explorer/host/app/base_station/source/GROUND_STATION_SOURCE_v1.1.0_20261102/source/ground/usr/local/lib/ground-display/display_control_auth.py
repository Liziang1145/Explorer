"""Dedicated AIPC credential: permits only display-state reads and updates."""
import hmac
from pathlib import Path
TOKEN_FILE=Path('/etc/ground-display/display-control.token')

def authorized(request):
    if request.path!='/api/display' or request.method not in ('GET','POST'):return False
    try:token=TOKEN_FILE.read_text().strip()
    except OSError:return False
    return len(token)>=32 and hmac.compare_digest(request.headers.get('Authorization',''),'Bearer '+token)
