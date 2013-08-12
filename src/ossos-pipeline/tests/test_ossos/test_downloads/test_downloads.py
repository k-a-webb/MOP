__author__ = "David Rusk <drusk@uvic.ca>"

import tempfile
import unittest

from hamcrest import assert_that, equal_to, contains
from mock import Mock, call, MagicMock

import vos

from tests.base_tests import FileReadingTestCase
from ossos.astrom import SourceReading
from ossos.downloads.cutouts import ImageCutoutDownloader
from ossos.downloads.requests import DownloadRequest


class DownloadTest(FileReadingTestCase):
    def setUp(self):
        self.image_uri = "vos://cadc.nrc.ca~vospace/OSSOS/dbimages/1584431/1584431p15.fits"
        self.apcor_uri = "vos://cadc.nrc.ca~vospace/OSSOS/dbimages/1584431/ccd15/1584431p15.apcor"

        self.reading = MagicMock(spec=SourceReading)
        self.reading.x = 0
        self.reading.y = 0
        self.reading.ra = 0
        self.reading.dec = 0
        self.reading.get_image_uri.return_value = self.image_uri
        self.reading.get_apcor_uri.return_value = self.apcor_uri
        self.reading.get_extension.return_value = 19
        self.reading.get_original_image_size.return_value = (2000, 3000)
        self.reading.is_inverted.return_value = False

        self.needs_apcor = True
        self.focal_point = (75, 80)

        self.vosclient = Mock(spec=vos.Client)
        self.downloader = ImageCutoutDownloader(slice_rows=100, slice_cols=50,
                                                vosclient=self.vosclient)

        # Mock vosclient to open a local file instead of one from vospace
        self.localfile = open(self.get_abs_path("data/testimg.fits"), "rb")
        self.apcorfile = tempfile.TemporaryFile("r+b")
        self.apcorfile.write("4 10 0.3 0.1")
        self.apcorfile.flush()
        self.apcorfile.seek(0)

        def choose_ret_val(*args, **kwargs):
            selected_file = None
            if self.image_uri in args:
                selected_file = self.localfile
            elif self.apcor_uri in args:
                selected_file = self.apcorfile
            else:
                self.fail("Unrecognized URI")

            selected_file.seek(0)

            return selected_file

        self.vosclient.open.side_effect = choose_ret_val

    def tearDown(self):
        self.localfile.close()
        self.apcorfile.close()

    def make_request(self, callback=None):
        return DownloadRequest(self.reading,
                               needs_apcor=self.needs_apcor,
                               focal_point=self.focal_point,
                               callback=callback)

    def test_request_image_cutout(self):
        request = self.make_request()

        download = request.execute(self.downloader)

        assert_that(self.vosclient.open.call_args_list, contains(
            call(self.image_uri, view="cutout", cutout="[19][50:100,30:130]"),
            call(self.apcor_uri, view="data")
        ))

        # This is just a test file, make sure we can read an expected value
        # it.  It won't have the right shape necessarily though.
        assert_that(download.get_fits_header()["FILENAME"],
                    equal_to("u5780205r_cvt.c0h"))

    def test_download_callback(self):
        callback = Mock()
        download = self.make_request(callback).execute(self.downloader)
        callback.assert_called_once_with(download)


if __name__ == '__main__':
    unittest.main()
