from ossos.storage import get_mopheader, get_astheader

__author__ = 'Michele Bannister, JJ Kavelaars'

import datetime
import os
import warnings

from astropy.io import ascii
from astropy.time import Time
import requests
import sys

from . import astrom
from .gui import logger, config
from . import mpc
from .orbfit import Orbfit
from . import storage
from . import wcs


SSOS_URL = "http://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/cadcbin/ssos/ssos.pl"
RESPONSE_FORMAT = 'tsv'
NEW_LINE = '\r\n'


class TracksParser(object):
    def __init__(self, inspect=True, skip_previous=False):
        self.orbit = None
        self._nights_per_darkrun = 18
        self._nights_separating_darkruns = 30
        self.inspect = inspect
        self.skip_previous = skip_previous

    def parse(self, filename):
        mpc_observations = mpc.MPCReader(filename).mpc_observations

        # pass down the provisional name so the table lines are linked to this TNO
        self.ssos_parser = SSOSParser(mpc_observations[0].provisional_name,
                                      input_observations=mpc_observations, skip_previous=self.skip_previous)
        self.orbit = Orbfit(mpc_observations)
        print(self.orbit.summarize())  # defaults to predicting at today's date

        if self.orbit.arc_length < 1:
            # data from the same dark run.
            lunation_count = 0
        elif self.orbit.arc_length > 1 and self.orbit.arc_length < self._nights_per_darkrun:
            # data from neighbouring darkruns.
            lunation_count = 1
        else:
            # data from the entire project.
            lunation_count = None

        # loop over the query until some new observations are found, or raise assert error.
        while True:
            tracks_data = self.query_ssos(mpc_observations, lunation_count)

            if (tracks_data.get_arc_length() > (self.orbit.arc_length + 2.0 / 86400.0) or
                        tracks_data.get_reading_count() > len(mpc_observations)):
                return tracks_data
            if not self.inspect:
                assert lunation_count is not None, "No new observations available."
            if lunation_count is None:
                return tracks_data
            lunation_count += 1
            if lunation_count > 2:
                lunation_count = None

    def query_ssos(self, mpc_observations, lunation_count=None):
        """Send a query to the SSOS web service, looking for available observations using the given track.

        :param mpc_observations: a list of mpc.Observations
        :param lunation_count: how many dark runs (+ and -) to search into
        :return: an SSOSData object
        """

        # we observe ~ a week either side of new moon
        # but we don't know when in the dark run the discovery happened
        # so be generous with the search boundaries, add extra 2 weeks
        # current date just has to be the night of the triplet,

        if lunation_count is None:
            # Only using SSOS to find data acquired during the survey period, for now.
            search_start_date = Time('2013-02-08', scale='utc')
            search_end_date = Time(datetime.datetime.now().strftime('%Y-%m-%d'), scale='utc')
        else:
            search_start_date = Time((mpc_observations[0].date.jd - (
                self._nights_per_darkrun +
                lunation_count * self._nights_separating_darkruns)),
                                     format='jd', scale='utc')
            search_end_date = Time((mpc_observations[-1].date.jd + (
                self._nights_per_darkrun +
                lunation_count * self._nights_separating_darkruns)),
                                   format='jd', scale='utc')

        logger.info("Sending query to SSOS start_date: {} end_data: {}\n".format(search_start_date, search_end_date))
        query = Query(mpc_observations,
                      search_start_date=search_start_date,
                      search_end_date=search_end_date)

        logger.debug("Parsing query results...")
        tracks_data = self.ssos_parser.parse(query.get(), mpc_observations=mpc_observations)

        tracks_data.mpc_observations = {}

        for mpc_observation in mpc_observations:
            # attach the input observations to the the SSOS query result.
            assert isinstance(mpc_observation, mpc.Observation)
            try:
                tracks_data.mpc_observations[mpc_observation.comment.frame] = mpc_observation
            except:
                print mpc_observation

        for source in tracks_data.get_sources():
            astrom_observations = tracks_data.observations
            source_readings = source.get_readings()
            for idx in range(len(source_readings)):
                source_reading = source_readings[idx]
                astrom_observation = astrom_observations[idx]
                self.orbit.predict(Time(astrom_observation.mjd, format='mjd', scale='utc'))
                source_reading.pa = self.orbit.pa
                # why are these being recorded just in pixels?  Because the error ellipse is drawn in pixels.
                # TODO: Modify error ellipse drawing routine to use WCS but be sure
                # that this does not cause trouble with the use of dra/ddec for cutout computer
                source_reading.dra = self.orbit.dra / 0.185
                source_reading.ddec = self.orbit.ddec / 0.185

                frame = astrom_observation.rawname
                if frame in tracks_data.mpc_observations:
                    source_reading.discovery = tracks_data.mpc_observations[frame].discovery

        return tracks_data  # a SSOSData with .sources and .observations only


