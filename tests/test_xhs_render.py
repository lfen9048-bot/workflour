import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('xhs_render', Path(__file__).resolve().parents[1] / 'scripts/render-xhs-cards.py')
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


class RenderOutputTests(unittest.TestCase):
    def test_output_file_symlink_cannot_overwrite_an_external_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root / 'external'
            external.write_text('keep')
            target = root / 'preview.html'
            target.symlink_to(external)
            with self.assertRaisesRegex(ValueError, 'symlink output'):
                render.save_output(target, 'replace')
            self.assertEqual(external.read_text(), 'keep')

    def test_card_copy_is_escaped_and_reference_cannot_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            value = render.build(root, {'cards': [{'title': '<script>bad</script>'}]})
            self.assertNotIn('<script>bad</script>', value)
            project = root / 'project'
            project.mkdir()
            (root / 'other.png').write_bytes(b'outside')
            with self.assertRaises(ValueError):
                render.build(project, {'cards': [{'title': 'title', 'image': '../other.png'}]})

    def test_version_output_stays_separate_and_inside_project(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            frozen = render.output_directory(project, 'output') / 'card-01.png'
            frozen.write_bytes(b'frozen')
            output = render.output_directory(project, 'image-versions/gemini-v1/output')
            render.save_output(output / 'card-01.png', b'version')
            self.assertEqual(frozen.read_bytes(), b'frozen')
            self.assertEqual((output / 'card-01.png').read_bytes(), b'version')
            for invalid in ('../outside', 'image-versions/../../outside', str(project / 'absolute'), ''):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    render.output_directory(project, invalid)

    def test_output_rejects_symlink_directory_and_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / 'project'
            project.mkdir()
            outside = root / 'outside'
            outside.mkdir()
            (project / 'linked').symlink_to(outside, target_is_directory=True)
            for value in ('linked', 'linked/output'):
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'symlink output'):
                    render.output_directory(project, value)
            self.assertFalse((outside / 'output').exists())

    def test_image_cover_uses_local_image_and_keeps_readable_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            image = project / 'real-image.png'
            image.write_bytes(b'image fixture')
            before = image.read_bytes()
            card = {'layout': 'image-cover', 'title': 'Claude <更新>', 'image': image.name,
                    'subtitle': '三件新事', 'source_label': '来源：Anthropic', 'image_alt': '真实配图'}
            value = render.build(project, {'as_of': '2026-11-11', 'cards': [card]})
            self.assertIn('class="card image-cover"', value)
            self.assertIn('class="cover-art"', value)
            self.assertIn(image.as_uri(), value)
            self.assertIn('Claude &lt;更新&gt;', value)
            self.assertIn('01 / 01', value)
            self.assertIn('来源：Anthropic', value)
            self.assertIn('2026-11-11', value)
            self.assertEqual(image.read_bytes(), before)
            ordinary = render.build(project, {'cards': [dict(card, layout='standard')]})
            self.assertIn('class="card cover"', ordinary)
            self.assertIn('class="art"', ordinary)

    def test_image_cover_needs_a_real_project_file(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            with self.assertRaisesRegex(ValueError, 'image-cover needs'):
                render.build(project, {'cards': [{'layout': 'image-cover', 'title': 'title'}]})
            with self.assertRaises(FileNotFoundError):
                render.build(project, {'cards': [{'layout': 'image-cover', 'title': 'title', 'image': 'missing.png'}]})


if __name__ == '__main__':
    unittest.main()
