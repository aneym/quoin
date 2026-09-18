"""Version-2 teaching schema, ordered retrieval and real EPUB regression tests."""

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from quoin.assemble import build
from quoin.errors import QuoinError
from quoin.fetch import run as fetch
from quoin.manifest import validate
from quoin.teaching import authored_html_errors
from tests.test_manifest import valid_manifest


def teaching_manifest():
    m = valid_manifest()
    m.update(format_version=2, sources=[], series="aneym")
    m["blocks"] = [
        {
            "id": bid,
            "kind": kind,
            "brief": "Teach the crash window",
            "evidence": [],
            "editorial_ref": f"editorial:{bid}",
            **extra,
        }
        for bid, kind, extra in [
            ("lesson", "lesson", {}),
            ("q1", "exercise", {"recall_group": "m1"}),
            ("q2", "exercise", {"recall_group": "m1"}),
            ("a1", "answer", {"recall_group": "m1", "answers": ["q1"]}),
            ("a2", "answer", {"recall_group": "m1", "answers": ["q2"]}),
            ("debrief", "debrief", {}),
        ]
    ]
    m["movements"][0]["items"] = [{"ref": f"block:{b['id']}"} for b in m["blocks"]]
    return m


def prepare(root):
    m = teaching_manifest()
    (root / "blocks").mkdir(parents=True)
    (root / "assets").mkdir()
    Image.new("RGB", (1600, 2400), "#211d19").save(root / "assets/cover.png")
    image = root / "assets/crash.png"
    Image.new("RGB", (600, 800), "white").save(image)
    m["blocks"][0]["figures"] = [
        {
            "id": "crash",
            "path": "assets/crash.png",
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "alt": "Provider accepts before the worker saves its result.",
            "caption": "An accepted reservation can outlive the worker.",
        }
    ]
    (root / "manifest.json").write_text(json.dumps(m))
    (root / "book.toml").write_text('cover_image = "assets/cover.png"\n')
    for b in m["blocks"]:
        (root / "blocks" / f"{b['id']}.json").write_text(
            json.dumps(
                {
                    "block_id": b["id"],
                    "kind": b["kind"],
                    "title": b["id"],
                    "html": f"<p>{b['id']}: a timeout leaves the provider outcome unknown.</p>",
                }
            )
        )
    fetch(root, offline=True)
    return m


