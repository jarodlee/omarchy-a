import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import os
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'desktop/recovery/omarchy-touch-recovery'
loader = importlib.machinery.SourceFileLoader('touch_recovery', str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
recovery = importlib.util.module_from_spec(spec)
loader.exec_module(recovery)
HOME, UP = recovery.HOME, recovery.VOLUME_UP


class ChordTests(unittest.TestCase):
    def pair(self, chord, now=0, order=(HOME, UP)):
        for key in order:
            chord.feed(key, 1, now)

    def release(self, chord, now):
        for key in (HOME, UP):
            chord.feed(key, 0, now)

    def test_both_press_orders_require_the_full_hold(self):
        for order in ((HOME, UP), (UP, HOME)):
            chord = recovery.Chord()
            self.pair(chord, order=order)
            self.assertFalse(chord.tick(2.999))
            self.assertTrue(chord.tick(3))

    def test_single_keys_do_not_trigger(self):
        for key in (HOME, UP, 116, 114):
            chord = recovery.Chord()
            chord.feed(key, 1, 0)
            self.assertFalse(chord.tick(100))

    def test_delay_starts_when_second_button_is_pressed(self):
        chord = recovery.Chord()
        chord.feed(HOME, 1, 0)
        chord.feed(UP, 1, 10)
        self.assertFalse(chord.tick(12.9))
        self.assertTrue(chord.tick(13))

    def test_repeat_and_duplicate_press_do_not_reset_timer_or_retrigger(self):
        chord = recovery.Chord()
        self.pair(chord)
        chord.feed(UP, 2, 1)
        chord.feed(UP, 1, 2)
        self.assertTrue(chord.tick(3))
        self.assertFalse(chord.tick(100))

    def test_short_chord_is_cancelled(self):
        chord = recovery.Chord()
        self.pair(chord)
        chord.feed(UP, 0, 2)
        self.assertFalse(chord.tick(4))

    def test_release_requires_a_new_full_hold(self):
        chord = recovery.Chord()
        self.pair(chord)
        chord.feed(UP, 0, 2)
        chord.feed(UP, 1, 4)
        self.assertFalse(chord.tick(6.9))
        self.assertTrue(chord.tick(7))

    def test_full_release_and_cooldown(self):
        chord = recovery.Chord()
        self.pair(chord)
        self.assertTrue(chord.tick(3))
        self.release(chord, 4)
        self.pair(chord, 5)
        self.assertFalse(chord.tick(8))
        self.assertTrue(chord.tick(33))

    def test_partially_releasing_does_not_rearm_a_fired_chord(self):
        chord = recovery.Chord()
        self.pair(chord)
        self.assertTrue(chord.tick(3))
        chord.feed(UP, 0, 4)
        chord.feed(UP, 1, 35)
        self.assertFalse(chord.tick(40))

    def test_startup_or_lost_events_need_a_fresh_release(self):
        chord = recovery.Chord()
        chord.resync({HOME, UP})
        self.assertFalse(chord.tick(100))
        chord.feed(UP, 0, 101)
        chord.feed(UP, 1, 102)
        self.assertFalse(chord.tick(110))
        self.release(chord, 111)
        self.pair(chord, 112)
        self.assertTrue(chord.tick(115))


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'rc.xml'
        self.original = '''<labwc_config>
          <!-- retain this -->
          <keyboard><keybind key="W-w"><action name="Close"/></keybind></keyboard>
          <touch deviceName="iPad7,5 Touchscreen" mapToOutput="wrong" mouseEmulation="yes"/>
          <touch deviceName="Other touch" mapToOutput="HDMI-A-1"/>
          <libinput><device category="iPad7,5 Touchscreen">
          <calibrationMatrix>0 1 0 -1 0 1</calibrationMatrix><tap>yes</tap>
          </device></libinput></labwc_config>'''
        self.path.write_text(self.original)

    def test_repairs_only_named_touch_and_retains_other_settings(self):
        recovery.configure(self.path, 'Unknown-1', ['iPad7,5 Touchscreen'])
        root = ET.parse(self.path).getroot()
        named = root.find("touch[@deviceName='iPad7,5 Touchscreen']")
        self.assertEqual(named.get('mouseEmulation'), 'no')
        self.assertEqual(named.get('mapToOutput'), 'Unknown-1')
        self.assertEqual(root.find("touch[@deviceName='Other touch']").get('mapToOutput'), 'HDMI-A-1')
        self.assertIsNotNone(root.find("keyboard/keybind[@key='W-w']"))
        self.assertEqual(root.find('.//calibrationMatrix').text, '1 0 0 0 1 0')
        self.assertEqual(root.find('.//tap').text, 'yes')
        self.assertIn('retain this', self.path.read_text())
        self.assertEqual(self.path.with_name('rc.xml.before-hardware-recovery').read_text(), self.original)

    def test_creates_mapping_for_greeter_and_escapes_output(self):
        self.path.write_text('<labwc_config><keyboard/></labwc_config>')
        recovery.configure(self.path, 'Panel&1', ['iPad7,5 Touchscreen'])
        self.assertEqual(ET.parse(self.path).find('touch').get('mapToOutput'), 'Panel&1')

    def test_second_repair_does_not_duplicate_entries(self):
        recovery.configure(self.path, 'Unknown-1', ['iPad7,5 Touchscreen'])
        recovery.configure(self.path, 'Unknown-1', ['iPad7,5 Touchscreen'])
        root = ET.parse(self.path).getroot()
        self.assertEqual(len(root.findall("touch[@deviceName='iPad7,5 Touchscreen']")), 1)
        self.assertEqual(len(root.findall('.//calibrationMatrix')), 1)

    def test_symlinks_and_malformed_configs_are_not_overwritten(self):
        target = self.path.with_name('target')
        target.write_text('keep')
        self.path.unlink()
        self.path.symlink_to(target)
        with self.assertRaises(RuntimeError):
            recovery.configure(self.path, 'Unknown-1', ['iPad7,5 Touchscreen'])
        self.assertEqual(target.read_text(), 'keep')
        self.path.unlink()
        self.path.write_text('<bad')
        with self.assertRaises(ET.ParseError):
            recovery.configure(self.path, 'Unknown-1', ['iPad7,5 Touchscreen'])
        self.assertEqual(self.path.read_text(), '<bad')

    def test_symlinked_backup_is_not_followed(self):
        target = self.path.with_name('target')
        target.write_text('keep')
        self.path.with_name('rc.xml.before-hardware-recovery').symlink_to(target)
        with self.assertRaises(RuntimeError):
            recovery.configure(self.path, 'Unknown-1', ['iPad7,5 Touchscreen'])
        self.assertEqual(target.read_text(), 'keep')
        self.assertEqual(self.path.read_text(), self.original)

    def test_marker_expiry_fails_open_for_normal_buttons(self):
        marker = self.path.with_name('held.json')
        for value, expected in [('bad', False), ('{}', False),
                                (json.dumps({'expires': 10}), False),
                                (json.dumps({'expires': 12}), True),
                                (json.dumps({'expires': 100}), False)]:
            marker.write_text(value)
            self.assertEqual(recovery.active(marker, now=10), expected)

    def test_pidfd_is_closed_after_signalling(self):
        with patch.object(recovery.os, 'pidfd_open', create=True, return_value=17), \
             patch.object(recovery.signal, 'pidfd_send_signal', create=True) as send, \
             patch.object(recovery.os, 'close') as close:
            recovery.signal_process(123, recovery.signal.SIGTERM)
        send.assert_called_once_with(17, recovery.signal.SIGTERM)
        close.assert_called_once_with(17)

    def test_unsupported_device_does_not_change_config_or_close_desktop(self):
        with patch.object(recovery.os, 'geteuid', return_value=0), \
             patch.object(recovery, 'supported', return_value=False), \
             patch.object(recovery, 'configure') as configure, \
             patch.object(recovery, 'signal_process') as signal_process:
            with self.assertRaises(RuntimeError):
                recovery.recover()
        configure.assert_not_called()
        signal_process.assert_not_called()


class WatcherTests(unittest.TestCase):
    def exercise(self, data, times, states=(set(),)):
        fd, writer = os.pipe()
        self.addCleanup(os.close, writer)
        child = unittest.mock.Mock()
        child.poll.return_value = None
        ready = [([fd], [], [])] + [([], [], [])] * (len(times) - 3)
        ready.append(InterruptedError('done'))
        with patch.object(recovery.os, 'geteuid', return_value=0), \
             patch.object(recovery, 'supported', return_value=True), \
             patch.object(recovery, 'gpio_device', return_value=fd), \
             patch.object(recovery, 'key_state', side_effect=states), \
             patch.object(recovery.os, 'read', return_value=data), \
             patch.object(recovery.select, 'select', side_effect=ready), \
             patch.object(recovery.time, 'monotonic', side_effect=times), \
             patch.object(recovery, 'mark') as mark, \
             patch.object(recovery.subprocess, 'Popen', return_value=child) as spawn:
            with self.assertRaises(InterruptedError):
                recovery.watch()
        self.assertEqual(mark.call_args.args, (False,))
        return spawn

    def test_actual_event_decoder_triggers_once_and_keeps_cleanup(self):
        data = b''.join(recovery.EVENT.pack(0, 0, 1, key, 1) for key in (HOME, UP))
        spawn = self.exercise(data, [0, 0, 0, 3, 4])
        spawn.assert_called_once_with(['/usr/bin/timeout', '-k', '5', '60', recovery.SCRIPT, 'recover'])

    def test_dropped_event_stream_cannot_trigger_from_stale_downs(self):
        events = [(1, HOME, 1), (1, UP, 1), (0, 3, 0), (1, UP, 1), (0, 0, 0)]
        data = b''.join(recovery.EVENT.pack(0, 0, kind, code, value) for kind, code, value in events)
        spawn = self.exercise(data, [0, 0, 0, 3, 4], states=(set(), {HOME, UP}))
        spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
