import json
from pathlib import Path
root = Path(r'C:\Users\25298\Desktop\FPGA')
text = (root / '01_文档' / '机械部分_参数台账.md').read_text(encoding='utf-8')
code = """(async()=>{const f=new File([%s],'机械部分_参数台账.md',{type:'text/markdown'});const z=await DocumentPageImport.markdownZip(f);return await api('/api/upload',z,true)})()""" % json.dumps(text, ensure_ascii=False)
request = {'action':'evaluate','args':{'code':code},'session':'fpga-ledger-clearance'}
(root / '0000_未处理归档' / 'webbridge-req-doc-upload-06.json').write_text(json.dumps(request, ensure_ascii=False), encoding='utf-8')
