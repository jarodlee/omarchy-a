"""Chinese first-login policy and orientation persistence, without a device."""
import configparser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
DEFAULTS = PROJECT / 'desktop/configuration/chinese-defaults'
I18N = PROJECT / 'desktop/shell/default/i18n'
ORIENTATION = PROJECT / 'desktop/shell/bin/omarchy-display-orientation'
SCALE = PROJECT / 'desktop/configuration/scale-output'


def placeholders(value):
    if isinstance(value, dict):
        return set().union(*(placeholders(v) for v in value.values()))
    return set(re.findall(r'%[1-9][0-9]*', value))


class ChineseCatalogs(unittest.TestCase):
    def test_catalog_covers_english_keys_without_losing_placeholders(self):
        english = json.loads((I18N / 'en/shell.json').read_text())
        chinese = json.loads((I18N / 'zh-CN/shell.json').read_text())
        self.assertEqual(set(english), set(chinese))
        for key, value in english.items():
            with self.subTest(key=key):
                self.assertTrue(chinese[key])
                self.assertEqual(placeholders(value), placeholders(chinese[key]))
        menu = json.loads((I18N / 'zh-CN/menu.json').read_text())
        self.assertEqual(menu['apps']['label'], '应用')
        self.assertEqual(menu['setup']['label'], '设置')

    def test_user_defaults_select_both_input_methods_and_a_fixed_landscape(self):
        config = DEFAULTS / 'home/tablet/.config'
        self.assertEqual((config / 'omarchy/language').read_text().strip(), 'zh-CN')
        self.assertEqual((config / 'omarchy/output-transform').read_text().strip(), '90')
        self.assertTrue((config / 'omarchy/rotation-lock').is_file())
        profile = configparser.ConfigParser()
        profile.read(config / 'fcitx5/profile')
        self.assertEqual(profile['Groups/0']['DefaultIM'], 'pinyin')
        self.assertEqual(profile['Groups/0/Items/0']['Name'], 'keyboard-us')
        self.assertEqual(profile['Groups/0/Items/1']['Name'], 'pinyin')
        hotkeys = configparser.ConfigParser()
        hotkeys.read(config / 'fcitx5/config')
        self.assertEqual(hotkeys['Hotkey/TriggerKeys']['0'], 'Control+space')


class OrientationPreferences(unittest.TestCase):
    def run_orientation(self, choice, output='Unknown-1 "Apple panel"\n  Enabled: yes\n', existing=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            randr = bin_dir / 'wlr-randr'
            randr.write_text('#!/bin/sh\nif [ "$#" -eq 0 ]; then printf "%s" "$RANDR_STATE"; '
                             'else printf "%s\\n" "$*" >> "$RANDR_LOG"; fi\n')
            randr.chmod(0o755)
            config = root / 'config/omarchy'
            if existing:
                config.mkdir(parents=True)
                (config / 'output-transform').write_text('90\n')
                (config / 'rotation-lock').touch()
            log = root / 'randr.log'
            result = subprocess.run(['bash', str(ORIENTATION), choice], capture_output=True, text=True,
                env={**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}',
                     'XDG_CONFIG_HOME': str(config.parent), 'RANDR_STATE': output, 'RANDR_LOG': str(log)},
                timeout=10)
            return (result.returncode,
                    (config / 'output-transform').read_text().strip() if (config / 'output-transform').exists() else None,
                    (config / 'rotation-lock').exists(), log.read_text().splitlines() if log.exists() else [])

    def test_fixed_directions_are_applied_and_saved(self):
        self.assertEqual(self.run_orientation('landscape'),
                         (0, '90', True, ['--output Unknown-1 --transform 90']))
        self.assertEqual(self.run_orientation('portrait'),
                         (0, 'normal', True, ['--output Unknown-1 --transform normal']))

    def test_auto_removes_the_hold_without_rotating_or_touching_calibration(self):
        self.assertEqual(self.run_orientation('auto', existing=True), (0, None, False, []))

    def test_invalid_or_multiple_outputs_leave_the_preference_unchanged(self):
        self.assertEqual(self.run_orientation('sideways', existing=True), (2, '90', True, []))
        self.assertEqual(self.run_orientation('portrait', output='A\nB\n', existing=True),
                         (1, '90', True, []))


BASH = shutil.which('bash')
BASH4 = BASH and int(subprocess.check_output([BASH, '-c', 'echo ${BASH_VERSINFO[0]}'], text=True)) >= 4


@unittest.skipUnless(BASH4, 'scale-output uses bash 4+, as installed on the iPad')
class StartupOrientation(unittest.TestCase):
    def run_scale(self, preference=None, mode='1536x2048', outputs=1):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            stub = bin_dir / 'wlr-randr'
            stub.write_text('#!/bin/sh\nif [ "$#" -eq 0 ]; then printf "%s" "$RANDR_STATE"; '
                            'else printf "%s\\n" "$*" >> "$RANDR_LOG"; fi\n')
            stub.chmod(0o755)
            config = root / 'config/omarchy'
            config.mkdir(parents=True)
            if preference is not None:
                (config / 'output-transform').write_text(preference)
            log = root / 'randr.log'
            state = f'Unknown-1 "Apple panel"\n  Enabled: yes\n    {mode} px, 60.000000 Hz (preferred, current)\n'
            if outputs > 1:
                state += 'HDMI-A-1 "External"\n'
            subprocess.run([BASH, str(SCALE)], check=True, capture_output=True, text=True,
                env={**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}',
                     'XDG_CONFIG_HOME': str(config.parent), 'RANDR_STATE': state, 'RANDR_LOG': str(log)},
                timeout=10)
            return log.read_text().splitlines() if log.exists() else []

    def test_saved_landscape_runs_before_the_shell_without_changing_timing(self):
        self.assertEqual(self.run_scale('90\n'),
                         ['--output Unknown-1 --scale 2', '--output Unknown-1 --transform 90'])

    def test_greeter_without_preference_only_scales(self):
        self.assertEqual(self.run_scale(), ['--output Unknown-1 --scale 2'])

    def test_invalid_preference_is_not_executed_and_other_displays_are_unchanged(self):
        self.assertEqual(self.run_scale('90; touch /no-such-command'), ['--output Unknown-1 --scale 2'])
        self.assertEqual(self.run_scale('90', mode='1920x1080'), [])
        self.assertEqual(self.run_scale('90', outputs=2), [])