class SSOSParser(object):
    """
    Parse the result of an SSOS query, which is stored in an astropy Table object
    """

    def __init__(self, provisional_name, input_observations=None, skip_previous=False):
        """
        setup the parser.
        :param provisional_name: name of KBO to assign SSOS data to
        :param input_observations: input observations used in search
        """
        if input_observations is None:
            input_observations = []
        self.provisional_name = provisional_name
        self.input_rawnames = []
        self.null_observations = []
        self.skip_previous = skip_previous
        for observation in input_observations:
            assert isinstance(observation, mpc.Observation)
            try:
                rawname = observation.comment.frame
                self.input_rawnames.append(rawname)
                if observation.null_observation:
                    self.null_observations.append(rawname)
            except:
                logger.error("Failed to get original filename from {}".format(observation.comment))

    def _skip_missing_data(self, str_vals, ncols):
        """
        add a extra column if one is missing, else return None.
        """
        if len(str_vals) == ncols - 1:
            str_vals.append('None')
            return str_vals
        else:
            logger.error("Failed to parse row: {}".format(str_vals))
            raise ValueError("not enough columns in table")

    def build_source_reading(self, expnum, ccd, X, Y):
        """
        Given the location of a source in the image, create a source reading.

        """

        image_uri = storage.dbimages_uri(expnum=expnum,
                                         ccd=None,
                                         version='p',
                                         ext='.fits',
                                         subdir=None)

        slice_rows = config.read("CUTOUTS.SINGLETS.SLICE_ROWS")
        slice_cols = config.read("CUTOUTS.SINGLETS.SLICE_COLS")

        if X == -9999 or Y == -9999:
            logger.warning("Skipping {} as x/y not resolved.".format(image_uri))
            raise ValueError("No position resolution from SSOIS")

        if not (-slice_cols / 2. < X < 2048 + slice_cols / 2. and -slice_rows / 2. < Y < 4600 + slice_rows / 2.0):
            logger.warning("Central location ({},{}) off image cutout.".format(X, Y))
            raise ValueError("Best fit position outside CCD boundaries.")

        observation = astrom.Observation(expnum=str(expnum),
                                         ftype='p',
                                         ccdnum=str(ccd),
                                         fk="")
        observation._header = None

        observation.rawname = os.path.splitext(os.path.basename(image_uri))[0] + str(ccd).zfill(2)

        return observation


    def get_coord_offset(self, expnum, ccd, X, Y, ref_expnum, ref_ccd):
        # determine offsets to reference reference frame using wcs

        astheader = get_astheader(expnum, ccd)
        ref_astheader = get_astheader(ref_expnum, ref_ccd)

        ref_pvwcs = wcs.WCS(ref_astheader)
        pvwcs = wcs.WCS(astheader)

        (ra, dec) = pvwcs.xy2sky(X, Y)
        (x0, y0) = ref_pvwcs.sky2xy(ra, dec)
        logger.debug("{}p{} {},{} ->  {}p{} {},{}".format(expnum, ccd,
                                                          X, Y,
                                                          ref_expnum, ref_ccd,
                                                          x0, y0))
        return (x0, y0)


    def parse(self, ssos_result_filename_or_lines, mpc_observations=None):
        """
        given the result table create 'source' objects.

        :param ssos_result_filename_or_lines:
        """
        table_reader = ascii.get_reader(Reader=ascii.Basic)
        table_reader.inconsistent_handler = self._skip_missing_data
        table_reader.header.splitter.delimiter = '\t'
        table_reader.data.splitter.delimiter = '\t'
        table = table_reader.read(ssos_result_filename_or_lines)

        sources = []
        observations = []
        source_readings = []

        warnings.filterwarnings('ignore')
        ref_x = None
        ref_y = None
        ref_mjd = None
        ref_expnum = None
        ref_ccd = None
        nrows = len(table)
        logger.info("Loading {} observations\n".format(nrows))
        for row in table:
            # check if a dbimages object exists
            ccd = int(row['Ext']) - 1
            expnum = row['Image'].rstrip('p')
            X = row['X']
            Y = row['Y']
            mjd = row['MJD']
            logger.debug("{}".format(row))

            # Excludes the non-CFHT OSSOS data, and the wallpaper.
            # note: 'Telescope_Insturment' is a typo in SSOIS's return format
            if (row['Telescope_Insturment'] != 'CFHT/MegaCam') or (row['Filter'] not in ['r.MP9601', 'u.MP9301']) \
                    or row['Image_target'].startswith('WP'):
                continue

            # Build astrom.SourceReading
            nrows -= 1
            if self.skip_previous:
                previous = False
                for mpc_observation in mpc_observations:
                    try:
                        if mpc_observation.comment.frame == "{}p{:02d}".format(expnum, ccd) \
                                and not mpc_observation.discovery.is_initial_discovery:
                            logger.info("Skipping {}p{:02d}: already measured\n".format(expnum, ccd))
                            previous = True
                            break
                    except Exception as e:
                        pass
                if previous:
                    continue
            logger.info(
                "\r{}\r {}: observation {} {} {} {} from SSOS .. ".format(" " * 190, nrows, expnum, ccd, X, Y))
            try:
                observation = self.build_source_reading(expnum, ccd, X, Y)
                observation.mjd = mjd
                logger.info('built source reading {}'.format(observation))
            except Exception as err:
                logger.error(str(err)+"\n")
                continue
            observations.append(observation)

            from_input_file = observation.rawname in self.input_rawnames
            null_observation = observation.rawname in self.null_observations
            ref_x = None
            if ref_x is None or mjd - ref_mjd > 0.5:
                ref_x = X
                ref_y = Y
                ref_expnum = expnum
                ref_ccd = ccd
                ref_mjd = mjd
                x0 = X
                y0 = Y
            else:
                (x0, y0) = self.get_coord_offset(expnum,
                                                 ccd,
                                                 X,
                                                 Y,
                                                 ref_expnum,
                                                 ref_ccd)

            # Also reset the reference point if the x/y shift is large.
            if x0 - X > 250 or y0 - Y > 250:
                ref_x = X
                ref_y = Y
                ref_expnum = expnum
                ref_ccd = ccd
                ref_mjd = mjd
                x0 = X
                y0 = Y

            logger.info(" Building SourceReading .... \n")
            source_reading = astrom.SourceReading(x=row['X'], y=row['Y'], x0=x0, y0=y0, ra=row['Object_RA'],
                                                  dec=row['Object_Dec'], xref=ref_x, yref=ref_y, obs=observation,
                                                  ssos=True, from_input_file=from_input_file,
                                                  null_observation=null_observation, is_inverted=False)
            logger.info("done")

            source_readings.append(source_reading)


        # build our array of SourceReading objects
        sources.append(source_readings)

        warnings.filterwarnings('once')

        return SSOSData(observations, sources, self.provisional_name)


