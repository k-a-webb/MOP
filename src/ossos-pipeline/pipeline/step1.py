#!python
# ###############################################################################
##                                                                            ##
## Copyright 2013 by its authors                                              ##
## See COPYING, AUTHORS                                                       ##
##                                                                            ##
## This file is part of OSSOS Moving Object Pipeline (OSSOS-MOP)              ##
##                                                                            ##
##    OSSOS-MOP is free software: you can redistribute it and/or modify       ##
##    it under the terms of the GNU General Public License as published by    ##
##    the Free Software Foundation, either version 3 of the License, or       ##
##    (at your option) any later version.                                     ##
##                                                                            ##
##    OSSOS-MOP is distributed in the hope that it will be useful,            ##
##    but WITHOUT ANY WARRANTY; without even the implied warranty of          ##
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           ##
##    GNU General Public License for more details.                            ##
##                                                                            ##
##    You should have received a copy of the GNU General Public License       ##
##    along with OSSOS-MOP.  If not, see <http://www.gnu.org/licenses/>.      ##
##                                                                            ##
################################################################################
"""step1 is to run the two source finding algorithms in the image.

step1jmp is a stand-alone fortran code from Jean-Marc Petit et al.
step1matt is a script from M. Holman that runs E. Bertain's sExtractor.

"""

import argparse
from subprocess import CalledProcessError
from astropy.io import fits
import logging
import os
from ossos import storage
from ossos import util
import sys

_SEX_THRESHOLD = 1.1
_WAVE_THRESHOLD = 2.7
_FWHM = 4.0
_MAX_COUNT = 30000


def step1(expnum,
          ccd,
          prefix='',
          version='p',
          sex_thresh=_SEX_THRESHOLD,
          wave_thresh=_WAVE_THRESHOLD,
          maxcount=_MAX_COUNT,
          dry_run=False):
    """run the actual step1jmp/matt codes.

    expnum: the CFHT expousre to process
    ccd: which ccd in the mosaic to process
    fwhm: the image quality, FWHM, of the image.  In pixels.
    sex_thresh: the detection threhold to run sExtractor at
    wave_thresh: the detection threshold for wavelet
    maxcount: saturation level

    """

    storage.get_file(expnum, ccd, prefix=prefix, version=version, ext='mopheader')
    filename = storage.get_image(expnum, ccd, version=version, prefix=prefix)
    fwhm = storage.get_fwhm(expnum, ccd, prefix=prefix, version=version)
    basename = os.path.splitext(filename)[0]

    logging.info(util.exec_prog(['step1jmp',
                                 '-f', basename,
                                 '-t', str(wave_thresh),
                                 '-w', str(fwhm),
                                 '-m', str(maxcount)]))

    obj_uri = storage.get_uri(expnum, ccd, version=version, ext='obj.jmp',
                              prefix=prefix)
    obj_filename = basename + ".obj.jmp"

    if not dry_run:
        storage.copy(obj_filename, obj_uri)

    ## for step1matt we need the weight image
    hdulist = fits.open(filename)
    flat_name = hdulist[0].header.get('FLAT', 'weight.fits')
    parts = os.path.splitext(flat_name)
    if parts[1] == '.fz':
        flat_name = os.path.splitext(parts[0])[0]
    else:
        flat_name = parts[0]
    flat_filename = storage.get_image(flat_name, ccd, version='', ext='fits', subdir='calibrators')

    if not os.access('weight.fits', os.R_OK):
        os.symlink(flat_filename, 'weight.fits')

    logging.info(util.exec_prog(['step1matt',
                                 '-f', basename,
                                 '-t', str(sex_thresh),
                                 '-w', str(fwhm),
                                 '-m', str(maxcount)]))

    obj_uri = storage.get_uri(expnum, ccd, version=version, ext='obj.matt',
                              prefix=prefix)
    obj_filename = basename + ".obj.matt"

    if not dry_run:
        storage.copy(obj_filename, obj_uri)

    return True


def main(task='step1'):
    ### Must be running as a script

    parser = argparse.ArgumentParser(
        description='Run step1jmp and step1matt on a given exposure.')

    parser.add_argument("--ccd", "-c",
                        action="store",
                        default=None,
                        type=int,
                        dest="ccd")
    parser.add_argument("--ignore", help="Try to run even in previous step failed.",
                        default=False,
                        action="store_true")
    parser.add_argument("--fk", help="add the fk prefix on processing?",
                        default=False,
                        action='store_true')
    parser.add_argument("--dbimages",
                        action="store",
                        default="vos:OSSOS/dbimages",
                        help='vospace dbimages containerNode')
    parser.add_argument("--sex_thresh",
                        action="store",
                        type=float,
                        default=_SEX_THRESHOLD,
                        help="sExtractor detection threhold")
    parser.add_argument("--wavelet_thresh",
                        type=float,
                        default=_WAVE_THRESHOLD,
                        help="Wavelet detection threhold")
    parser.add_argument("expnum",
                        type=int,
                        nargs='+',
                        help="expnum(s) to process")
    parser.add_argument("--version",
                        action='version',
                        version='%(prog)s 1.0')
    parser.add_argument('--type', default='p',
                        choices=['o', 'p', 's'], help="which type of image")
    parser.add_argument('--log', default=None, help="Write standard out to this file")
    parser.add_argument("--verbose", "-v",
                        action="store_true")
    parser.add_argument("--debug", '-d',
                        action='store_true')
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry_run", action="store_true", help="Do a dry run, not changes to vospce, implies --force")

    args = parser.parse_args()

    if args.dry_run:
        args.force = True

    level = logging.CRITICAL
    log_format = "%(message)s"
    if args.debug:
        log_format = "%(module)s: %(levelname)s: %(message)s"
        level = logging.DEBUG
    elif args.verbose:
        level = logging.INFO

    logging.basicConfig(level=level, format=log_format)

    storage.DBIMAGES = args.dbimages

    if args.ccd is None:
        ccdlist = range(0, 36)
    else:
        ccdlist = [args.ccd]

    prefix = (args.fk and 'fk') or ''

    exit_code = 0
    for expnum in args.expnum:
        for ccd in ccdlist:
            storage.set_logger(os.path.splitext(os.path.basename(sys.argv[0]))[0],
                               prefix, expnum, ccd, args.type, args.dry_run)
            try:
                message = storage.SUCCESS
                if storage.get_status(expnum, ccd, prefix+task, version=args.type) and not args.force:
                    logging.critical("{} completed successfully for {} {} {} {}".format(task, prefix,
                                                                                        expnum, args.type, ccd))
                    continue
                if not storage.get_status(expnum, ccd, prefix+'mkpsf', version=args.type) and not args.ignore:
                    raise IOError(35, "mkpsf hasn't run for {} {} {} {}".format(task, prefix,
                                                                                expnum, args.type, ccd))
                step1(expnum, ccd, prefix=prefix, version=args.type, dry_run=args.dry_run)
            except CalledProcessError as cpe:
                message = str(cpe)
                exit_code = message
            except Exception as e:
                message = str(e)
                exit_code = str(e)

            logging.error("Error running step1_p: %s " % message)

            if not args.dry_run:
                storage.set_status(expnum,
                                   ccd,
                                   prefix + 'step1',
                                   version=args.type,
                                   status=message)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
