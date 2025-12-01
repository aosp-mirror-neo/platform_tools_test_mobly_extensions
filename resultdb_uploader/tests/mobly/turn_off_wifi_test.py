from mobly import asserts
from mobly import base_test
from mobly import test_runner
from mobly.controllers import android_device


class TurnOffWifiTest(base_test.BaseTestClass):

  def setup_class(self):
    self.ads = self.register_controller(android_device)
    self.dut = self.ads[0]

    # Install and start Mobly Bundled Snippets (MBS).
    mbs_path = self.user_params['files']['mobly-bundled-snippets'][0]
    self.dut.adb.install(['-r', '-g', mbs_path])
    self.dut.load_snippet('mbs', android_device.MBS_PACKAGE)

  def test_turn_off_wifi(self):
    self.dut.mbs.wifiDisable()
    asserts.assert_false(self.dut.mbs.wifiIsEnabled(), 'WIFI is not disabled.')


if __name__ == '__main__':
  test_runner.main()