class SSOSData(object):
    """
    Encapsulates data extracted from an .astrom file.
    """

    def __init__(self, observations, sources, provisional_name):
        """
        Constructs a new astronomy data set object.

        Args:
          observations: list(Observations)
            The observations that are part of the data set.
        """
        self.mpc_observations = {}
        self.observations = observations
        self.sys_header = None
        self.sources = [astrom.Source(
            reading_list,
            provisional_name) for reading_list in sources]

    def get_reading_count(self):
        count = 0
        for source in self.sources:
            count += source.num_readings()

        return count

    def get_sources(self):
        return self.sources

    def get_source_count(self):
        return len(self.get_sources())

    def get_arc_length(self):
        mjds = []
        for obs in self.observations:
            mjds.append(obs.mjd)
        arc = (len(mjds) > 0 and max(mjds) - min(mjds)) or 0
        return arc


class ParamDictBuilder(object):
    """
    Build a dictionary of parameters needed for an SSOS Query.

    This should be fun!
    """

    def __init__(self,
                 observations,
                 verbose=False,
                 search_start_date=Time('2013-01-01', scale='utc'),
                 search_end_date=Time('2017-01-01', scale='utc'),
                 orbit_method='bern',
                 error_ellipse='bern',
                 resolve_extension=True,
                 resolve_position=True):
        self.observations = observations
        self.verbose = verbose
        self.search_start_date = search_start_date
        self.search_end_date = search_end_date
        self.orbit_method = orbit_method
        self.error_ellipse = error_ellipse
        self.resolve_extension = resolve_extension
        self.resolve_position = resolve_position

    @property
    def observations(self):
        """
        The observations to be used in fitting, returned as list of
        the mpc format lines.

        This should be set to a list of objects whose 'str' values
        will be valid MPC observations.
        """
        return self._observations

    @observations.setter
    def observations(self, observations):
        self._observations = []
        for observation in observations:
            assert isinstance(observation, mpc.Observation)
            if not observation.null_observation:
                self._observations.append(observation)

    @property
    def verbose(self):
        """
        In verbose mode the SSOS query will return diagnoistic
        information about how the search was done.
        """
        return self._verbose

    @verbose.setter
    def verbose(self, verbose):
        self._verbose = ( verbose and 'yes') or 'no'

    @property
    def search_start_date(self):
        """
        astropy.io.Time object. The start date of SSOS search window.
        """
        return self._search_start_date

    @search_start_date.setter
    def search_start_date(self, search_start_date):
        """

        :type search_start_date: astropy.io.Time
        :param search_start_date: search for frames take after the given date.
        """
        assert isinstance(search_start_date, Time)
        self._search_start_date = search_start_date.replicate(format='iso')
        self._search_start_date.out_subfmt = 'date'

    @property
    def search_end_date(self):
        """
        astropy.io.Time object. The end date of SSOS search window.
        """
        return self._search_end_date

    @search_end_date.setter
    def search_end_date(self, search_end_date):
        """
        :type search_end_date: astropy.io.Time
        :param search_end_date: search for frames take after the given date.
        """
        assert isinstance(search_end_date, Time)
        self._search_end_date = search_end_date.replicate(format='iso')
        self._search_end_date.out_subfmt = 'date'

    @property
    def orbit_method(self):
        """
        What fitting method should be used to turn the observations
        into an orbit.

        Must be one of ['bern', 'mpc']
        """
        return self._orbit_method

    @orbit_method.setter
    def orbit_method(self, orbit_method):
        assert orbit_method in ['bern', 'mpc']
        self._orbit_method = orbit_method

    @property
    def error_ellipse(self):
        """
        The size of the error ellipse to assign to each position, or
        'bern' to use the output of the BK fit.
        """
        return self._error_ellipse

    @error_ellipse.setter
    def error_ellipse(self, error_ellipse):
        """

        :param error_ellipse: either a number or the work 'bern'
        """
        if error_ellipse == 'bern':
            assert self.orbit_method == 'bern'
        else:
            error_ellipse = float(error_ellipse)
        self._error_ellipse = error_ellipse

    @property
    def resolve_extension(self):
        """
        Should SSOS resolve and return which extension of a frame the
        object would be in?
        """
        return self._resolve_extension

    @resolve_extension.setter
    def resolve_extension(self, resolve_extension):
        if str(resolve_extension).lower() == "no":
            resolve_extension = False
        self._resolve_extension = (resolve_extension and "yes") or "no"

    @property
    def resolve_position(self):
        """
        Should SSOS resolve and return the predicted X/Y location of
        the source?
        """
        return self._resolve_position

    @resolve_position.setter
    def resolve_position(self, resolve_position):
        if str(resolve_position).lower() == "no":
            resolve_position = False
        self._resolve_position = (resolve_position and "yes") or "no"

    @property
    def params(self):
        """
        The SSOS Query parameters as dictionary, appropriate for url_encoding
        """
        return dict(format=RESPONSE_FORMAT,
                    verbose=self.verbose,
                    epoch1=str(self.search_start_date),
                    epoch2=str(self.search_end_date),
                    search=self.orbit_method,
                    eunits=self.error_ellipse,
                    extres=self.resolve_extension,
                    xyres=self.resolve_position,
                    obs=NEW_LINE.join((
                        str(observation) for observation in self.observations))
        )


