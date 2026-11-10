"""Architecture and portable-export checks; no simulator or synthesis required."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/gen"))
from flavor.generate import archive, generate, identities, verify_bundle
from flavor.model import FlavorError, catalog, dumps, parse, resolve, starter, validate


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.document = starter()

    def test_nested_toml_roundtrip(self):
        self.document["cluster"]["tiles"][0]["parameters"] = {"RF_DEPTH": 16}
        self.document["cluster"]["tiles"][3]["parameters"] = {"FIFO_PROTECTION": 2}
        self.assertEqual(parse(dumps(self.document)), self.document)

    def test_legacy_descriptor_import(self):
        self.assertEqual(parse(dumps(self.document["cluster"])), self.document)

    def test_quoted_keys_and_unicode_in_drafts(self):
        draft = {'key."\n': 'quote " · emoji 🧩\n\\', "array": [True, 3, "x"]}
        self.assertEqual(tomllib.loads(dumps(draft)), draft)
        with self.assertRaises(FlavorError):
            dumps({"unsupported": 1.5})

    def test_invalid_syntax_and_schema(self):
        for text in ('[broken', 'schema = "wrong"'):
            with self.subTest(text=text), self.assertRaises(FlavorError):
                parse(text)

    def test_per_instance_parameters_and_input_immutability(self):
        tile = self.document["cluster"]["tiles"][0]
        tile["parameters"] = {"RF_DEPTH": 32, "FU_PROFILE": 2}
        before = deepcopy(self.document)
        resolved, _ = resolve(self.document)
        self.assertEqual(resolved["cluster"]["tiles"][0]["parameters"]["RF_DEPTH"], 32)
        self.assertEqual(resolved["cluster"]["tiles"][1]["parameters"]["RF_DEPTH"], 8)
        self.assertEqual(self.document, before)

    def test_independent_fu_flags_and_legacy_defaults(self):
        types = {item["id"]: item for item in catalog()["tile_classes"]}
        for kind, item in types.items():
            for unit in item["functional_units"]:
                flag = unit["activation_parameter"]
                document = deepcopy(self.document)
                tile = document["cluster"]["tiles"][0]
                tile.update({"class": kind, "parameters": {flag: 0}})
                baseline, _ = resolve(document)
                tile["parameters"][flag] = 1
                enabled, _ = resolve(document)
                before = baseline["cluster"]["tiles"][0]["parameters"]
                after = enabled["cluster"]["tiles"][0]["parameters"]
                self.assertEqual({key for key in before if before[key] != after[key]}, {flag})
                self.assertEqual(parse(dumps(document)), document)
        tile = self.document["cluster"]["tiles"][0]
        tile.update({"class": "SFT", "parameters": {"FU_PROFILE": 0,
                    "ENABLE_RECIPROCAL": 1, "ENABLE_POLYNOMIAL": 0}})
        resolved, _ = resolve(self.document)
        p = resolved["cluster"]["tiles"][0]["parameters"]
        self.assertEqual((p["ENABLE_RECIPROCAL"], p["ENABLE_POLYNOMIAL"], p["ENABLE_RSQRT"]),
                         (1, 0, 0))
        tile["parameters"] = {"FU_PROFILE": 3}
        resolved, _ = resolve(self.document)
        self.assertEqual(resolved["cluster"]["tiles"][0]["parameters"]["ENABLE_EXPONENTIAL"], 1)

    def test_guidance_covers_each_configuration(self):
        data = catalog()
        self.assertTrue({"rows", "cols", "scratchpad_banks", "scratchpad_bank_words",
                         "clock_gating", "tile_id"} <= data["configuration_guidance"].keys())
        self.assertIn("qualitative", data["guidance_scope"])
        for tile in data["tile_classes"]:
            self.assertTrue(tile["guidance"]["implications"])
            for unit in tile["functional_units"]:
                self.assertTrue(unit["enabled"])
                self.assertTrue(unit["disabled"])
            for name, spec in tile["parameters"].items():
                with self.subTest(tile=tile["id"], parameter=name):
                    self.assertTrue(spec["description"])
                    self.assertTrue(spec["implications"])
                    self.assertNotIn("elaboration-time setting", spec["description"])
                    self.assertTrue(set(spec.get("unavailable_choices", {})) <=
                                    {str(value) for value in spec["choices"]})

    def test_unreleased_circular_mst_mode_is_rejected(self):
        self.document["cluster"]["tiles"][3]["parameters"] = {"SUPPORT_CIRCULAR": 1}
        result = validate(self.document)
        self.assertFalse(result["valid"])
        self.assertEqual(result["issues"][0]["tile_id"], 3)
        self.assertIn("unreleased MST adapter", result["issues"][0]["message"])
        tile = next(t for t in catalog()["tile_classes"] if t["id"] == "MST")
        self.assertIn("1", tile["parameters"]["SUPPORT_CIRCULAR"]["unavailable_choices"])

    def test_parameter_errors_locate_the_tile(self):
        for parameters in ({"RF_DEPTH": True}, {"RF_DEPTH": 3}, {"TYPO": 8},
                           {"DATA_WIDTH": 17}, []):
            document = deepcopy(self.document)
            document["cluster"]["tiles"][0]["parameters"] = parameters
            result = validate(document)
            with self.subTest(parameters=parameters):
                self.assertFalse(result["valid"])
                self.assertEqual(result["issues"][0]["tile_id"], 0)

    def test_geometry_and_identity_guards(self):
        mutations = [
            lambda d: d.update(name="../outside"),
            lambda d: d["cluster"].update(rows=3),
            lambda d: d["cluster"].update(rows=True),
            lambda d: d["cluster"].update(scratchpad_banks=3),
            lambda d: d["cluster"]["tiles"][0].update(id=3),
            lambda d: d["cluster"]["tiles"][0].update(row=1, col=1),
            lambda d: d["cluster"]["tiles"][0].update({"class": "unknown"}),
        ]
        for mutation in mutations:
            document = deepcopy(self.document)
            mutation(document)
            with self.subTest(document=document):
                self.assertFalse(validate(document)["valid"])

    def test_four_by_four_scope_is_explicit(self):
        self.document["cluster"].update(rows=4, cols=4, tiles=[
            dict(id=r * 4 + c, row=r, col=c, **{"class": "MST" if (r, c) == (2, 1)
                 else "BCT"}) for r in range(4) for c in range(4)])
        result = validate(self.document)
        self.assertTrue(result["valid"])
        self.assertEqual(result["summary"]["validation_scope"],
                         "native tile interfaces and grid transport")

    def test_catalog_and_generator_have_one_parameter_contract(self):
        types = {item["id"]: item for item in catalog()["tile_classes"]}
        self.assertEqual({key for key, item in types.items() if item["available"]},
                         {"BCT", "MST", "VCT", "SFT", "CPT"})
        for tile in self.document["cluster"]["tiles"]:
            for name, parameter in types[tile["class"]]["parameters"].items():
                for value in parameter["choices"]:
                    candidate = deepcopy(self.document)
                    candidate["cluster"]["tiles"][tile["id"]]["parameters"] = {name: value}
                    report = validate(candidate)
                    if not report["valid"]:
                        self.assertIn((name, value), (("SUPPORT_WIDTH_CONVERSION", 0), ("SUPPORT_CIRCULAR", 1),
                            ("MULTIPLY_OPERAND_WIDTH", 32), ("DATA_WIDTH", 2), ("DATA_WIDTH", 4),
                            ("DATA_WIDTH", 6), ("DATA_WIDTH", 8), ("DATA_WIDTH", 16)))

    def test_rectangular_grids_and_all_tile_classes(self):
        classes = ("BCT", "MST", "VCT", "SFT", "CPT")
        for rows, cols in ((1, 1), (1, 5), (5, 1), (3, 5), (2, 9)):
            document = deepcopy(self.document)
            document["cluster"].update(rows=rows, cols=cols, tiles=[
                dict(id=r * cols + c, row=r, col=c,
                     **{"class": classes[(r * cols + c) % len(classes)]})
                for r in range(rows) for c in range(cols)])
            self.assertTrue(validate(document)["valid"], validate(document))

    def test_zero_or_multiple_memory_tiles(self):
        for kind in ("BCT", "MST", "VCT", "SFT", "CPT"):
            document = deepcopy(self.document)
            for tile in document["cluster"]["tiles"]:
                tile["class"] = kind
            self.assertTrue(validate(document)["valid"], kind)

    def test_fu_parameters_are_independent_between_tiles(self):
        document = deepcopy(self.document)
        document["cluster"]["tiles"][0].update({"class": "SFT", "parameters": {
            "FU_PROFILE": 3, "RECIP_INTERNAL_WIDTH": 32, "RSQRT_INTERNAL_WIDTH": 48,
            "EXP_PIPELINE_DEPTH": 7}})
        document["cluster"]["tiles"][1].update({"class": "SFT"})
        resolved, _ = resolve(document)
        a, b = resolved["cluster"]["tiles"][:2]
        self.assertEqual(a["parameters"]["EXP_PIPELINE_DEPTH"], 7)
        self.assertEqual(b["parameters"]["EXP_PIPELINE_DEPTH"], 5)
        self.assertEqual(a["parameters"]["RECIP_INTERNAL_WIDTH"], 32)
        self.assertEqual(a["parameters"]["RSQRT_INTERNAL_WIDTH"], 48)

    def test_invalid_dependent_fu_settings(self):
        for kind, parameters in (("VCT", {"LANE_LATENCY": 0, "MUL_LATENCY": 1}),
                ("SFT", {"OUTPUT_WIDTH": 8, "OUTPUT_FRAC_BITS": 12}),
                ("CPT", {"LOOP_EXPORT_LEVELS": 4, "MAX_LOOP_DEPTH": 1})):
            document = deepcopy(self.document)
            document["cluster"]["tiles"][0].update({"class": kind, "parameters": parameters})
            self.assertFalse(validate(document)["valid"])

    def test_architecture_identity_resolves_defaults_and_placement_order(self):
        resolved, _ = resolve(self.document)
        resolved["cluster"]["tiles"].reverse()
        self.assertEqual(identities(self.document)[1:3], identities(resolved)[1:3])
        resolved["cluster"]["tiles"][0]["parameters"]["READ_DATA_FIFO_DEPTH"] = 16
        self.assertNotEqual(identities(self.document)[1:3], identities(resolved)[1:3])


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.document = starter()
        cls.document["cluster"]["tiles"][0]["parameters"] = {"RF_DEPTH": 16}
        cls.before = (ROOT / "src/rtl/mosaic_blocks/cluster.sv").read_bytes()
        cls.bundle, cls.record = generate(cls.document, cls.directory)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_portable_closure_and_per_tile_rtl(self):
        sources = (self.bundle / "sources.f").read_text().splitlines()
        self.assertGreater(len(sources), 20)
        for name in sources:
            path = Path(name)
            self.assertFalse(path.is_absolute())
            self.assertTrue((self.bundle / path).is_file())
        rtl = (self.bundle / "rtl/cluster.sv").read_text()
        self.assertIn(".RF_DEPTH(16)", rtl)
        self.assertIn(".RF_DEPTH(8)", rtl)
        self.assertEqual(self.before, (ROOT / "src/rtl/mosaic_blocks/cluster.sv").read_bytes())
        manifest = json.loads((self.bundle / "manifest.json").read_text())
        self.assertEqual(manifest["tile_parameter_table"][0]["parameters"]["RF_DEPTH"], 16)

    def test_reproducible_bundle_and_archive(self):
        bundle, record = generate(self.document, self.directory / "another")
        self.assertEqual(record, self.record)
        first, second = archive(self.bundle), archive(bundle)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with zipfile.ZipFile(first) as file:
            self.assertIn("rtl/cluster.sv", file.namelist())
            self.assertNotIn(str(ROOT), "\n".join(file.namelist()))
        self.assertEqual(verify_bundle(bundle), record)

    def test_changed_artifact_blocks_reuse_and_download(self):
        bundle, _ = generate(self.document, self.directory / "tampered")
        (bundle / "rtl/cluster.sv").write_text("// changed\n")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            generate(self.document, self.directory / "tampered")
        with self.assertRaises(ValueError):
            archive(bundle)

    def test_incomplete_record_is_rejected(self):
        bundle, record = generate(self.document, self.directory / "incomplete")
        record["artifact_sha256"].pop("sources.f")
        (bundle / "generation.json").write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            verify_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
