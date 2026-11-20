"""Credential initialization must never destroy the original encrypted store."""
from pathlib import Path
import importlib.util
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parents[1] / 'rea/apktool/smali_classes2/com/qinl/car/pub/CredentialManager.smali'
PATTERN = re.compile(r'(?ms)^\.method public final init\(Landroid/content/Context;\)V\n.*?^\.end method')

class CredentialPatchTest(unittest.TestCase):
 def test_init_preserves_store_and_blocks_failed_migration(self):
  self.assertTrue((ROOT / 'credential_patch.py').exists(), 'missing non-destructive credential patch')
  spec = importlib.util.spec_from_file_location('credential_patch', ROOT / 'credential_patch.py')
  module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as temp:
   target = Path(temp) / 'smali_classes2/com/qinl/car/pub/CredentialManager.smali'
   target.parent.mkdir(parents=True)
   original = SOURCE.read_text(encoding='utf-8'); target.write_text(original, encoding='utf-8')
   module.apply(temp)
   updated = target.read_text(encoding='utf-8'); body = PATTERN.search(updated).group()
   self.assertEqual(PATTERN.sub('', original), PATTERN.sub('', updated))
   self.assertNotIn('deleteSharedPreferences', body)
   self.assertNotIn('AppLog;', body)
   self.assertNotIn('getMessage', body)
   self.assertEqual(body.count('->create(Landroid/content/Context;)Landroid/content/SharedPreferences;'), 1)
   self.assertIn('sput-object v1, Lcom/qinl/car/pub/CredentialManager;->prefs:Landroid/content/SharedPreferences;', body)
   failure = body[body.index(':init_failed'):]
   self.assertIn('const-string v1, "storage_unavailable"', failure)
   self.assertIn('sput-object v1, Lcom/qinl/car/pub/CredentialManager;->initError:Ljava/lang/String;', failure)
   self.assertIn('sput-object v0, Lcom/qinl/car/pub/CredentialManager;->prefs:Landroid/content/SharedPreferences;', failure)
   module.apply(temp); self.assertEqual(updated, target.read_text(encoding='utf-8'))

if __name__ == '__main__': unittest.main()
