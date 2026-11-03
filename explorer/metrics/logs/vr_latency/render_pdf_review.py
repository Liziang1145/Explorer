from pathlib import Path
import pypdfium2 as pdfium
from PIL import Image,ImageOps,ImageDraw
from zipfile import ZipFile
from lxml import etree as E
import hashlib,json

base=Path(__file__).resolve().parent
review=base/'render_review'
pdf=pdfium.PdfDocument(str(review/'reference.pdf'))
pages=[];index=[]
for i in range(len(pdf)):
    page=pdf[i]
    text=page.get_textpage().get_text_range()
    im=page.render(scale=1.5).to_pil().convert('RGB')
    path=review/f'page-{i+1:02}.png';im.save(path)
    pages.append(path)
    index.append({'page':i+1,'text':text})
for start in range(0,len(pages),4):
    canvas=Image.new('RGB',(1280,1830),'#cccccc')
    for j,path in enumerate(pages[start:start+4]):
        im=Image.open(path)
        im.thumbnail((620,865))
        x=(j%2)*640+(640-im.width)//2;y=(j//2)*915+35
        canvas.paste(im,(x,y))
        ImageDraw.Draw(canvas).text(((j%2)*640+12,(j//2)*915+10),f'PAGE {start+j+1}',fill='black')
    canvas.save(review/f'contact-{start//4+1:02}.png')
(review/'page-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
for row in index:
    if any(x in row['text'] for x in ['表3.3','表3.4','表3.5','表1.1','148.08','215/215','待核实','表B.2','E07','E14']):
        print('REVIEW_PAGE',row['page'],row['text'][:80].replace('\r',' ').replace('\n',' '))

s=Path('C:/Users/25298/Desktop/探路者_竞赛技术文档V1.5.docx')
t=Path('C:/Users/25298/Desktop/FPGA/01_文档/探路者_竞赛技术文档V1.5_数据更新参考稿.docx')
with ZipFile(s) as a,ZipFile(t) as b:
    media=[n for n in a.namelist() if n.startswith('word/media/') and not n.endswith('/')]
    other_media=[n for n in b.namelist() if n.startswith('word/media/') and not n.endswith('/')]
    assert sorted(hashlib.sha256(a.read(n)).hexdigest() for n in media)==sorted(hashlib.sha256(b.read(n)).hexdigest() for n in other_media)
    ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
    aa=E.fromstring(a.read('word/document.xml'));bb=E.fromstring(b.read('word/document.xml'))
    assert len(aa.findall('.//m:oMath',ns))==len(bb.findall('.//m:oMath',ns))
    print('PRESERVED_MEDIA',len(media),'PRESERVED_MATH',len(aa.findall('.//m:oMath',ns)))
print('PAGES',len(pdf),'CONTACT_SHEETS',(len(pdf)+3)//4)
