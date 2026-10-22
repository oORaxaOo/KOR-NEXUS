#!/usr/bin/env python3
import importlib.util, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.simulation import simulate_resource_runway
class AdvancedFeatureTests(unittest.TestCase):
    def test_runway(self):
        result=simulate_resource_runway(5,3,10)
        self.assertEqual([x["remaining_stock"] for x in result],[7.0,4.0,1.0,0.0])
        self.assertEqual(result[-1]["status"],"KRITISCH")
    def test_invalid_runway_inputs(self):
        for args in [(-1,1,2),(2,-1,2),(2,1,float("inf")),(True,1,2)]:
            with self.assertRaises(ValueError): simulate_resource_runway(*args)
    def test_importer_imports_without_downloading(self):
        path=Path(__file__).parent/"import-bkg-data.py"
        spec=importlib.util.spec_from_file_location("bkg_importer",path)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertTrue(module.BKG_URL.startswith("https://daten.gdz.bkg.bund.de/"))
        self.assertEqual(len(module.STATE_NAMES),16)
    def test_mesh_is_disabled_initially(self):
        from core import mesh
        mesh.stop()
        self.assertFalse(mesh.status()["enabled"])
if __name__=="__main__": unittest.main()
