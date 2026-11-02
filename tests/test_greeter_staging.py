import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

STAGE = Path(__file__).resolve().parents[1] / 'desktop/stage.py'
spec = importlib.util.spec_from_file_location('desktop_stage', STAGE)
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class GreeterStagingTests(unittest.TestCase):
    def test_group_writable_source_modes_cannot_reach_login_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'greeter'
            config = root / 'labwc/rc.xml'
            config.parent.mkdir(parents=True)
            config.write_text('<labwc_config/>')
            config.chmod(0o664)
            startup = config.parent / 'autostart'
            startup.write_text('#!/bin/sh\n')
            startup.chmod(0o775)
            for path in (root, config.parent):
                path.chmod(0o775)
            stage.harden_greeter(root)
            self.assertEqual(config.stat().st_mode & 0o777, 0o644)
            for path in (root, config.parent, startup):
                self.assertEqual(path.stat().st_mode & 0o777, 0o755)

    def test_trusted_ui_fallback_theme_and_tmpfiles_are_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            upstream = root / 'upstream'
            theme = upstream / 'themes/osaka-jade'
            (theme / 'backgrounds').mkdir(parents=True)
            (theme / 'colors.toml').write_text('foreground = "#ffffff"\n')
            (theme / 'backgrounds/first.webp').write_bytes(b'fallback')
            (upstream / 'applications').mkdir()
            (upstream / 'applications/foot.desktop').write_text('[Desktop Entry]\n')
            keyboard = root / 'keyboard'
            keyboard.write_bytes(b'keyboard')
            xpi = root / 'extension.xpi'
            xpi.write_bytes(b'extension')
            target = root / 'payload'
            args = ['stage.py', str(target), '--upstream', str(upstream), '--keyboard', str(keyboard),
                    '--keyboard-sha256', hashlib.sha256(keyboard.read_bytes()).hexdigest(),
                    '--omafox-xpi', str(xpi)]
            with patch.object(sys, 'argv', args), patch.object(stage, 'XPI_SHA', hashlib.sha256(xpi.read_bytes()).hexdigest()):
                stage.main()
            greeter = target / 'usr/share/omarchy-greeter'
            for path in (greeter, greeter / 'labwc', greeter / 'labwc/rc.xml'):
                self.assertFalse(path.stat().st_mode & 0o022)
            self.assertEqual((greeter / 'plugins/lock/LockView.qml').read_bytes(),
                             (stage.PORT / 'shell/plugins/lock/LockView.qml').read_bytes())
            self.assertTrue((greeter / 'Commons/Color.qml').is_file())
            jade = stage.HERE / 'themes/jade-horse'
            self.assertEqual((greeter / 'default-theme/background').read_bytes(),
                             (jade / 'backgrounds/01-mountain-horses.webp').read_bytes())
            self.assertEqual((greeter / 'default-theme/colors.toml').read_bytes(),
                             (jade / 'colors.toml').read_bytes())
            themes = target / 'home/tablet/.local/share/omarchy-ipad/themes'
            self.assertFalse((themes / 'osaka-jade').exists())
            self.assertEqual((themes / 'jade-horse/icons.theme').read_text().strip(), 'Yaru-sage')
            first_theme = (target / 'usr/local/libexec/arch-ipad-first-theme').read_text()
            self.assertIn('themes/jade-horse', first_theme)
            self.assertIn("'jade-horse' >", first_theme)
            self.assertNotIn('tokyo-night', first_theme)
            self.assertIn('tablet tablet', (target / 'usr/lib/tmpfiles.d/omarchy-greeter-theme.conf').read_text())
            self.assertTrue((target / 'home/tablet/.local/share/omarchy-ipad/bin/omarchy-greeter-theme-publish').is_file())
            # Boot login is the PIN greeter on VT1, not a tty1 autologin.
            greetd = (target / 'etc/greetd/config.toml').read_text()
            self.assertIn('vt = 1', greetd)
            self.assertIn('command = "/usr/local/libexec/omarchy-greeter-session"', greetd)
            self.assertTrue((target / 'etc/systemd/system/greetd.service.d/seatd.conf').is_file())
            self.assertFalse((target / 'etc/systemd/system/getty@tty1.service.d').exists())
            self.assertFalse((target / 'home/tablet/.bash_profile').exists())
            self.assertTrue((target / 'usr/local/libexec/arch-ipad-rotate-output').stat().st_mode & 0o111)
            self.assertTrue((target / 'usr/local/libexec/arch-ipad-touch-output').stat().st_mode & 0o111)
            # Chinese fonts/input/language must be ready at the first login,
            # and be bound to the same payload manifest as the desktop.
            import json
            manifest = json.loads((target / 'arch-ipad-ui-manifest.json').read_text())
            for relative in (
                'etc/locale.conf',
                'home/tablet/.config/fcitx5/profile',
                'home/tablet/.config/omarchy/rotation-lock',
                'home/tablet/.config/labwc/environment',
                'home/tablet/.local/share/omarchy-ipad/default/i18n/zh-CN/shell.json',
                'home/tablet/.local/share/omarchy-ipad/default/i18n/zh-CN/menu.json',
            ):
                self.assertEqual(manifest[relative], hashlib.sha256((target / relative).read_bytes()).hexdigest())
            self.assertTrue((target / 'usr/local/bin/omarchy-display-orientation').is_symlink())
            recovery = target / 'usr/local/libexec/omarchy-touch-recovery'
            self.assertTrue(recovery.stat().st_mode & 0o111)
            self.assertEqual(manifest[str(recovery.relative_to(target))],
                             hashlib.sha256(recovery.read_bytes()).hexdigest())
            recovery_unit = target / 'usr/lib/systemd/system/omarchy-touch-recovery.service'
            self.assertIn('ExecCondition=/usr/local/libexec/omarchy-touch-recovery supported',
                          recovery_unit.read_text())
            enabled = target / 'etc/systemd/system/multi-user.target.wants/omarchy-touch-recovery.service'
            self.assertTrue(enabled.is_symlink())
            self.assertEqual(str(enabled.readlink()), '/usr/lib/systemd/system/omarchy-touch-recovery.service')


if __name__ == '__main__':
    unittest.main()
