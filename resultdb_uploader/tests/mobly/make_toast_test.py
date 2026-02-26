from mobly import base_test
from mobly import test_runner
from mobly.controllers import android_device


class MakeToastTest(base_test.BaseTestClass):

  def setup_class(self):
    self.ads = self.register_controller(android_device)
    self.dut = self.ads[0]

    # Install and start Mobly Bundled Snippets (MBS).
    mbs_path = self.user_params['files']['mobly-bundled-snippets'][0]
    self.dut.adb.install(['-r', '-g', mbs_path])
    self.dut.load_snippet('mbs', android_device.MBS_PACKAGE)

  def test_hello(self):
    self.dut.mbs.makeToast('Hello!')

  def test_goodbye(self):
    self.dut.mbs.makeToast('Goodbye!')

  def teardown_test(self):
    self.dut.services.create_output_excerpts_all(self.current_test_info)


if __name__ == '__main__':
  test_runner.main()
