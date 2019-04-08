import os
import pytest

import numpy as np

from astropy.wcs import WCS
from astropy.table import Table
from astropy import units as u
from astropy.coordinates import SkyCoord

from .test_qt_widget import assert_widget_image

from ..core import BaseWWTWidget
from ..layers import TableLayer, guess_lon_lat_columns


class TestLayers:

    def setup_method(self, method):
        self.client = BaseWWTWidget()
        self.table = Table()
        self.table['flux'] = [2, 3, 4]
        self.table['dec'] = [4, 5, 6]
        self.table['ra'] = [1, 2, 3] * u.deg

    def test_add_and_remove_layer(self, capsys):

        assert len(self.client.layers) == 0
        assert str(self.client.layers) == 'Layer manager with no layers'
        layer1 = self.client.layers.add_table_layer(table=self.table)
        assert len(self.client.layers) == 1
        assert str(self.client.layers) == ('Layer manager with 1 layers:\n\n'
                                           '  [0]: TableLayer with 3 markers\n')

        layer2 = self.client.layers.add_table_layer(table=self.table)

        assert len(self.client.layers) == 2
        assert str(self.client.layers) == ('Layer manager with 2 layers:\n\n'
                                           '  [0]: TableLayer with 3 markers\n'
                                           '  [1]: TableLayer with 3 markers\n')

        assert self.client.layers[0] is layer1
        assert self.client.layers[1] is layer2

        # Test iteration
        for layer in self.client.layers:
            assert isinstance(layer, TableLayer)

        layer1.remove()

        assert len(self.client.layers) == 1
        assert str(self.client.layers) == ('Layer manager with 1 layers:\n\n'
                                           '  [0]: TableLayer with 3 markers\n')

        self.client.layers.remove_layer(layer2)

        assert len(self.client.layers) == 0
        assert str(self.client.layers) == 'Layer manager with no layers'

    def test_alt_unit(self):

        layer = self.client.layers.add_table_layer(table=self.table)

        # Using a string
        layer.alt_unit = 'm'

        # Using a string of an imperial unit
        layer.alt_unit = 'inch'

        # Using an astropy unit
        layer.alt_unit = u.km

        # Using a unit that is equal but not identical to one of the accepted ones
        layer.alt_unit = u.def_unit('same_as_km', 1000 * u.m)

        # Using an invalid string
        with pytest.raises(ValueError) as exc:
            layer.alt_unit = 'banana'
        assert exc.value.args[0].strip() == "'banana' did not parse as unit: At col 0, banana is not a valid unit."

        # Using an unsupported unit
        with pytest.raises(ValueError) as exc:
            layer.alt_unit = u.kg
        assert exc.value.args[0].strip() == "alt_unit should be one of AU/Mpc/ft/inch/km/lyr/m/mi/pc"

        # Using a non-equal custom unit
        with pytest.raises(ValueError) as exc:
            layer.alt_unit = u.def_unit('same_as_half_km', 500 * u.m)
        assert exc.value.args[0].strip() == "alt_unit should be one of AU/Mpc/ft/inch/km/lyr/m/mi/pc"

    def test_lon_unit(self):

        layer = self.client.layers.add_table_layer(table=self.table)

        # Using a string
        layer.lon_unit = 'deg'

        # Using an astropy unit
        layer.lon_unit = u.hourangle

        # Using a unit that is equal but not identical to one of the accepted ones
        layer.lon_unit = u.def_unit('same_as_deg', 3600 * u.arcsec)

        # Using an invalid string
        with pytest.raises(ValueError) as exc:
            layer.lon_unit = 'banana'
        assert exc.value.args[0].strip() == "'banana' did not parse as unit: At col 0, banana is not a valid unit."

        # Using an unsupported unit
        with pytest.raises(ValueError) as exc:
            layer.lon_unit = u.kg
        assert exc.value.args[0].strip() == "lon_unit should be one of deg/h/hourangle"

        # Using a non-equal custom unit
        with pytest.raises(ValueError) as exc:
            layer.lon_unit = u.def_unit('same_as_arcmin', 60 * u.arcsec)
        assert exc.value.args[0].strip() == "lon_unit should be one of deg/h/hourangle"

    def test_alt_type(self):

        layer = self.client.layers.add_table_layer(table=self.table)

        layer.alt_type = 'depth'

        with pytest.raises(ValueError) as exc:
            layer.alt_type = 'time'
        assert exc.value.args[0].strip() == "alt_type should be one of depth/altitude/distance/seaLevel/terrain"

    def test_auto_alt_unit(self):

        self.table['altitude'] = [1, 4, 5] * u.au
        self.table['altitude2'] = [1, 4, 5] * u.def_unit('same_as_km', 1000 * u.m)
        self.table['flux'].unit = u.kg

        layer = self.client.layers.add_table_layer(table=self.table)

        assert layer.alt_att == ''
        assert layer.alt_unit is None

        layer.alt_att = 'altitude'
        assert layer.alt_unit is u.au

        layer.alt_att = 'altitude2'
        assert layer.alt_unit is u.km

        expected_warning = ('Column flux has units of kg but this is not a '
                            'valid unit of altitude - set the unit directly with '
                            'alt_unit')

        with pytest.warns(UserWarning, match=expected_warning):
            layer.alt_att = 'flux'

    def test_auto_lon_unit(self):

        self.table['longitude'] = [1, 4, 5] * u.hour
        self.table['longitude2'] = [1, 4, 5] * u.def_unit('same_as_deg', 3600 * u.arcsec)
        self.table['flux'].unit = u.kg

        layer = self.client.layers.add_table_layer(table=self.table)

        assert layer.lon_att == 'ra'
        assert layer.lon_unit is u.deg

        layer.lon_att = 'longitude'
        assert layer.lon_unit is u.hour

        layer.lon_att = 'longitude2'
        assert layer.lon_unit is u.deg

        expected_warning = ('Column flux has units of kg but this is not a '
                            'valid unit of longitude - set the unit directly with '
                            'lon_unit')

        with pytest.warns(UserWarning, match=expected_warning):
            layer.lon_att = 'flux'

    def test_update_data(self):

        self.table['flux'].unit = 'm'
        layer = self.client.layers.add_table_layer(table=self.table,
                                                  lon_att='ra', lat_att='dec', alt_att='flux')

        assert layer.lon_att == 'ra'
        assert layer.lon_unit is u.deg
        assert layer.lat_att == 'dec'
        assert layer.alt_att == 'flux'
        assert layer.alt_unit is u.m

        # Replace with a table with the same column names but different units
        # for the lon and alt
        table = Table()
        table['ra'] = [1, 2, 3] * u.hourangle
        table['dec'] = [4, 5, 6]
        table['flux'] = [2, 3, 4] * u.km
        layer.update_data(table=table)

        assert layer.lon_att == 'ra'
        assert layer.lon_unit is u.hourangle
        assert layer.lat_att == 'dec'
        assert layer.alt_att == 'flux'
        assert layer.alt_unit is u.km

        # Replace with a table with different column names
        table = Table()
        table['a'] = [1, 2, 3] * u.deg
        table['b'] = [4, 5, 6]
        table['c'] = [2, 3, 4] * u.au
        layer.update_data(table=table)

        assert layer.lon_att == 'a'
        assert layer.lon_unit is u.deg
        assert layer.lat_att == 'b'
        assert layer.alt_att == ''


