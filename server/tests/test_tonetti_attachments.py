import base64
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import tonetti
import tonetti_attachments as a
from PIL import Image

class Attachments(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
 def put(self,name,raw):return a.upload(self.root,{'name':name,'data':base64.b64encode(raw).decode()},tonetti.storage.connect)[0]
 def test_text_private_roundtrip_and_reject_paths(self):
  item=self.put('nota.md',b'**Hola Tone**');row,path=a.get(self.root,item['id'],tonetti.storage.connect)
  self.assertEqual(path.read_bytes(),b'**Hola Tone**');self.assertEqual(path.stat().st_mode&0o777,0o600)
  self.assertIn('Hola Tone',a.context(self.root,[item['id']],tonetti.storage.connect)[0])
  for name in ['../escape.txt','x\n.txt','folder/file.txt','app.exe']:
   with self.assertRaises(ValueError):self.put(name,b'test')
  for ident in ['../escape','x'*32]:
   with self.assertRaises(ValueError):a.get(self.root,ident,tonetti.storage.connect)
 def test_photo_is_resized_jpeg_and_available_to_openclaw_bridge(self):
  out=io.BytesIO();Image.new('RGB',(2000,1000),'red').save(out,'PNG')
  item=self.put('foto.png',out.getvalue());row,path=a.get(self.root,item['id'],tonetti.storage.connect,True)
  with Image.open(path) as image:self.assertEqual(image.format,'JPEG');self.assertLessEqual(max(image.size),1280)
  import openclaw_tonetti
  prompt=openclaw_tonetti._attachment_prompt(self.root,[item['id']],lambda ids:a.context(self.root,ids,tonetti.storage.connect))
  self.assertIn(str(self.root/'attachments'/(item['id']+'.jpg')),prompt)
  self.assertIn('view_image',prompt)
 def test_invalid_image_pdf_and_binary_text_rejected(self):
  for name,raw in [('bad.jpg',b'not image'),('bad.pdf',b'not pdf'),('binary.txt',b'\x00')]:
   with self.assertRaises(ValueError):self.put(name,raw)
 def test_docx_plain_text_only(self):
  import zipfile
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Documento Tone</w:t></w:r></w:p></w:document>')
  item=self.put('test.docx',out.getvalue());self.assertIn('Documento Tone',a.context(self.root,[item['id']],tonetti.storage.connect)[0])
 def test_pdf_without_text_is_not_claimed_read(self):
  from pypdf import PdfWriter
  out=io.BytesIO();writer=PdfWriter();writer.add_blank_page(100,100);writer.write(out)
  with self.assertRaises(ValueError):self.put('scan.pdf',out.getvalue())
 def test_text_pdf_extracted(self):
  from pypdf import PdfWriter
  from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
  writer=PdfWriter();page=writer.add_blank_page(300,300)
  font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
  page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
  stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 20 250 Td (Informe Tone: prueba local) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream)
  out=io.BytesIO();writer.write(out);item=self.put('informe.pdf',out.getvalue());self.assertIn('Informe Tone',a.context(self.root,[item['id']],tonetti.storage.connect)[0])
 def test_attachment_is_linked_and_cannot_be_silently_reused(self):
  item=self.put('nota.txt',b'Un dato para Tone')
  with patch.object(tonetti,'ROOT',self.root),patch.object(tonetti.service,'generate',return_value=('Recibido',[])):
   self.assertEqual(tonetti.start({'message':'Lee esto','attachments':[item['id']]})[1],202)
   self.assertTrue(tonetti._LOCK.acquire(timeout=4));tonetti._LOCK.release()
   messages=tonetti.snapshot()['messages'];self.assertEqual(messages[0]['attachments'][0]['name'],'nota.txt')
   with self.assertRaises(ValueError):tonetti.start({'message':'otra vez','attachments':[item['id']]})
   self.assertFalse(tonetti._LOCK.locked())
 def test_backup_preserves_original_and_detects_corruption(self):
  item=self.put('test.txt',b'Conservar documento');destination=self.root/'backup'
  self.assertEqual(a.backup_files(self.root,destination),1);self.assertEqual(a.backup_files(self.root,destination),1)
  copy=destination/(item['id']+'.original');self.assertEqual(copy.read_bytes(),b'Conservar documento')
  copy.write_bytes(b'corrupt')
  with self.assertRaises(ValueError):a.backup_files(self.root,destination)
  self.assertEqual(a.get(self.root,item['id'],tonetti.storage.connect)[1].read_bytes(),b'Conservar documento')