class TeachingTests(unittest.TestCase):
    def test_zero_length_tolerance_only_for_v2(self):
        m = teaching_manifest()
        m["expected_length"] = {"words": 100, "tolerance_pct": 0}
        self.assertEqual(validate(m), [])
        m["format_version"] = 1
        self.assertTrue(any("between 1 and 50" in e for e in validate(m)))

    def test_old_contract_and_new_opt_in(self):
        self.assertEqual(validate(valid_manifest()), [])
        m = teaching_manifest()
        self.assertEqual(validate(m), [])
        m["format_version"] = 1
        self.assertTrue(validate(m))

    def test_answers_follow_all_questions(self):
        m = teaching_manifest()
        items = m["movements"][0]["items"]
        items[2], items[3] = items[3], items[2]
        self.assertTrue(any("every exercise" in e for e in validate(m)))

    def test_answer_reference_errors(self):
        for field, value in [("answers", ["missing"]), ("answers", []), ("recall_group", "other")]:
            m = teaching_manifest()
            m["blocks"][3][field] = value
            self.assertTrue(validate(m), (field, value))

    def test_required_answer_and_unique_spine_and_editorial_ref(self):
        for mutation in (
            lambda m: m["blocks"][4].update(answers=["q1"]),
            lambda m: m["blocks"][0].pop("editorial_ref"),
            lambda m: m["movements"][0]["items"].append({"ref": "block:lesson"}),
        ):
            m = teaching_manifest()
            mutation(m)
            self.assertTrue(validate(m))

    def test_contributor_run(self):
        m = teaching_manifest()
        intro = {
            "id": "intro",
            "kind": "introduction",
            "brief": "Who",
            "evidence": [],
            "editorial_ref": "editorial:intro",
            "introduces": ["author"],
        }
        m["blocks"].append(intro)
        m["blocks"][0]["contributors"] = ["author"]
        m["movements"][0]["items"].insert(0, {"ref": "block:intro"})
        self.assertEqual(validate(m), [])
        m["movements"][0]["items"].reverse()
        self.assertTrue(any("adjacent" in e for e in validate(m)))

    def test_movement_is_an_adjacency_barrier(self):
        m = teaching_manifest()
        intro = {
            "id": "bio",
            "kind": "introduction",
            "brief": "author",
            "evidence": [],
            "editorial_ref": "editorial:bio",
            "introduces": ["person"],
        }
        m["blocks"].append(intro)
        m["blocks"][0]["contributors"] = ["person"]
        m["movements"].insert(
            0, {"id": "before", "title": "Before", "items": [{"ref": "block:bio"}]}
        )
        self.assertTrue(any("adjacent" in e for e in validate(m)))

    def test_html_reveals_and_undeclared_images_fail(self):
        for markup in [
            "<details><summary>Show</summary>answer</details>",
            '<p hidden="hidden">answer</p>',
            '<img src="remote"/>',
            '<p style="display:none">answer</p>',
            '<a href="javascript:x">go</a>',
            '<link rel="stylesheet" href="https://example.invalid/hide.css"/>',
            '<base href="https://example.invalid/"/>',
            '<a href="java&#x09;script:alert(1)">Answer</a>',
            '<a href="//example.invalid">Answer</a>',
            '<p class="hidden">Answer</p>',
        ]:
            self.assertTrue(authored_html_errors(markup))
        self.assertEqual(authored_html_errors("<p>Predict before turning the page.</p>"), [])

    def test_actual_epub_and_cache_and_asset_fidelity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            m = prepare(root)
            target, first = build(root)
            _, second = build(root)
            self.assertTrue(second["stages"]["assemble"]["cache_hit"])
            with zipfile.ZipFile(target) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(
                    archive.read("OEBPS/images/figures/crash.png"),
                    (root / "assets/crash.png").read_bytes(),
                )
                for bid in ("lesson", "q1", "q2", "a1", "a2", "debrief"):
                    self.assertIn(
                        f"{bid}: a timeout", archive.read(f"OEBPS/text/block-{bid}.xhtml").decode()
                    )
                self.assertIn("figcaption", archive.read("OEBPS/text/block-lesson.xhtml").decode())
                self.assertIn("belongs-to-collection", archive.read("OEBPS/content.opf").decode())
            Image.new("RGB", (600, 800), "black").save(root / "assets/crash.png")
            with self.assertRaisesRegex(QuoinError, "sha256 mismatch"):
                build(root)
            m["blocks"][0]["figures"][0]["sha256"] = hashlib.sha256(
                (root / "assets/crash.png").read_bytes()
            ).hexdigest()
            (root / "manifest.json").write_text(json.dumps(m))
            _, third = build(root)
            self.assertFalse(third["stages"]["assemble"]["cache_hit"])
            self.assertNotEqual(first["epub_sha256"], third["epub_sha256"])

    def test_missing_cover_and_path_escape_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            m = prepare(root)
            (root / "book.toml").write_text("")
            with self.assertRaisesRegex(QuoinError, "designed"):
                build(root)
            m["blocks"][0]["figures"][0]["path"] = "../escape.png"
            self.assertTrue(validate(m))

    def test_existing_source_bytes_survive_v2(self):
        from tests.test_source_headers import _prepare_book

        with tempfile.TemporaryDirectory() as temp:
            root = _prepare_book(Path(temp), "book")
            first, _ = build(root)
            with zipfile.ZipFile(first) as z:
                old = {n: z.read(n) for n in z.namelist() if "/source-" in n}
            m = json.loads((root / "manifest.json").read_text())
            m["format_version"] = 2
            for b in m["blocks"]:
                b["editorial_ref"] = f"editorial:{b['id']}"
            Image.new("RGB", (1600, 2400), "black").save(root / "cover.png")
            with (root / "book.toml").open("a") as f:
                f.write('\ncover_image = "cover.png"\n')
            (root / "manifest.json").write_text(json.dumps(m))
            second, _ = build(root)
            with zipfile.ZipFile(second) as z:
                for n, data in old.items():
                    self.assertEqual(data, z.read(n))