CASES = [[('flux', 'dec', 'ra'), ('ra', 'dec')],
         [('mass', 'lat', 'lon'), ('lon', 'lat')],
         [('a', 'lng', 'b', 'lat'), ('lng', 'lat')],
         [('flux', 'ra', 'radius', 'dec'), ('ra', 'dec')],
         [('FLUX', 'DECJ2000', 'RAJ2000'), ('RAJ2000', 'DECJ2000')],
         [('DISTANCE', 'LON1', 'LAT1'), ('LON1', 'LAT1')],
         [('flux', 'lng2', 'lat2', 'lng1', 'lat1'), (None, None)],
         [('ra', 'ra', 'dec'), (None, None)]]


@pytest.mark.parametrize(('colnames', 'expected'), CASES)
def test_guess_lon_lat_columns(colnames, expected):
    assert guess_lon_lat_columns(colnames) == expected


def test_layers_image(tmpdir, wwt_qt_client):

    # A series of tests that excercise the layer functionality and compare
    # the results with a set of baseline images.

    wwt = wwt_qt_client

    wwt.foreground = 'Black Sky Background'
    wwt.background = 'Black Sky Background'

    # TODO: need a way to completely turn off sun + planets. For now we just
    # point towards the ecliptic North pole
    wwt.center_on_coordinates(SkyCoord(18 * u.hourangle, 66 * u.deg))

    # Simple default case

    table = Table()
    table['flux'] = [2, 3, 4, 5, 6]
    table['dec'] = [84, 85, 86, 87, 88]
    table['ra'] = [250, 260, 270, 280, 290] * u.deg

    layer1 = wwt.layers.add_table_layer(table=table)

    # Case where we change the default values on initialization

    table = Table()
    table['flux'] = [2, 3, 4, 5, 6]
    table['dec'] = [74, 75, 76, 77, 78]
    table['ra'] = [250, 260, 270, 280, 290] * u.deg
    table['other'] = [255, 265, 275, 285, 295] * u.deg

    layer2 = wwt.layers.add_table_layer(table=table, color='red', lon_att='other', size_scale=100, opacity=0.5)

    # Case where we change the values after initialization

    table = Table()
    table['flux'] = [2, 3, 4, 5, 6]
    table['dec'] = [64, 65, 66, 67, 68]
    table['ra'] = [250, 260, 270, 280, 290] * u.deg
    table['other'] = [255, 265, 275, 285, 295] * u.deg

    layer3 = wwt.layers.add_table_layer(table=table)

    wwt.wait(2)

    layer3.color = 'green'
    layer3.lon_att = 'other'
    layer3.size_scale = 50
    layer3.opacity = 0.8

    # Case with size and color encoding where we change the default values on initialization

    table = Table()
    table['flux'] = [2, 3, 4, 5, 6]
    table['dec'] = [54, 55, 56, 57, 58]
    table['ra'] = [250, 260, 270, 280, 290] * u.deg
    table['other'] = [255, 265, 275, 285, 295] * u.deg

    layer4 = wwt.layers.add_table_layer(table=table, cmap_att='other', size_att='flux')

    # Case with size and color encoding where we change the values after initialization

    table = Table()
    table['flux'] = [2, 3, 4, 5, 6]
    table['dec'] = [44, 45, 46, 47, 48]
    table['ra'] = [250, 260, 270, 280, 290] * u.deg
    table['other'] = [255, 265, 275, 285, 295] * u.deg

    layer5 = wwt.layers.add_table_layer(table=table)

    wwt.wait(2)

    layer5.cmap_att = 'other'
    layer5.size_att = 'flux'

    wwt.wait(2)

    # For now this test doesn't work in CI, seemingly because of some
    # OpenGL features that aren't available there.
    if os.environ.get('CI', 'false').lower() == 'false':
        assert_widget_image(tmpdir, wwt, 'sky_layers.png')


