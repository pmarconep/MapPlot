from unittest import TestCase
from unittest.mock import patch, MagicMock
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from staticmap import StaticMap, Map3D


class LonLatConversionTest(TestCase):
    def testLon(self):
        for lon in range(-180, 180, 20):
            for zoom in range(0, 10):
                x = _lon_to_x(zoom)
                l = _x_to_lon(zoom)
                self.assertAlmostEqual(lon, l, places=5)

    def testLat(self):
        for lat in range(-89, 89, 2):
            for zoom in range(0, 10):
                y = _lat_to_y(zoom)
                l = _y_to_lat(zoom)
                self.assertAlmostEqual(lat, l, places=5)


def _make_tile_response():
    """Return (200, PNG bytes) for a plain grey tile."""
    img = Image.new("RGBA", (256, 256), (200, 200, 200, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return 200, buf.getvalue()


class Map3DImportTest(TestCase):
    def test_import_from_staticmap(self):
        from staticmap import Map3D as M
        from staticmap.plots import Map3D as M2
        self.assertIs(M, M2)


class Map3DInitTest(TestCase):
    def setUp(self):
        self.m = Map3D(center=(-70.65, -33.45), zoom=12, width=256, height=256)

    def test_extent_ordered(self):
        self.assertLess(self.m.lon_min, self.m.lon_max)
        self.assertLess(self.m.lat_min, self.m.lat_max)

    def test_center_within_extent(self):
        lon, lat = self.m.center
        self.assertLess(self.m.lon_min, lon)
        self.assertLess(lon, self.m.lon_max)
        self.assertLess(self.m.lat_min, lat)
        self.assertLess(lat, self.m.lat_max)


class Map3DFeaturesTest(TestCase):
    def setUp(self):
        self.m = Map3D(center=(-70.65, -33.45), zoom=12, width=256, height=256)

    def test_add_bars(self):
        self.m.add_bars([(-70.65, -33.45)], [100])
        self.assertEqual(len(self.m._bars), 1)
        self.assertEqual(len(self.m._bars[0]["values"]), 1)

    def test_add_points_default_values(self):
        self.m.add_points([(-70.65, -33.45)])
        self.assertEqual(self.m._points[0]["values"], [0.0])

    def test_add_line_default_values(self):
        self.m.add_line([(-70.65, -33.45), (-70.64, -33.46)])
        self.assertEqual(self.m._lines[0]["values"], [0.0, 0.0])

    def test_default_bar_width_positive(self):
        self.m.add_bars([(-70.65, -33.45)], [50])
        self.assertGreater(self.m._bars[0]["bar_width"], 0)


class Map3DRenderTest(TestCase):
    def setUp(self):
        self.m = Map3D(center=(-70.65, -33.45), zoom=12, width=256, height=256)
        self.m.add_bars([(-70.65, -33.45), (-70.64, -33.46)], [200, 350])
        self.m.add_points([(-70.64, -33.46)], [150], color="green")
        self.m.add_line(
            [(-70.65, -33.45), (-70.64, -33.46)], [200, 350], color="red"
        )

    def tearDown(self):
        plt.close("all")

    def test_render_no_map(self):
        fig, ax = self.m.render(show_map=False, show_elevation=False)
        self.assertIsNotNone(fig)

    def test_render_with_map(self):
        with patch.object(self.m, "_get_tile", return_value=_make_tile_response()):
            fig, ax = self.m.render(show_map=True, show_elevation=False)
        self.assertIsNotNone(fig)

    def test_render_with_elevation(self):
        fake_elevation = {
            "results": [{"elevation": float(i)} for i in range(100)]
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = fake_elevation

        with patch("staticmap.plots.map3d.requests.post", return_value=mock_resp), \
             patch.object(self.m, "_get_tile", return_value=_make_tile_response()):
            fig, ax = self.m.render(
                show_map=True, show_elevation=True, elevation_n_points=10
            )
        self.assertIsNotNone(fig)

    def test_render_saves_file(self):
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            with patch.object(self.m, "_get_tile", return_value=_make_tile_response()):
                self.m.render(show_map=True, show_elevation=False, savefig=path)
            self.assertGreater(os.path.getsize(path), 0)
        finally:
            os.unlink(path)


class Map3DElevationFallbackTest(TestCase):
    def test_fallback_returns_zeros(self):
        m = Map3D(center=(-70.65, -33.45), zoom=12)
        with patch(
            "staticmap.plots.map3d.requests.post",
            side_effect=RuntimeError("offline"),
        ):
            LON, LAT, elev = m.fetch_elevation(n_points=5)
        self.assertEqual(elev.shape, (5, 5))
        np.testing.assert_array_equal(elev, 0)