class Query(object):
    """
    Query the CADC's Solar System Object search for a given set of
    MPC-formatted moving object detection lines.

    Inputs:
        - a list of ossos.mpc.Observation instances

    Optional:
        - a tuple of the start and end times to be searched
          between. Format '%Y-%m-%d'

    Otherwise the temporal range defaults to spanning from the start
    of OSSOS surveying on 2013-01-01 to the present day.

    """

    def __init__(self,
                 observations,
                 search_start_date=Time('2013-01-01', scale='utc'),
                 search_end_date=Time('2017-01-01', scale='utc')):
        self.param_dict_builder = ParamDictBuilder(
            observations,
            search_start_date=search_start_date,
            search_end_date=search_end_date)

        self.headers = {'User-Agent': 'OSSOS Target Track'}

    def get(self):
        """
        :return: astropy.table.table
        :raise: AssertionError
        """
        params = self.param_dict_builder.params
        logger.debug("{}\n".format(params))
        self.response = requests.post(SSOS_URL,
                                      data=params,
                                      headers=self.headers)
        logger.info(self.response.url)
        assert isinstance(self.response, requests.Response)

        assert (self.response.status_code == requests.codes.ok )

        lines = self.response.content
        # note: spelling 'occured' is in SSOIS
        if len(lines) < 2 or "An error occured getting the ephemeris" in lines:
            raise IOError(os.errno.EACCES,
                          "call to SSOIS failed on format error")

        if os.access("backdoor.tsv", os.R_OK):
            lines += open("backdoor.tsv").read()

        return lines