def test_image_layer_equ(tmpdir, wwt_qt_client_isolated):

    # A series of tests that excercise the image layer functionality and compare
    # the results with a set of baseline images.

    # NOTE: due to an unknown issue, we need to run this using an isolated
    # Qt client and we can't re-use the usual wwt_qt_client fixture, as loading
    # the image layer appears to have some kind of irreversible impact on the
    # state of the Qt widget.

    wwt = wwt_qt_client_isolated

    wwt.foreground = 'Black Sky Background'
    wwt.background = 'Black Sky Background'

    wwt.center_on_coordinates(SkyCoord(30 * u.deg, 40 * u.deg))

    array = np.arange(10000).reshape((100, 100))
    wcs = WCS()
    wcs.wcs.ctype = 'RA---TAN', 'DEC--TAN'
    # wcs.wcs.ctype = 'GLON-CAR', 'GLAT-CAR'
    wcs.wcs.crval = 30, 40
    wcs.wcs.crpix = 50.5, 50.5
    wcs.wcs.cdelt = -0.1, 0.1

    wwt.layers.add_image_layer(image=(array, wcs))

    wwt.wait(2)

    # For now this test doesn't work in CI, seemingly because of some
    # OpenGL features that aren't available there.
    if os.environ.get('CI', 'false').lower() == 'false':
        assert_widget_image(tmpdir, wwt, 'image_layer_equ.png')


def test_image_layer_gal(tmpdir, wwt_qt_client_isolated):

    # A series of tests that excercise the image layer functionality and compare
    # the results with a set of baseline images.

    # NOTE: due to an unknown issue, we need to run this using an isolated
    # Qt client and we can't re-use the usual wwt_qt_client fixture, as loading
    # the image layer appears to have some kind of irreversible impact on the
    # state of the Qt widget.

    wwt = wwt_qt_client_isolated

    wwt.foreground = 'Black Sky Background'
    wwt.background = 'Black Sky Background'

    array = np.arange(10000).reshape((100, 100))
    wcs = WCS()
    wcs.wcs.ctype = 'GLON-CAR', 'GLAT-CAR'
    wcs.wcs.crpix = 50.5, 50.5
    wcs.wcs.cdelt = -0.03, 0.03

    wcs.wcs.crval = 33, 43
    wwt.layers.add_image_layer(image=(array, wcs))

    wcs.wcs.crval = 27, 43
    layer2 = wwt.layers.add_image_layer(image=(array, wcs))
    layer2.vmin = -5000
    layer2.vmax = 15000

    wcs.wcs.crval = 27, 37
    layer3 = wwt.layers.add_image_layer(image=(array, wcs))
    layer3.stretch = 'log'

    wcs.wcs.crval = 33, 37
    layer4 = wwt.layers.add_image_layer(image=(array, wcs))
    layer4.opacity = 0.5

    wwt.wait(2)

    wwt.center_on_coordinates(SkyCoord(30 * u.deg, 40 * u.deg, frame='galactic'), fov=14 * u.deg)

    wwt.wait(2)

    # For now this test doesn't work in CI, seemingly because of some
    # OpenGL features that aren't available there.
    if os.environ.get('CI', 'false').lower() == 'false':
        assert_widget_image(tmpdir, wwt, 'image_layer_gal.png')
