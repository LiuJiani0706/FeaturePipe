import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile


spec=importlib.util.spec_from_file_location('import_interviews',Path(__file__).resolve().parents[1]/'scripts/import_interviews.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ImportTests(unittest.TestCase):
    def test_text_breaks_tables_and_deleted_material(self):
        xml='''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
        <w:p><w:r><w:t>受访者</w:t><w:tab/><w:t>甲</w:t><w:br/><w:t>保留内容</w:t></w:r><w:del><w:r><w:t>已删内容</w:t></w:r></w:del></w:p>
        <w:del><w:p><w:r><w:t>整段删除</w:t></w:r></w:p></w:del>
        <w:tbl><w:tr><w:tc><w:p><w:r><w:t>表格文字</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
        </w:body></w:document>'''
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'interview.docx'
            with ZipFile(path,'w') as archive:
                archive.writestr('word/document.xml',xml)
                archive.writestr('word/media/image1.png',b'test-placeholder')
            text,media=module.docx_text(path)
        self.assertEqual(text,'受访者\t甲\n保留内容\n表格文字')
        self.assertEqual(media,1)
